use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::entities::experiment::{MiaMethod, Model};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CreateTaskRequest {
	/// 実験ID
	pub experiment_id: i64,
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


/// entities::experiment::Model から CreateTaskRequest への変換を定義
impl From<&Model> for CreateTaskRequest {
	fn from(model: &Model) -> Self {
		Self {
			experiment_id: model.id,
			name: model.name.clone(),
			notes: model.notes.clone(),
			method: model.method.clone(),
			// -- 条件 --
			batch_size: model.batch_size,
			max_epochs: model.max_epochs,
			num_shadow_models: model.num_shadow_models,
			target_train_size: model.target_train_size,
			target_test_size: model.target_test_size,
			shadow_train_size: model.shadow_train_size,
			shadow_test_size: model.shadow_test_size,
			seed: model.seed,
			hyperparameters: model.hyperparameters.clone(),
			// -- データ流用 --
			base_experiment_id: model.base_experiment_id,
			load_target_model: model.load_target_model,
			load_shadow_model: model.load_shadow_model,
			load_attack_model: model.load_attack_model,
		}
	}
}