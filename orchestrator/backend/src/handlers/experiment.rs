use axum::{extract::Path, extract::State, Json};
use std::sync::Arc;
use uuid::Uuid;

use crate::dto::experiment::UpdateResultsRequest;
use crate::dto::experiment::{ClaimExperimentRequest, CreateExperimentRequest};
use crate::entities::experiment::Model;
use crate::entities::task::Task;
use crate::error::ServerError;
use crate::repositories::experiment::ExperimentRepository;
use crate::repositories::task::TaskRepository;
use crate::services::experiment::ExperimentService;

/// 実験の作成
#[utoipa::path(
	post,
	path = "/api/experiments",
	request_body = CreateExperimentRequest,
	responses(
		(status = 200, description = "実験が正常に作成された", body = Model),
		(status = 500, description = "サーバー内部エラー")
	),
	tag = "Experiments"
)]
pub async fn create_experiment(
  State(service): State<Arc<ExperimentService<ExperimentRepository, TaskRepository>>>,
  Json(request): Json<CreateExperimentRequest>,
) -> Result<Json<Model>, ServerError> {
  let experiment = service.create_experiment(request).await?;
  Ok(Json(experiment))
}

/// 実験の結果反映
// ちゃんとidは外部に出してあげた方が内部の処理が綺麗になると思う
#[utoipa::path(
	put,
	path = "/api/experiments",
	request_body = UpdateResultsRequest,
	responses(
		(status = 200, description = "実験結果が正常に反映された", body = Model),
		(status = 404, description = "指定された実験が見つからない"),
		(status = 500, description = "サーバー内部エラー")
	),
	tag = "Experiments"
)]
pub async fn reflect_experiment_results(
  State(service): State<Arc<ExperimentService<ExperimentRepository, TaskRepository>>>,
  Json(request): Json<UpdateResultsRequest>,
) -> Result<Json<Model>, ServerError> {
  let experiment = service.reflect_experiment_results(request).await?;
  Ok(Json(experiment))
}

/// 処理取得の報告
// ちゃんとidは外部に出してあげた方が内部の処理が綺麗になると思う
#[utoipa::path(
	put,
	path = "/api/experiments/claim",
	request_body = ClaimExperimentRequest,
	responses(
		(status = 200, description = "処理取得が正常に報告された", body = Model),
		(status = 404, description = "指定された実験が見つからない"),
		(status = 500, description = "サーバー内部エラー")
	),
	tag = "Experiments"
)]
pub async fn claim_experiment(
  State(service): State<Arc<ExperimentService<ExperimentRepository, TaskRepository>>>,
  Json(request): Json<ClaimExperimentRequest>,
) -> Result<Json<Model>, ServerError> {
  let experiment = service.claim_experiment(request).await?;
  Ok(Json(experiment))
}

/// 実験の一覧取得
#[utoipa::path(
	get,
	path = "/api/experiments",
	responses(
		(status = 200, description = "実験の一覧を取得", body = [Model]),
		(status = 500, description = "サーバー内部エラー")
	),
	tag = "Experiments"
)]
pub async fn get_all_experiments(
  State(service): State<Arc<ExperimentService<ExperimentRepository, TaskRepository>>>,
) -> Result<Json<Vec<Model>>, ServerError> {
  let experiments = service.get_all_experiments().await?;
  Ok(Json(experiments))
}

/// 実験の削除
/// Path: /experiments/{id} のような指定の場合 idを取ってこれるエクストラクタ
#[utoipa::path(
	delete,
	path = "/api/experiments/{id}",
	params(
		("id" = i64, Path, description = "削除する実験のID")
	),
	responses(
		(status = 200, description = "実験が正常に削除された", body = u64),
		(status = 500, description = "サーバー内部エラー")
	),
	tag = "Experiments"
)]
pub async fn delete_experiment(
  State(service): State<Arc<ExperimentService<ExperimentRepository, TaskRepository>>>,
  Path(id): Path<i64>,
) -> Result<Json<u64>, ServerError> {
  let result = service.delete_experiment_by_id(id).await?;
  Ok(Json(result))
}

/// タスクの一覧取得
#[utoipa::path(
	get,
	path = "/api/tasks",
	responses(
		(status = 200, description = "タスクの一覧を取得", body = [Task]),
		(status = 500, description = "サーバー内部エラー")
	),
	tag = "Tasks"
)]
pub async fn get_all_tasks(
  State(service): State<Arc<ExperimentService<ExperimentRepository, TaskRepository>>>,
) -> Result<Json<Vec<Task>>, ServerError> {
  let tasks = service.get_all_tasks().await?;
  Ok(Json(tasks))
}

/// タスクの削除
#[utoipa::path(
	delete,
	path = "/api/tasks/{id}",
	params(
		("id" = Uuid, Path, description = "削除するタスクのID")
	),
	responses(
		(status = 200, description = "タスクが正常に削除された", body = u64),
		(status = 500, description = "サーバー内部エラー")
	),
	tag = "Tasks"
)]
pub async fn delete_task(
  State(service): State<Arc<ExperimentService<ExperimentRepository, TaskRepository>>>,
  Path(id): Path<Uuid>,
) -> Result<Json<u64>, ServerError> {
  let result = service.delete_task_by_id(id).await?;
  Ok(Json(result))
}
