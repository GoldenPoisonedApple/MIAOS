use crate::dto::experiment::{
  ClaimExperimentRequest, CreateExperimentRequest, UpdateResultsRequest,
};
use crate::dto::task::CreateTaskRequest;
use crate::entities::experiment::Model;
use crate::entities::task::Task;
use crate::error::ServerError;
use crate::repositories::experiment::ExperimentRepositoryTrait;
use crate::repositories::task::TaskRepositoryTrait;
use time::OffsetDateTime;
use uuid::Uuid;

/// ビジネスロジックを担当するサービス
pub struct ExperimentService<E: ExperimentRepositoryTrait, T: TaskRepositoryTrait> {
  experiment_repository: E,
  task_repository: T,
}

impl<E: ExperimentRepositoryTrait, T: TaskRepositoryTrait> ExperimentService<E, T> {
  pub fn new(experiment_repository: E, task_repository: T) -> Self {
    Self {
      experiment_repository,
      task_repository,
    }
  }

  /// 実験の作成
  /// * request: CreateExperimentRequest - 実験の作成リクエスト
  /// * 戻り値: Result<Model, sea_orm::DbErr> - 実験の作成結果
  pub async fn create_experiment(
    &self,
    request: CreateExperimentRequest,
  ) -> Result<Model, ServerError> {
    // 実験条件登録
    let result = self.experiment_repository.create(request).await?;
    // タスクリクエスト作成
    let task_request = CreateTaskRequest::from(&result);
    // タスク登録
    match self.task_repository.create_task(task_request).await {
      Ok(_) => Ok(result),
      // ロールバック: タスク登録に失敗した場合は実験を削除
      Err(e) => {
        if let Err(rollback_err) = self.experiment_repository.delete_from_id(result.id).await {
          // 補償すら失敗した場合
          tracing::error!(
            "Failed to rollback experiment {}: {}",
            result.id,
            rollback_err
          );
        }
        Err(e)
      }
    }
  }

  /// 実験の結果反映
  /// * request: UpdateResultsRequest - 実験の結果更新リクエスト
  /// * 戻り値: Result<Model, ServerError> - 実験の結果更新結果
  pub async fn reflect_experiment_results(
    &self,
    request: UpdateResultsRequest,
  ) -> Result<Model, ServerError> {
    // 更新対象取得
    let mut model = self
      .experiment_repository
      .find_by_id(request.experiment_id)
      .await?;
    // 結果反映
    model.complete(request, OffsetDateTime::now_utc())?;
    // 更新
    self.experiment_repository.update(model).await
  }

  /// 処理取得の報告
  /// * request: ClaimExperimentRequest - 処理取得の報告リクエスト
  /// * 戻り値: Result<Model, ServerError> - 処理取得の報告結果
  pub async fn claim_experiment(
    &self,
    request: ClaimExperimentRequest,
  ) -> Result<Model, ServerError> {
    // 更新対象取得
    let mut model = self.experiment_repository.find_by_id(request.id).await?;
    // 処理取得の報告
    model.claim(request)?;
    // 更新
    self.experiment_repository.update(model).await
  }

  /// 実験の一覧取得
  /// * 戻り値: Result<Vec<Model>, ServerError> - 実験の一覧取得結果
  pub async fn get_all_experiments(&self) -> Result<Vec<Model>, ServerError> {
    self.experiment_repository.find_all().await
  }

  /// タスクの一覧取得
  /// * 戻り値: Result<Vec<Task>, ServerError> - タスクの一覧取得結果
  pub async fn get_all_tasks(&self) -> Result<Vec<Task>, ServerError> {
    self.task_repository.find_all_tasks().await
  }

  /// 指定IDの実験を削除 タスクも一緒に削除する
  /// * id: i64 - 削除する実験のID
  /// * 戻り値: Result<u64, ServerError> - 実験の削除結果
  pub async fn delete_experiment_by_id(&self, id: i64) -> Result<u64, ServerError> {
    let result = self.experiment_repository.delete_from_id(id).await?;
    // タスクも削除
    let tasks = self.task_repository.find_all_tasks().await?;
    for task in tasks {
      if task.experiment_id == id {
        self.task_repository.delete_by_id(task.id).await?;
      }
    }
    Ok(result)
  }

