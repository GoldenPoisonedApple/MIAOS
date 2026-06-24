use sea_orm::entity::prelude::*;
use sea_orm::ActiveValue::{Set, Unchanged};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use time::OffsetDateTime;
use utoipa::ToSchema;

use crate::dto::experiment::{ClaimExperimentRequest, UpdateResultsRequest};
use crate::error::ServerError;

#[derive(
  Debug, Clone, PartialEq, Eq, EnumIter, DeriveActiveEnum, Serialize, Deserialize, ToSchema,
)]
#[sea_orm(rs_type = "String", db_type = "Enum", enum_name = "experiment_status")]
pub enum ExperimentStatus {
  #[sea_orm(string_value = "WAITING")]
  Waiting,
  #[sea_orm(string_value = "RUNNING")]
  Running,
  #[sea_orm(string_value = "SUCCEEDED")]
  Succeeded,
  #[sea_orm(string_value = "FAILED")]
  Failed,
}

impl ExperimentStatus {
  /// 処理取得が可能かどうか
  /// * 戻り値: bool - 処理取得が可能かどうか
  pub fn can_claim(&self) -> bool {
    // Waitingのみ
    matches!(self, ExperimentStatus::Waiting)
  }

  /// 結果反映が可能かどうか
  /// * next: ExperimentStatus - 次のステータス
  /// * 戻り値: bool - 結果反映が可能かどうか
  pub fn can_complete_to(&self, next: &ExperimentStatus) -> bool {
    // RunningからSucceededまたはFailedへの遷移のみ可能
    matches!(self, ExperimentStatus::Running)
      && matches!(next, ExperimentStatus::Succeeded | ExperimentStatus::Failed)
  }
}

#[derive(
  Debug, Clone, PartialEq, Eq, EnumIter, DeriveActiveEnum, Serialize, Deserialize, ToSchema,
)]
#[sea_orm(rs_type = "String", db_type = "Enum", enum_name = "mia_method")]
pub enum MiaMethod {
  #[sea_orm(string_value = "offline_lira")]
  OfflineLira,
  #[sea_orm(string_value = "shokri")]
  Shokri,
}

// DBの1行と1対1で対応する構造体
// 名前はModelにしておくと、SeaORMのデフォルトの挙動になる
#[derive(Clone, Debug, PartialEq, DeriveEntityModel, Serialize, Deserialize, ToSchema)]
#[sea_orm(table_name = "experiments")]
pub struct Model {
  /// 主キー
  #[sea_orm(primary_key)]
  pub id: i64,
  /// 実験名
  pub name: String,
  /// 備考
  pub notes: Option<String>,
  /// 攻撃手法
  pub method: MiaMethod,

  // 条件
  /// バッチサイズ
  pub batch_size: i32,
  /// 最大エポック数
  pub max_epochs: i32,
  /// シャドウモデル数
  pub num_shadow_models: i32,
  /// ターゲットモデルのトレーニングサイズ
  pub target_train_size: i32,
  /// ターゲットモデルのテストサイズ
  pub target_test_size: i32,
  /// シャドウモデルのトレーニングサイズ
  pub shadow_train_size: i32,
  /// シャドウモデルのテストサイズ
  pub shadow_test_size: i32,
  /// シード値
  pub seed: i32,
  /// その他のハイパーパラメータ
  #[schema(value_type = Object)]
  pub hyperparameters: Json, // SeaORMのJson型
  /// 透かし設定
  #[schema(value_type = Object)]
  pub watermark: Json,

  // データ流用
  /// 既存実験結果を流用する実験結果
  pub base_experiment_id: Option<i64>,
  /// ターゲットモデルを読み込むかどうか
  pub load_target_model: bool,
  /// シャドウモデルを読み込むかどうか
  pub load_shadow_model: bool,
  /// 攻撃モデルを読み込むかどうか
  pub load_attack_model: bool,

  // 環境・状態
  /// ステータス
  pub status: ExperimentStatus,
  /// 作業PC名
  pub worker_name: Option<String>,
  /// 完了日時
  #[serde(with = "time::serde::iso8601::option")]
  #[schema(value_type = Option<String>, format = DateTime)]
  pub completed_at: Option<TimeDateTimeWithTimeZone>, // SeaORMのTime型
  /// エラーメッセージ
  pub error_message: Option<String>,

