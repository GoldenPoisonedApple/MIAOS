use sea_orm::Set;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::config::default::*;
use crate::entities::experiment::{ActiveModel, MiaMethod};

// --- デフォルト値 ---
fn default_load_target_model() -> bool {
  LOAD_TARGET_MODEL
}
fn default_load_shadow_model() -> bool {
  LOAD_SHADOW_MODEL
}
fn default_load_attack_model() -> bool {
  LOAD_ATTACK_MODEL
}
fn default_batch_size() -> i32 {
  BATCH_SIZE
}
fn default_max_epochs() -> i32 {
  MAX_EPOCHS
}
fn default_num_shadow_models() -> i32 {
  NUM_SHADOW_MODELS
}
fn default_target_train_size() -> i32 {
  TARGET_TRAIN_SIZE
}
fn default_target_test_size() -> i32 {
  TARGET_TEST_SIZE
}
fn default_shadow_train_size() -> i32 {
  SHADOW_TRAIN_SIZE
}
fn default_shadow_test_size() -> i32 {
  SHADOW_TEST_SIZE
}
fn default_seed() -> i32 {
  SEED
}

fn default_hyperparameters() -> Value {
  serde_json::json!({})
}

/// 実験の作成リクエスト
#[derive(Debug, Serialize, Deserialize)]
pub struct CreateExperimentRequest {
  /// 実験名
  pub name: String,
  /// 備考
  pub notes: Option<String>,
  /// 攻撃手法
  pub method: MiaMethod,

  // -- 条件 --
  /// バッチサイズ
  #[serde(default = "default_batch_size")]
  pub batch_size: i32,
  /// 最大エポック数
  #[serde(default = "default_max_epochs")]
  pub max_epochs: i32,
  /// シャドウモデル数
  #[serde(default = "default_num_shadow_models")]
  pub num_shadow_models: i32,
  /// ターゲットモデルのトレーニングサイズ
  #[serde(default = "default_target_train_size")]
  pub target_train_size: i32,
  /// ターゲットモデルのテストサイズ
  #[serde(default = "default_target_test_size")]
  pub target_test_size: i32,
  /// シャドウモデルのトレーニングサイズ
  #[serde(default = "default_shadow_train_size")]
  pub shadow_train_size: i32,
  /// シャドウモデルのテストサイズ
  #[serde(default = "default_shadow_test_size")]
  pub shadow_test_size: i32,
  /// シード値
  #[serde(default = "default_seed")]
  pub seed: i32,
  /// その他のハイパーパラメータ
  #[serde(default = "default_hyperparameters")]
  pub hyperparameters: Value,

  // -- データ流用 --
  /// 既存実験結果を流用する実験結果
  #[serde(default)] // デフォルト値はNone
  pub base_experiment_id: Option<i64>,
  /// ターゲットモデルを読み込むかどうか
  #[serde(default = "default_load_target_model")]
  pub load_target_model: bool,
  /// シャドウモデルを読み込むかどうか
  #[serde(default = "default_load_shadow_model")]
  pub load_shadow_model: bool,
  /// 攻撃モデルを読み込むかどうか
  #[serde(default = "default_load_attack_model")]
  pub load_attack_model: bool,
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
