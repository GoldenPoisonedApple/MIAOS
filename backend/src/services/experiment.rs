use crate::dto::experiment::CreateExperimentRequest;
use crate::dto::task::CreateTaskRequest;
use crate::entities::experiment::Model;
use crate::error::ServerError;
use crate::repositories::experiment::ExperimentRepositoryTrait;
use crate::repositories::task::TaskRepositoryTrait;

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
  pub async fn create(&self, request: CreateExperimentRequest) -> Result<Model, ServerError> {
    // 実験条件登録
    let result = self.experiment_repository.create(request).await?;
    // タスクリクエスト作成
    let task_request = CreateTaskRequest::from(&result);
    // タスク登録
    self.task_repository.create_task(task_request).await?;
    Ok(result)
  }
}

#[cfg(test)]
mod tests {
  use super::*;
  use crate::infrastructure::{
    establish_celery_app, establish_db_connection, establish_redis_connection,
  };
  use crate::test_utils::{remove_test_experiments, remove_test_tasks};
  use crate::repositories::experiment::ExperimentRepository;
  use crate::repositories::task::TaskRepository;

  /// テストの前処理
  async fn setup() -> ExperimentService<ExperimentRepository, TaskRepository> {
    // 実験リポジトリ
    let conn = establish_db_connection().await;
    let experiment_repository = ExperimentRepository::new(conn.clone());
    // タスクリポジトリ
    let pool = establish_redis_connection().await;
    let celery_app = establish_celery_app().await;
    let task_repository = TaskRepository::new(pool, celery_app);

    // テストデータの削除
    remove_test_experiments(&experiment_repository).await;
    remove_test_tasks(&task_repository).await;

    // サービスインスタンス作成
    let service = ExperimentService::new(experiment_repository, task_repository);

    service
  }

  /// requestファクトリー
  fn create_request(name: &str) -> CreateExperimentRequest {
    let request = CreateExperimentRequest {
      name: name.to_string(),
      notes: Some("backend_test".to_string()),
      ..Default::default()
    };

    request
  }

  /// 実験の作成テスト
  #[tokio::test]
  async fn test_create() {
    // Arrange
    let service = setup().await;
    let request = create_request("test_experiment");
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
    let result = service.create(request).await.unwrap();
    // Assert
    assert_eq!(result.name, "test_experiment"); // 実験名が一致する事
    let experiments = service.experiment_repository.find_all().await.unwrap();
    let tasks = service.task_repository.find_all_tasks().await.unwrap();
    assert_eq!(experiments.len(), experiment_total + 1); // 実験の数が1増えている事
    assert_eq!(tasks.len(), task_total + 1); // タスクの数が1増えている事
    assert_eq!(tasks[task_total].args_keyword["_params"]["experiment_id"], result.id); // タスクに同じ実験IDが設定されている事
		remove_test_experiments(&service.experiment_repository).await;
		remove_test_tasks(&service.task_repository).await;
  }
}