  // 結果
  /// 全体のAUC
  pub global_auc: Option<f64>,
  /// 1%FPRでのTPR
  pub tpr_at_1_fpr: Option<f64>,
  /// 1%FPRでの閾値
  pub threshold_at_1_fpr: Option<f64>,
  /// 0.1%FPRでのTPR
  pub tpr_at_01_fpr: Option<f64>,
  /// 0.1%FPRでの閾値
  pub threshold_at_01_fpr: Option<f64>,
  /// その他のメトリクス
  #[schema(value_type = Option<Object>)]
  pub other_metrics: Option<Value>,
  /// トータルの実行時間(秒)
  pub total_time: Option<f64>,

  // ファイル
  #[schema(value_type = Option<Object>)]
  pub files: Option<Value>,

  // メタ情報
  /// 作成日時
  // OffsetDateTimeをISO8601形式でシリアライズ
  #[serde(with = "time::serde::iso8601")]
  #[schema(value_type = String, format = DateTime)]
  pub created_at: TimeDateTimeWithTimeZone,
}

// リレーションシップの定義（今回は自己参照のみ）
#[derive(Copy, Clone, Debug, EnumIter, DeriveRelation)]
pub enum Relation {
  #[sea_orm(
    belongs_to = "Entity",
    from = "Column::BaseExperimentId",
    to = "Column::Id"
  )]
  SelfReferencing,
}

/// データベースに保存する直前 or 直後に特定の処理を挟むためのトレイト
impl ActiveModelBehavior for ActiveModel {}

// Rich Domain Modelを頑張る
// createの処理については idがないのでどうしようもない 新規作成時に複雑なビジネスロジックがないのでDTOをそのままrepositoryにねじ込む構造
// 複雑なロジックがある場合は、serviceとrepositoryの間のDTOを作成するのが良いかと
impl Model {
  /// 結果を反映する
  pub fn complete(
    &mut self,
    results: UpdateResultsRequest,
    completed_at: OffsetDateTime,
  ) -> Result<(), ServerError> {
    // 状態遷移ルールブロッキング
    if !self.status.can_complete_to(&results.status) {
      return Err(ServerError::Conflict(format!(
        "結果反映が可能ではありません: {:?} -> {:?}",
        self.status, results.status
      )));
    }
    // 状態遷移のルール
    self.status = results.status;
    self.error_message = results.error_message;
    self.completed_at = Some(completed_at);

    // 結果の反映
    self.worker_name = Some(results.worker_name);
    // 結果
    self.global_auc = results.global_auc;
    self.tpr_at_1_fpr = results.tpr_at_1_fpr;
    self.threshold_at_1_fpr = results.threshold_at_1_fpr;
    self.tpr_at_01_fpr = results.tpr_at_01_fpr;
    self.threshold_at_01_fpr = results.threshold_at_01_fpr;
    self.other_metrics = Some(results.other_metrics);
    // 時間
    self.total_time = results.total_time;
    // ファイル
    self.files = Some(results.files);

    Ok(())
  }

  /// 処理取得の報告
  pub fn claim(&mut self, claim: ClaimExperimentRequest) -> Result<(), ServerError> {
    // 状態遷移ルールブロッキング
    if !self.status.can_claim() {
      return Err(ServerError::Conflict(format!(
        "既に処理が報告されています: {:?}",
        self.status
      )));
    }
    self.status = ExperimentStatus::Running;
    self.worker_name = Some(claim.worker_name);

    Ok(())
  }

  // SeaORMの仕様のせいでつくってる変換 Updateを通知してあげる
  pub fn into_active_model_for_update(self) -> ActiveModel {
    ActiveModel {
      id: Unchanged(self.id), // 更新対象ではないのでUnchanged
      name: Set(self.name),
      notes: Set(self.notes),
      method: Set(self.method),
      batch_size: Set(self.batch_size),
      max_epochs: Set(self.max_epochs),
      num_shadow_models: Set(self.num_shadow_models),
      target_train_size: Set(self.target_train_size),
      target_test_size: Set(self.target_test_size),
      shadow_train_size: Set(self.shadow_train_size),
      shadow_test_size: Set(self.shadow_test_size),
      seed: Set(self.seed),
      hyperparameters: Set(self.hyperparameters),
      watermark: Set(self.watermark),
      base_experiment_id: Set(self.base_experiment_id),
      load_target_model: Set(self.load_target_model),
      load_shadow_model: Set(self.load_shadow_model),
      load_attack_model: Set(self.load_attack_model),
      status: Set(self.status),
      worker_name: Set(self.worker_name),
      completed_at: Set(self.completed_at),
      error_message: Set(self.error_message),
      global_auc: Set(self.global_auc),
      tpr_at_1_fpr: Set(self.tpr_at_1_fpr),
      threshold_at_1_fpr: Set(self.threshold_at_1_fpr),
      tpr_at_01_fpr: Set(self.tpr_at_01_fpr),
      threshold_at_01_fpr: Set(self.threshold_at_01_fpr),
      other_metrics: Set(self.other_metrics),
      total_time: Set(self.total_time),
      files: Set(self.files),
      created_at: Unchanged(self.created_at), // 作成日時は更新対象ではないのでUnchanged
    }
  }
}

