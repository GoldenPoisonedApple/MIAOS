use crate::error::ServerError;
use async_trait::async_trait;
use base64::{engine::general_purpose, Engine as _};
use deadpool_redis::Pool;
use redis::AsyncCommands;
use serde_json::Value;
use uuid::Uuid;

use crate::dto::task::CreateTaskRequest;
use crate::entities::task::Task;
use crate::infrastructure::run_attack;

#[async_trait]
pub trait TaskRepositoryTrait: Send + Sync {
  async fn create_task(&self, request: CreateTaskRequest) -> Result<Uuid, ServerError>;
  async fn find_all_tasks(&self) -> Result<Vec<Task>, ServerError>;
  async fn delete_by_id(&self, id: Uuid) -> Result<u64, ServerError>;
}

#[derive(Clone)]
pub struct TaskRepository {
  pool: Pool,                                 // Redis接続
  celery_app: std::sync::Arc<celery::Celery>, // create_task のエンキュー用
}

impl TaskRepository {
  /// コンストラクタ
  pub fn new(pool: Pool, celery_app: std::sync::Arc<celery::Celery>) -> Self {
    Self { pool, celery_app }
  }

  /// ボディをデコード
  fn decode_body(body: &str) -> Result<Value, ServerError> {
    let decoded = general_purpose::STANDARD.decode(body)?;
    let json = String::from_utf8(decoded)?;
    let parsed = serde_json::from_str(&json)?;

    Ok(parsed)
  }

  /// 取得文字列をパースしてTaskに変換
  fn parse_task(result: String) -> Result<Task, ServerError> {
    let json: Value = serde_json::from_str(&result)?; // Jsonに変換
    let body = match json["body"].as_str() {
      Some(body) => body,
      None => {
        return Err(ServerError::DataFormatError(
          "Missing or invalid 'body'".to_string(),
        ))
      }
    };

    // idとtaskを取得
    let headers = &json["headers"];
    let id = match headers["id"].as_str() {
      Some(id) => Uuid::parse_str(id)?,
      None => {
        return Err(ServerError::DataFormatError(
          "Missing or invalid 'id'".to_string(),
        ))
      }
    };
    let task = match headers["task"].as_str() {
      Some(task) => task.to_string(),
      None => {
        return Err(ServerError::DataFormatError(
          "Missing or invalid 'task'".to_string(),
        ))
      }
    };
    // ボディをデコード
    let args: Value = Self::decode_body(body)?;
    let (positional, params, control) = match args.as_array().map(|array| array.as_slice()) {
      Some([p0, p1, p2]) => (p0, p1, p2),
      _ => {
        return Err(ServerError::DataFormatError(
          "invalid Celery args format".to_string(),
        ))
      }
    };
    // 実験IDを取得
    let experiment_id = match params["_params"]["experiment_id"].as_i64() {
      Some(experiment_id) => experiment_id,
      None => {
        return Err(ServerError::DataFormatError(
          "Missing or invalid 'experiment_id'".to_string(),
        ))
      }
    };
    // タスクを作成
    let task_entity = Task {
      id,
      task,
      experiment_id,
      args_positional: positional.clone(),
      args_keyword: params.clone(),
      args_control: control.clone(),
    };
    Ok(task_entity)
  }
}

/// TaskRepositoryの実装
#[async_trait]
impl TaskRepositoryTrait for TaskRepository {
  /// タスクを作成（Celery経由でエンキュー）
  /// * request: CreateTaskRequest - 作成するタスクのリクエスト
  /// * 戻り値: Result<Uuid, ServerError> - タスクのUUID
  async fn create_task(&self, request: CreateTaskRequest) -> Result<Uuid, ServerError> {
    let result = self.celery_app.send_task(run_attack::new(request)).await?;
    let id = Uuid::parse_str(&result.task_id)?;
    Ok(id)
  }

  /// すべてのタスクを取得
  /// * 戻り値: Result<Vec<Task>, ServerError> - タスクの一覧取得結果
  async fn find_all_tasks(&self) -> Result<Vec<Task>, ServerError> {
    // Redis接続 複雑なエラーを返すため、Stringとして返す
    let mut conn = self
      .pool
      .get()
      .await
      .map_err(|e| ServerError::PoolError(e.to_string()))?;
    // タスクの取得
    let results: Vec<String> = conn.lrange("celery", 0, -1).await?;

    // タスクの解析 取得
    let mut tasks: Vec<Task> = Vec::new();
    for result in results {
      match Self::parse_task(result) {
        // タスクの解析に成功: タスクを追加
        Ok(task_entity) => tasks.push(task_entity),
        // タスクの解析に失敗: エラータスクとして追加
        Err(e) => {
          tracing::error!("Failed to parse task: {}", e);
          let error_task = Task {
            id: Uuid::nil(),
            task: "error".to_string(),
            experiment_id: 0,
            args_positional: serde_json::Value::Null,
            args_keyword: serde_json::Value::Null,
            args_control: serde_json::Value::Null,
          };
          tasks.push(error_task);
        }
      }
    }

    Ok(tasks)
  }

