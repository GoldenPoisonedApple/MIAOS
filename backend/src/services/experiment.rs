use crate::dto::experiment::CreateExperimentRequest;
use crate::entities::experiment::Model;
use crate::dto::task::CreateTaskRequest;
use crate::repositories::experiment::ExperimentRepositoryTrait;
use crate::repositories::task::TaskRepositoryTrait;
use crate::error::ServerError;

/// ビジネスロジックを担当するサービス
pub struct ExperimentService<E: ExperimentRepositoryTrait, T: TaskRepositoryTrait> {
	experiment_repository: E,
	task_repository: T,
}

impl<E: ExperimentRepositoryTrait, T: TaskRepositoryTrait> ExperimentService<E, T> {
	pub fn new(experiment_repository: E, task_repository: T) -> Self {
		Self { experiment_repository, task_repository }
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
	use crate::repositories::experiment::ExperimentRepository;
	use crate::repositories::task::TaskRepository;
	use crate::infrastructure::{establish_db_connection, establish_redis_connection, establish_celery_app};


	/// テストの前処理
	async fn setup() -> ExperimentService<ExperimentRepository, TaskRepository> {
		// 実験リポジトリ
		let conn = establish_db_connection().await;
		let experiment_repository = ExperimentRepository::new(conn);
    // タスクリポジトリ
    let pool = establish_redis_connection().await;
    let celery_app = establish_celery_app().await;
		let task_repository = TaskRepository::new(pool, celery_app);

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

}