  /// 指定IDのタスクを削除
  /// * id: Uuid - 削除するタスクのID
  /// * 戻り値: Result<u64, ServerError> - タスクの削除結果
  pub async fn delete_task_by_id(&self, id: Uuid) -> Result<u64, ServerError> {
    self.task_repository.delete_by_id(id).await
  }
}

#[cfg(test)]
mod tests {
  use super::*;
  use crate::config::app::AppConfig;
  use crate::entities::experiment::ExperimentStatus;
  use crate::infrastructure::{establish_celery_app, establish_redis_connection};
  use crate::repositories::experiment::ExperimentRepository;
  use crate::repositories::task::TaskRepository;
  use crate::test_utils::{
    create_experiment_request_factory, remove_test_tasks, update_experiment_request_factory,
  };
  use sea_orm::SqlxPostgresConnector;

  /// テストの前処理
  async fn setup(pool: sqlx::PgPool) -> ExperimentService<ExperimentRepository, TaskRepository> {
    // 実験リポジトリ
    let db = SqlxPostgresConnector::from_sqlx_postgres_pool(pool);
    let experiment_repository = ExperimentRepository::new(db);
    // タスクリポジトリ
    let config = AppConfig::test_defaults().unwrap();
    let redis_pool = establish_redis_connection(&config).await.unwrap();
    let celery_app = establish_celery_app(&config).await.unwrap();
    let task_repository = TaskRepository::new(redis_pool, celery_app);

    // テストデータの削除
    remove_test_tasks(&task_repository).await;

    // サービスインスタンス作成
    ExperimentService::new(experiment_repository, task_repository)
  }

  /// task_repositoryのモック
  struct MockTaskRepository {}
  impl MockTaskRepository {
    pub fn new() -> Self {
      Self {}
    }
  }
  #[async_trait::async_trait]
  impl TaskRepositoryTrait for MockTaskRepository {
    async fn create_task(&self, _request: CreateTaskRequest) -> Result<Uuid, ServerError> {
      Err(ServerError::Internal(String::from("Failed to create task")))
    }
    async fn find_all_tasks(&self) -> Result<Vec<Task>, ServerError> {
      Ok(vec![])
    }
    async fn delete_by_id(&self, _id: Uuid) -> Result<u64, ServerError> {
      Ok(0)
    }
  }

  /// モックタスクリポジトリを使用したテストの前処理
  async fn setup_with_mock_task_repository(
    pool: sqlx::PgPool,
  ) -> ExperimentService<ExperimentRepository, MockTaskRepository> {
    // 実験リポジトリ
    let db = SqlxPostgresConnector::from_sqlx_postgres_pool(pool);
    let experiment_repository = ExperimentRepository::new(db);
    // タスクリポジトリ
    let task_repository = MockTaskRepository::new();

    // サービスインスタンス作成
    ExperimentService::new(experiment_repository, task_repository)
  }

  /// 実験の作成テスト
  #[sqlx::test]
  async fn test_create(pool: sqlx::PgPool) {
    // Arrange
    let service = setup(pool).await;
    let request = create_experiment_request_factory("test_experiment");
    let experiment_total = service
      .experiment_repository
      .find_all()
      .await
      .unwrap()
      .len();
    let task_total = service
      .task_repository
      .find_all_tasks()
      .await
      .unwrap()
      .len();
    // Act
    let result = service.create_experiment(request).await.unwrap();
    // Assert
    assert_eq!(result.name, "test_experiment"); // 実験名が一致する事
    let experiments = service.experiment_repository.find_all().await.unwrap();
    let tasks = service.task_repository.find_all_tasks().await.unwrap();
    assert_eq!(experiments.len(), experiment_total + 1); // 実験の数が1増えている事
    assert_eq!(tasks.len(), task_total + 1); // タスクの数が1増えている事
    assert_eq!(
      tasks[task_total].args_keyword["_params"]["experiment_id"],
      result.id
    ); // タスクに同じ実験IDが設定されている事
    remove_test_tasks(&service.task_repository).await;
  }

