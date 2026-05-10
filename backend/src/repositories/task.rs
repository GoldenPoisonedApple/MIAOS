use async_trait::async_trait;
use base64::{engine::general_purpose, Engine as _};
use deadpool_redis::Pool;
use redis::{AsyncCommands, RedisError};
use serde_json::Value;
use celery::prelude::*;
use crate::error::ServerError;

use crate::dto::task::CreateTaskRequest;
use crate::entities::task::Task;

#[async_trait]
pub trait TaskRepositoryTrait: Send + Sync {
  // async fn create_task(&self, request: CreateTaskRequest) -> Result<(), RedisError>;
  async fn find_all_tasks(&self) -> Result<Vec<Task>, ServerError>;
}

#[derive(Clone)]
pub struct TaskRepository {
  pool: Pool,
}

impl TaskRepository {
  /// コンストラクタ
  pub fn new(pool: Pool) -> Self {
    Self { pool }
  }

  /// ボディをデコード
  fn decode_body(body: &str) -> Result<Value, ServerError> {
    let decoded = general_purpose::STANDARD.decode(body)?;
    let json = String::from_utf8(decoded)?;
    let parsed = serde_json::from_str(&json)?;

		Ok(parsed)
  }
}

/// TaskRepositoryの実装
#[async_trait]
impl TaskRepositoryTrait for TaskRepository {
  // /// タスクの作成
  // async fn create_task(&self, request: CreateTaskRequest) -> Result<(), RedisError> {
  //   let task = Task::from(request);
  //   let mut conn = self
  //     .pool
  //     .get()
  //     .await
  //     .map_err(|e| RedisError::from((redis::ErrorKind::Io, "Pool error", e.to_string())))?;
  //   let serialized = serde_json::to_string(&task).unwrap();
  //   conn.set(task.id, serialized).await?;
  //   Ok(())
  // }

  /// すべてのタスクを取得
  async fn find_all_tasks(&self) -> Result<Vec<Task>, ServerError> {
		// Redis接続 複雑なエラーを返すため、Stringとして返す
    let mut conn = self.pool.get().await.map_err(|e| ServerError::PoolError(e.to_string()))?;
		// タスクの取得
    let results: Vec<String> = conn.lrange("celery", 0, -1).await?;

		// タスクの解析 取得
    let mut tasks: Vec<Task> = Vec::new();
    for result in results {
      let json: Value = serde_json::from_str(&result)?;
      let body = match json["body"].as_str() {
        Some(body) => body,
        None => return Err(ServerError::DataFormatError("Missing or invalid 'body'".to_string())),
      };
      let args: Value = Self::decode_body(body)?;

			// idとtaskを取得
			let headers = &json["headers"];
			let id = match headers["id"].as_str() {
				Some(id) => id.to_string(),
				None => return Err(ServerError::DataFormatError("Missing or invalid 'id'".to_string())),
			};
			let task = match headers["task"].as_str() {
				Some(task) => task.to_string(),
				None => return Err(ServerError::DataFormatError("Missing or invalid 'task'".to_string())),
			};
			// タスクを作成
      let task = Task {
        id,
        task,
        args,
      };
      tasks.push(task);
    }

    Ok(tasks)
  }
}


#[cfg(test)]
mod tests {
  use super::*;
	use deadpool_redis::{Config, Runtime};

  #[tokio::test]
  async fn test_find_all_tasks() {
		// Redis接続
		let redis_url = std::env::var("REDIS_URL").expect("REDIS_URL must be set");
		println!("Redis URL: {}", redis_url);
		let cfg = Config::from_url(redis_url);
		let pool = cfg.create_pool(Some(Runtime::Tokio1)).unwrap();
		println!("Pool created");
		let task_repository = TaskRepository::new(pool);
		// タスクの取得
		let tasks = task_repository.find_all_tasks().await.unwrap();
    println!("Tasks: {:?}", tasks);
  }
}