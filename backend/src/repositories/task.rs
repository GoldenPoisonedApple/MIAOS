use async_trait::async_trait;
use base64::{engine::general_purpose, Engine as _};
use deadpool_redis::Pool;
use redis::{AsyncCommands, RedisError};
use serde_json::Value;

use crate::dto::task::CreateTaskRequest;
use crate::entities::task::Task;

#[async_trait]
pub trait TaskRepositoryTrait: Send + Sync {
  async fn create_task(&self, request: CreateTaskRequest) -> Result<(), RedisError>;
  async fn find_all_tasks(&self) -> Result<Vec<Task>, RedisError>;
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
  fn decode_body(body: &str) -> Value {
    let decoded = general_purpose::STANDARD.decode(body).unwrap();
    let json = String::from_utf8(decoded).unwrap();
    serde_json::from_str(&json).unwrap()
  }
}

/// TaskRepositoryの実装
#[async_trait]
impl TaskRepositoryTrait for TaskRepository {
  /// タスクの作成
  async fn create_task(&self, request: CreateTaskRequest) -> Result<(), RedisError> {
    let task = Task::from(request);
    let mut conn = self
      .pool
      .get()
      .await
      .map_err(|e| RedisError::from((redis::ErrorKind::Io, "Pool error", e.to_string())))?;
    let serialized = serde_json::to_string(&task).unwrap();
    conn.set(task.id, serialized).await?;
    Ok(())
  }

  /// すべてのタスクを取得
  async fn find_all_tasks(&self) -> Result<Vec<Task>, RedisError> {
    let mut conn = self
      .pool
      .get()
      .await
      .map_err(|e| RedisError::from((redis::ErrorKind::Io, "Pool error", e.to_string())))?;

    let results: Vec<String> = conn.lrange("celery", 0, -1).await?;

    let mut tasks: Vec<Task> = Vec::new();
    for result in results {
      let json: Value = serde_json::from_str(&result).unwrap();
      let body = json["body"].as_str().unwrap();
      let args: Value = Self::decode_body(body);
      let id = json["id"].as_str().unwrap();
      let task = Task {
        id: id.to_string(),
        task: args["task"].as_str().unwrap().to_string(),
        args,
      };
      tasks.push(task);
    }

    Ok(tasks)
  }
}
