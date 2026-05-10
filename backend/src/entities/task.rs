use serde::{Deserialize, Serialize};

/// タスク
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Task {
	/// id
	pub id: String,
	/// タスク名
	pub task: String,
	/// 引数
	pub args: serde_json::Value,
}