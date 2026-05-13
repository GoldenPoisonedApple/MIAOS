use serde::{Deserialize, Serialize};
use utoipa::ToSchema;
use uuid::Uuid;

/// タスク
#[derive(Debug, Serialize, Deserialize, Clone, ToSchema)]
pub struct Task {
	/// id
	pub id: Uuid,
	/// タスク名
	pub task: String,
	/// 実験ID
	pub experiment_id: i64,
	// ---- 引数 ----
	/// 位置引数
	#[schema(value_type = Object)]
	pub args_positional: serde_json::Value,
	/// キーワード引数
	#[schema(value_type = Object)]
	pub args_keyword: serde_json::Value,
	/// 制御情報
	#[schema(value_type = Object)]
	pub args_control: serde_json::Value,
	// ----- エラー情報 ----
	/// エラーメッセージ
	pub error_message: Option<String>,
}