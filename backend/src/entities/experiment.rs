use sea_orm::entity::prelude::*;
use sea_orm::ActiveValue::{Set, Unchanged};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use time::OffsetDateTime;

use crate::dto::experiment::UpdateResultsRequest;

#[derive(Debug, Clone, PartialEq, Eq, EnumIter, DeriveActiveEnum, Serialize, Deserialize)]
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

#[derive(Debug, Clone, PartialEq, Eq, EnumIter, DeriveActiveEnum, Serialize, Deserialize)]
#[sea_orm(rs_type = "String", db_type = "Enum", enum_name = "mia_method")]
pub enum MiaMethod {
  #[sea_orm(string_value = "offline_lira")]
  OfflineLira,
  #[sea_orm(string_value = "shokri")]
  Shokri,
}

// DBの1行と1対1で対応する構造体
// 名前はModelにしておくと、SeaORMのデフォルトの挙動になる
#[derive(Clone, Debug, PartialEq, DeriveEntityModel, Serialize, Deserialize)]
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
  pub hyperparameters: Json, // SeaORMのJson型

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
  pub completed_at: Option<TimeDateTimeWithTimeZone>, // SeaORMのTime型
  /// エラーメッセージ
  pub error_message: Option<String>,

  // 結果
  /// 全体のAUC
  pub global_auc: Option<f64>,
  /// 1%FPRでのTPR
  pub tpr_at_1_fpr: Option<f64>,
  /// 0.1%FPRでのTPR
  pub tpr_at_01_fpr: Option<f64>,
  /// 0.01%FPRでのTPR
  pub tpr_at_001_fpr: Option<f64>,
  /// その他のメトリクス
  pub other_metrics: Option<Value>,
  /// トータルの実行時間(秒)
  pub total_time: Option<f64>,

  // ファイル
  /// MINIOでのベースパス
  pub minio_path: Option<String>,
  /// データセットのパス
  pub dataset_json_path: Option<String>,
  /// 実行ログのパス
  pub execution_log_path: Option<String>,
  /// その他のファイルのパス
  pub other_files: Option<Value>,

  // メタ情報
  /// 作成日時
  // OffsetDateTimeをISO8601形式でシリアライズ
  #[serde(with = "time::serde::iso8601")]
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
  /// 実験を完了状態にし、結果を反映する
  pub fn complete(&mut self, results: UpdateResultsRequest, completed_at: OffsetDateTime) {
    // 状態遷移のルール
    self.status = ExperimentStatus::Succeeded;
    self.completed_at = Some(completed_at);

    // 結果の反映
    self.worker_name = Some(results.worker_name);
		// 結果
    self.global_auc = Some(results.global_auc);
    self.tpr_at_1_fpr = Some(results.tpr_at_1_fpr);
    self.tpr_at_01_fpr = Some(results.tpr_at_01_fpr);
    self.other_metrics = Some(results.other_metrics);
		// 時間
    self.total_time = Some(results.total_time);
		// ファイル
    self.minio_path = Some(results.minio_path);
    self.dataset_json_path = Some(results.dataset_json_path);
    self.execution_log_path = Some(results.execution_log_path);
    self.other_files = Some(results.other_files);
  }

	// SeaORMの仕様のせいでつくってる変換 Updateを通知してあげる
	pub fn into_active_model_for_update(&self) -> ActiveModel {
		ActiveModel {
			id: Unchanged(self.id),	// 更新対象ではないのでUnchanged
			name: Set(self.name.clone()),
			notes: Set(self.notes.clone()),
			method: Set(self.method.clone()),
			batch_size: Set(self.batch_size),
			max_epochs: Set(self.max_epochs),
			num_shadow_models: Set(self.num_shadow_models),
			target_train_size: Set(self.target_train_size),
			target_test_size: Set(self.target_test_size),
			shadow_train_size: Set(self.shadow_train_size),
			shadow_test_size: Set(self.shadow_test_size),
			seed: Set(self.seed),
			hyperparameters: Set(self.hyperparameters.clone()),
			base_experiment_id: Set(self.base_experiment_id),
			load_target_model: Set(self.load_target_model),
			load_shadow_model: Set(self.load_shadow_model),
			load_attack_model: Set(self.load_attack_model),
			status: Set(self.status.clone()),
			worker_name: Set(self.worker_name.clone()),
			completed_at: Set(self.completed_at),
			error_message: Set(self.error_message.clone()),
			global_auc: Set(self.global_auc),
			tpr_at_1_fpr: Set(self.tpr_at_1_fpr),
			tpr_at_01_fpr: Set(self.tpr_at_01_fpr),
			tpr_at_001_fpr: Set(self.tpr_at_001_fpr),
			other_metrics: Set(self.other_metrics.clone()),
			total_time: Set(self.total_time),
			minio_path: Set(self.minio_path.clone()),
			dataset_json_path: Set(self.dataset_json_path.clone()),
			execution_log_path: Set(self.execution_log_path.clone()),
			other_files: Set(self.other_files.clone()),
			created_at: Unchanged(self.created_at),	// 作成日時は更新対象ではないのでUnchanged
		}
	}
}
