use axum::{
	extract::State,
	extract::Path,
	Json,
};
use uuid::Uuid;
use std::sync::Arc;

use crate::dto::experiment::CreateExperimentRequest;
use crate::dto::experiment::UpdateResultsRequest;
use crate::entities::experiment::Model;
use crate::entities::task::Task;
use crate::error::ServerError;
use crate::services::experiment::ExperimentService;
use crate::repositories::experiment::ExperimentRepository;
use crate::repositories::task::TaskRepository;

/// 実験の作成
pub async fn create_experiment(
	State(service): State<Arc<ExperimentService<ExperimentRepository, TaskRepository>>>,
	Json(request): Json<CreateExperimentRequest>
) -> Result<Json<Model>, ServerError> {
	let experiment = service.create_experiment(request).await?;
	Ok(Json(experiment))
}

/// 実験の結果反映
pub async fn reflect_experiment_results(
	State(service): State<Arc<ExperimentService<ExperimentRepository, TaskRepository>>>,
	Json(request): Json<UpdateResultsRequest>
) -> Result<Json<Model>, ServerError> {
	let experiment = service.reflect_experiment_results(request).await?;
	Ok(Json(experiment))
}

/// 実験の一覧取得
pub async fn get_all_experiments(
	State(service): State<Arc<ExperimentService<ExperimentRepository, TaskRepository>>>,
) -> Result<Json<Vec<Model>>, ServerError> {
	let experiments = service.get_all_experiments().await?;
	Ok(Json(experiments))
}

/// 実験の削除
/// Path: /experiments/{id} のような指定の場合 idを取ってこれるエクストラクタ
pub async fn delete_experiment(
	State(service): State<Arc<ExperimentService<ExperimentRepository, TaskRepository>>>,
	Path(id): Path<i64>
) -> Result<Json<u64>, ServerError> {
	let result = service.delete_experiment_by_id(id).await?;
	Ok(Json(result))
}

/// タスクの一覧取得
pub async fn get_all_tasks(
	State(service): State<Arc<ExperimentService<ExperimentRepository, TaskRepository>>>,
) -> Result<Json<Vec<Task>>, ServerError> {
	let tasks = service.get_all_tasks().await?;
	Ok(Json(tasks))
}

/// タスクの削除
pub async fn delete_task(
	State(service): State<Arc<ExperimentService<ExperimentRepository, TaskRepository>>>,
	Path(id): Path<Uuid>
) -> Result<Json<u64>, ServerError> {
	let result = service.delete_task_by_id(id).await?;
	Ok(Json(result))
}
