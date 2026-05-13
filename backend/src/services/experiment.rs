use crate::dto::experiment::{CreateExperimentRequest, UpdateResultsRequest};
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
  pub async fn create_experiment(&self, request: CreateExperimentRequest) -> Result<Model, ServerError> {
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
					tracing::error!("Failed to rollback experiment {}: {}", result.id, rollback_err);
				}
				Err(e)
			}
		}
  }

	/// 実験の結果反映
	/// * request: UpdateResultsRequest - 実験の結果更新リクエスト
	/// * 戻り値: Result<Model, ServerError> - 実験の結果更新結果
	pub async fn reflect_experiment_results(&self, request: UpdateResultsRequest) -> Result<Model, ServerError> {
		// 更新対象取得
		let mut model = self.experiment_repository.find_by_id(request.experiment_id).await?;
		// 結果反映
		model.complete(request, OffsetDateTime::now_utc());
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

	/// 指定IDの実験を削除
	/// * id: i64 - 削除する実験のID
	/// * 戻り値: Result<u64, ServerError> - 実験の削除結果
	pub async fn delete_experiment_by_id(&self, id: i64) -> Result<u64, ServerError> {
		self.experiment_repository.delete_from_id(id).await
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
  use crate::infrastructure::{
    establish_celery_app, establish_db_connection, establish_redis_connection,
  };
  use crate::test_utils::{remove_test_experiments, remove_test_tasks};
  use crate::repositories::experiment::ExperimentRepository;
  use crate::repositories::task::TaskRepository;
  use crate::entities::experiment::ExperimentStatus;


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
	async fn setup_with_mock_task_repository() -> ExperimentService<ExperimentRepository, MockTaskRepository> {
    // 実験リポジトリ
    let conn = establish_db_connection().await;
    let experiment_repository = ExperimentRepository::new(conn.clone());
		// タスクリポジトリ
		let task_repository = MockTaskRepository::new();

		// テストデータの削除
		remove_test_experiments(&experiment_repository).await;

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

	/// requestファクトリー
	fn update_request(experiment_id: i64) -> UpdateResultsRequest {
		let request = UpdateResultsRequest {
			experiment_id: experiment_id,
			worker_name: "test_worker".to_string(),
			global_auc: 0.5,
			tpr_at_1_fpr: 0.5,
			tpr_at_01_fpr: 0.5,
			other_metrics: serde_json::json!({}),
			total_time: 10.0,
			dataset_json_path: "test_dataset_json_path".to_string(),
			execution_log_path: "test_execution_log_path".to_string(),
			other_files: serde_json::json!({}),
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
    let result = service.create_experiment(request).await.unwrap();
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

	/// 実験の作成: 失敗時のロールバック
	#[tokio::test]
	async fn create_should_rollback_on_task_creation_failure() {
		// Arrange
		let service = setup_with_mock_task_repository().await;
		let request = create_request("test_experiment");
		// Act
		let result = service.create_experiment(request.clone()).await;
		// Assert
		assert!(result.is_err()); // エラー時
		let experiments = service.experiment_repository.find_all().await.unwrap();
		assert!(!experiments.iter().any(|experiment| experiment.name == request.name)); // リクエストの実験が存在しない事
		remove_test_experiments(&service.experiment_repository).await;
	}

	/// 実験の結果反映テスト
	#[tokio::test]
	async fn test_reflect_experiment_results() {
		// Arrange
		let service = setup().await;
		let experiment = service.experiment_repository.create(create_request("test_experiment")).await.unwrap(); // 実験を作成
		let request = update_request(experiment.id);
		// Act
		let result = service.reflect_experiment_results(request).await.unwrap();
		// Assert
		assert_eq!(result.name, "test_experiment"); // 実験名が一致する事
		assert_eq!(result.status, ExperimentStatus::Succeeded); // ステータスがSUCCEEDEDである事
		assert!(result.completed_at.is_some()); // 完了時刻がセットされている事
		assert_eq!(result.worker_name, Some("test_worker".to_string())); // パラメータが更新されていること
		remove_test_experiments(&service.experiment_repository).await;
	}
}
