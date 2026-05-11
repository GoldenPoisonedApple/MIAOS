use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// タスク
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Task {
	/// id
	pub id: Uuid,
	/// タスク名
	pub task: String,
	// ---- 引数 ----
	/// 位置引数
	pub args_positional: serde_json::Value,
	/// キーワード引数
	pub args_keyword: serde_json::Value,
	/// 制御情報
	pub args_control: serde_json::Value,
	// ----- エラー情報 ----
	/// エラーメッセージ
	pub error_message: Option<String>,
}