use serde::{Deserialize, Serialize};
use serde_json::Value;
use sea_orm::entity::prelude::*;

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
  pub hyperparameters: Json,	// SeaORMのJson型


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
  /// 開始日時
  #[serde(with = "time::serde::iso8601::option")]
  pub start_at: Option<TimeDateTimeWithTimeZone>, // SeaORMのTime型
	/// 完了日時
  #[serde(with = "time::serde::iso8601::option")]
  pub completed_at: Option<TimeDateTimeWithTimeZone>,
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