  /// 指定されたIDのタスクを削除
  /// * id: Uuid - 削除するタスクのID
  /// * 戻り値: Result<u64, ServerError> - 削除されたタスクの件数
  async fn delete_by_id(&self, id: Uuid) -> Result<u64, ServerError> {
    let mut conn = self
      .pool
      .get()
      .await
      .map_err(|e| ServerError::PoolError(e.to_string()))?;
    // タスクの取得
    let results: Vec<String> = conn.lrange("celery", 0, -1).await?;
    let mut total_deleted = 0;
    for result in results {
      let json: Value = serde_json::from_str(&result)?;
      let headers = &json["headers"];
      let task_id = match headers["id"].as_str() {
        Some(task_id) => task_id.to_string(),
        None => continue,
      };
      if task_id == id.to_string() {
        // タスクの削除 完全一致のみ削除可能
        let lrem_result: u64 = conn.lrem("celery", 0, result).await?;
        if lrem_result == 0 {
          return Err(ServerError::NotFound(format!(
            "Task with id {} not found",
            id
          )));
        }
        total_deleted += lrem_result;
      }
    }

    Ok(total_deleted)
  }
}

#[cfg(all(test, feature = "integration-test"))]
mod tests {
  use super::*;
  use crate::config::app::AppConfig;
  use crate::entities::experiment::MiaMethod;
  use crate::infrastructure::{establish_celery_app, establish_redis_connection};
  use crate::test_utils::{init_test_logger, remove_test_tasks};

  /// テストの前処理
  async fn setup() -> TaskRepository {
    // Redis接続
    let config = AppConfig::test_defaults().unwrap();
    let pool = establish_redis_connection(&config).await.unwrap();
    // Celeryアプリの初期化
    let celery_app = establish_celery_app(&config).await.unwrap();
    // リポジトリ作成
    let task_repository = TaskRepository::new(pool, celery_app);

    // テストデータの削除
    remove_test_tasks(&task_repository).await;

    task_repository
  }

  /// taskファクトリー
  fn create_request(notes: &str) -> CreateTaskRequest {
    CreateTaskRequest {
      experiment_id: 1,
      name: "test".to_string(),
      notes: Some(notes.to_string()),
      method: MiaMethod::OfflineLira,
      batch_size: 10,
      max_epochs: 10,
      num_shadow_models: 10,
      target_train_size: 10,
      target_test_size: 10,
      shadow_train_size: 10,
      shadow_test_size: 10,
      seed: 10,
      hyperparameters: serde_json::json!({}),
      watermark: serde_json::json!({}),
      base_experiment_id: None,
      load_target_model: false,
      load_shadow_model: false,
      load_attack_model: false,
    }
  }

  /// タスクの一覧取得テスト
  #[tokio::test]
  async fn test_find_all_tasks() {
    init_test_logger();
    // Arrange
    let task_repository = setup().await;
    // Act
    let tasks = task_repository.find_all_tasks().await.unwrap();
    // Assert
    tracing::info!("Tasks: {:?}", tasks);
    remove_test_tasks(&task_repository).await;
  }

  /// タスクの作成テスト
  #[tokio::test]
  async fn test_create_task() {
    // Arrange
    let task_repository = setup().await;
    let request = create_request("backend_test");
    let experiment_id = request.experiment_id;
    let total = task_repository.find_all_tasks().await.unwrap().len();
    // Act
    let id = task_repository.create_task(request).await.unwrap();
    // Assert
    let tasks = task_repository.find_all_tasks().await.unwrap();
    let created_total = tasks.len();
    assert_eq!(created_total, total + 1); // タスクの数が1増えている事
    assert_eq!(tasks[created_total - 1].id, id); // 末尾に追加されている事
    assert_eq!(tasks[created_total - 1].experiment_id, experiment_id); // 実験IDが一致する事
    remove_test_tasks(&task_repository).await;
  }

  /// タスクの削除テスト
  #[tokio::test]
  async fn test_delete_by_id() {
    // Arrange
    let task_repository = setup().await;
    let request = create_request("backend_test");
    let id = task_repository.create_task(request).await.unwrap();
    let total = task_repository.find_all_tasks().await.unwrap().len();
    // Act
    let result = task_repository.delete_by_id(id).await.unwrap();
    // Assert
    assert_eq!(result, 1); // 削除されたタスクの数が1件である事
    let tasks = task_repository.find_all_tasks().await.unwrap();
    let deleted_total = tasks.len();
    assert_eq!(deleted_total, total - 1); // タスクの数が1減っている事
    assert!(!tasks.iter().any(|task| task.id == id)); // 削除されたタスクが存在しない事
    remove_test_tasks(&task_repository).await;
  }
}