#[cfg(test)]
mod tests {
  use super::*;
  use crate::test_utils::update_experiment_request_factory;

  /// モデルファクトリ
  fn create_model() -> Model {
    Model {
      id: 1,
      name: "test_experiment".to_string(),
      notes: Some("backend_test".to_string()),
      method: MiaMethod::OfflineLira,
      batch_size: 10,
      max_epochs: 10,
      num_shadow_models: 10,
      target_train_size: 10,
      target_test_size: 10,
      shadow_train_size: 10,
      shadow_test_size: 10,
      seed: 10,
      hyperparameters: serde_json::json!({}),
      watermark: serde_json::json!({}),
      base_experiment_id: None,
      load_target_model: false,
      load_shadow_model: false,
      load_attack_model: false,
      status: ExperimentStatus::Waiting,
      worker_name: None,
      completed_at: None,
      error_message: None,
      global_auc: None,
      tpr_at_1_fpr: None,
      threshold_at_1_fpr: None,
      tpr_at_01_fpr: None,
      threshold_at_01_fpr: None,
      other_metrics: None,
      total_time: None,
      files: None,
      created_at: OffsetDateTime::now_utc(),
    }
  }

  /// 実験を完了状態にし、結果を反映するテスト
  #[test]
  fn test_complete() {
    // Arrange
    let mut experiment = create_model();
    experiment.status = ExperimentStatus::Running;
    let request = update_experiment_request_factory(experiment.id, ExperimentStatus::Succeeded);
    let completed_at = OffsetDateTime::now_utc();
    // Act
    experiment.complete(request, completed_at).unwrap();
    // Assert
    assert_eq!(experiment.status, ExperimentStatus::Succeeded); // ステータスがセットされていること
    assert_eq!(experiment.completed_at, Some(completed_at)); // 完了時刻がセットされている事
    assert_eq!(experiment.worker_name, Some("test_worker".to_string())); // 結果が反映されていること
  }

  /// 結果反映失敗
  #[test]
  fn test_complete_with_waiting_status() {
    // Arrange
    let mut experiment = create_model();
    experiment.status = ExperimentStatus::Waiting; // 待機のステータスにする
    let request = update_experiment_request_factory(experiment.id, ExperimentStatus::Succeeded);
    let completed_at = OffsetDateTime::now_utc();
    // Act
    let result = experiment.complete(request, completed_at);
    // Assert
    assert!(result.is_err());
    assert!(matches!(result.unwrap_err(), ServerError::Conflict(_)));
  }

  /// 処理取得の報告テスト
  #[test]
  fn test_claim() {
    // Arrange
    let mut experiment = create_model();
    let request = ClaimExperimentRequest {
      id: experiment.id,
      worker_name: "test_worker".to_string(),
    };
    // Act
    experiment.claim(request).unwrap();
    // Assert
    assert_eq!(experiment.status, ExperimentStatus::Running); // ステータスが実行中となっていること
    assert_eq!(experiment.worker_name, Some("test_worker".to_string())); // ワーカーがセットされていること
  }

  /// 報告失敗
  #[test]
  fn test_claim_with_running_status() {
    // Arrange
    let mut experiment = create_model();
    experiment.status = ExperimentStatus::Running; // 実行中のステータスにする
    let request = ClaimExperimentRequest {
      id: experiment.id,
      worker_name: "test_worker".to_string(),
    };
    // Act
    let result = experiment.claim(request);
    // Assert
    assert!(result.is_err());
    assert!(matches!(result.unwrap_err(), ServerError::Conflict(_)));
  }
}