  /// 実験の作成: 失敗時のロールバック
  #[sqlx::test]
  async fn create_should_rollback_on_task_creation_failure(pool: sqlx::PgPool) {
    // Arrange
    let service = setup_with_mock_task_repository(pool).await;
    let request = create_experiment_request_factory("test_experiment");
    // Act
    let result = service.create_experiment(request.clone()).await;
    // Assert
    assert!(result.is_err()); // エラー時
    let experiments = service.experiment_repository.find_all().await.unwrap();
    assert!(!experiments
      .iter()
      .any(|experiment| experiment.name == request.name)); // リクエストの実験が存在しない事
  }

  /// 実験の結果反映テスト
  #[sqlx::test]
  async fn test_reflect_experiment_results(pool: sqlx::PgPool) {
    // Arrange
    let service = setup(pool).await;
    let experiment = service
      .experiment_repository
      .create(create_experiment_request_factory("test_experiment"))
      .await
      .unwrap(); // 実験を作成
    let request = ClaimExperimentRequest {
      id: experiment.id,
      worker_name: "test_worker".to_string(),
    };
    service.claim_experiment(request).await.unwrap(); // 処理取得の報告
    let request = update_experiment_request_factory(experiment.id, ExperimentStatus::Succeeded);
    // Act
    let result = service.reflect_experiment_results(request).await.unwrap();
    // Assert
    assert_eq!(result.name, "test_experiment"); // 実験名が一致する事
    assert_eq!(result.status, ExperimentStatus::Succeeded); // ステータスがセットされていること
    assert!(result.completed_at.is_some()); // 完了時刻がセットされている事
    assert_eq!(result.worker_name, Some("test_worker".to_string())); // ワーカーがセットされていること
  }

  /// 実験の結果反映: FAILED
  #[sqlx::test]
  async fn test_reflect_experiment_results_failed(pool: sqlx::PgPool) {
    // Arrange
    let service = setup(pool).await;
    let experiment = service
      .experiment_repository
      .create(create_experiment_request_factory("test_experiment"))
      .await
      .unwrap(); // 実験を作成
    let request = ClaimExperimentRequest {
      id: experiment.id,
      worker_name: "test_worker".to_string(),
    };
    service.claim_experiment(request).await.unwrap(); // 処理取得の報告
    let mut request = update_experiment_request_factory(experiment.id, ExperimentStatus::Failed);
    request.error_message = Some("test_error".to_string());
    // Act
    let result = service.reflect_experiment_results(request).await.unwrap();
    // Assert
    assert_eq!(result.status, ExperimentStatus::Failed); // 失敗となっていること
    assert_eq!(result.error_message, Some("test_error".to_string())); // エラーメッセージがセットされていること
  }

  /// 処理取得の報告テスト
  #[sqlx::test]
  async fn test_claim_experiment(pool: sqlx::PgPool) {
    // Arrange
    let service = setup(pool).await;
    let experiment = service
      .experiment_repository
      .create(create_experiment_request_factory("test_experiment"))
      .await
      .unwrap(); // 実験を作成
    let request = ClaimExperimentRequest {
      id: experiment.id,
      worker_name: "test_worker".to_string(),
    };
    // Act
    let result = service.claim_experiment(request).await.unwrap();
    // Assert
    assert_eq!(result.status, ExperimentStatus::Running); // ステータスが実行中となっていること
    assert_eq!(result.worker_name, Some("test_worker".to_string())); // ワーカーがセットされていること
  }

  /// 実験の削除テスト
  #[sqlx::test]
  async fn test_delete_experiment_by_id(pool: sqlx::PgPool) {
    // Arrange
    let service = setup(pool).await;
    let created_experiment = service
      .experiment_repository
      .create(create_experiment_request_factory("test_experiment"))
      .await
      .unwrap(); // 実験を作成
                 // Act
    let result = service
      .delete_experiment_by_id(created_experiment.id)
      .await
      .unwrap();
    // Assert
    assert_eq!(result, 1); // 削除された実験の数が1件である事
    let experiments = service.experiment_repository.find_all().await.unwrap();
    assert!(!experiments
      .iter()
      .any(|experiment| experiment.id == created_experiment.id)); // 指定IDの実験が存在しない事
    let tasks = service.task_repository.find_all_tasks().await.unwrap();
    assert!(!tasks
      .iter()
      .any(|task| task.experiment_id == created_experiment.id)); // 指定IDの実験タスクが存在しない事
    remove_test_tasks(&service.task_repository).await;
  }
}
