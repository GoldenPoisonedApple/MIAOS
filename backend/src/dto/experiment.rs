use sea_orm::Set;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::config::default::*;
use crate::entities::experiment::{ActiveModel, MiaMethod};

/// 実験の作成リクエスト
#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(default)] // 欠損値はデフォルト値(Default::default())を使用する
pub struct CreateExperimentRequest {
  /// 実験名
  pub name: String,
  /// 備考
  pub notes: Option<String>,
  /// 攻撃手法
  pub method: MiaMethod,

  // -- 条件 --
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
  pub hyperparameters: Value,

  // -- データ流用 --
  /// 既存実験結果を流用する実験結果
  pub base_experiment_id: Option<i64>,
  /// ターゲットモデルを読み込むかどうか
  pub load_target_model: bool,
  /// シャドウモデルを読み込むかどうか
  pub load_shadow_model: bool,
  /// 攻撃モデルを読み込むかどうか
  pub load_attack_model: bool,
}

/// デフォルト
/// 各種設定値は config/default.rs から引っ張る
impl Default for CreateExperimentRequest {
  fn default() -> Self {
    Self {
      name: EXPERIMENT_NAME(),
      notes: EXPERIMENT_NOTES,
      method: MIA_METHOD,
      // 条件
      batch_size: BATCH_SIZE,
      max_epochs: MAX_EPOCHS,
      num_shadow_models: NUM_SHADOW_MODELS,
      target_train_size: TARGET_TRAIN_SIZE,
      target_test_size: TARGET_TEST_SIZE,
      shadow_train_size: SHADOW_TRAIN_SIZE,
      shadow_test_size: SHADOW_TEST_SIZE,
      seed: SEED,
      hyperparameters: serde_json::json!({}),
      // データ流用
      base_experiment_id: None,
      load_target_model: LOAD_TARGET_MODEL,
      load_shadow_model: LOAD_SHADOW_MODEL,
      load_attack_model: LOAD_ATTACK_MODEL,
    }
  }
}

// CreateExperimentRequest から ActiveModel への変換を定義
impl From<CreateExperimentRequest> for ActiveModel {
  fn from(req: CreateExperimentRequest) -> Self {
    Self {
      name: Set(req.name),
      notes: Set(req.notes),
      method: Set(req.method),

      // 条件
      batch_size: Set(req.batch_size),
      max_epochs: Set(req.max_epochs),
      num_shadow_models: Set(req.num_shadow_models),
      target_train_size: Set(req.target_train_size),
      target_test_size: Set(req.target_test_size),
      shadow_train_size: Set(req.shadow_train_size),
      shadow_test_size: Set(req.shadow_test_size),
      seed: Set(req.seed),
      hyperparameters: Set(req.hyperparameters),

      // データ流用
      base_experiment_id: Set(req.base_experiment_id),
      load_target_model: Set(req.load_target_model),
      load_shadow_model: Set(req.load_shadow_model),
      load_attack_model: Set(req.load_attack_model),

      // DBのデフォルト値に任せるカラム（status, created_atなど）は
      // `..Default::default()` で処理されるため書かなくてOK
      ..Default::default()
    }
  }
}

/// 実験の結果更新リクエスト
#[derive(Debug, Serialize, Deserialize)]
pub struct UpdateResultsRequest {
  /// 実験ID
  pub experiment_id: i64,
  /// 作業PC名
  pub worker_name: String,

  /// 全体のAUC
  pub global_auc: f64,
  /// 1%FPRでのTPR
  pub tpr_at_1_fpr: f64,
  /// 0.1%FPRでのTPR
  pub tpr_at_01_fpr: f64,
  /// 拡張メトリクス
  pub other_metrics: Value,

  /// トータルの実行時間(秒)
  pub total_time: f64,

  /// MINIOでのベースパス
  pub minio_path: String,
  /// データセットのパス
  pub dataset_json_path: String,
  /// 実行ログのパス
  pub execution_log_path: String,
  /// その他のファイルのパス
  pub other_files: Value,
}

// UpdateResultsRequest から ActiveModel への変換を定義
impl From<UpdateResultsRequest> for ActiveModel {
  fn from(req: UpdateResultsRequest) -> Self {
    Self {
      id: Set(req.experiment_id),
      worker_name: Set(Some(req.worker_name)),

      global_auc: Set(Some(req.global_auc)),
      tpr_at_1_fpr: Set(Some(req.tpr_at_1_fpr)),
      tpr_at_01_fpr: Set(Some(req.tpr_at_01_fpr)),
      other_metrics: Set(Some(req.other_metrics)),

      total_time: Set(Some(req.total_time)),

      minio_path: Set(Some(req.minio_path)),
      dataset_json_path: Set(Some(req.dataset_json_path)),
      execution_log_path: Set(Some(req.execution_log_path)),
      other_files: Set(Some(req.other_files)),

      // 他パラメータは上書きしないので空
      ..Default::default()
    }
  }
}
