use axum::{
  routing::{delete, get, put},
  Router,
};
use utoipa::OpenApi;
use utoipa_swagger_ui::SwaggerUi;

use crate::state::{AppState, HealthState};

use crate::handlers::experiment::{
  claim_experiment, create_experiment, delete_experiment, delete_task, get_all_experiments,
  get_all_tasks, reflect_experiment_results,
};
use crate::handlers::file::get_file;
use crate::handlers::filter::{delete_filter, list_filters, upload_filter};
use crate::handlers::health::{liveness, readiness};

#[derive(OpenApi)]
#[openapi(
	paths(
		crate::handlers::experiment::create_experiment,
		crate::handlers::experiment::get_all_experiments,
		crate::handlers::experiment::delete_experiment,
		crate::handlers::experiment::reflect_experiment_results,
		crate::handlers::experiment::get_all_tasks,
		crate::handlers::experiment::delete_task,
		crate::handlers::experiment::claim_experiment,
		crate::handlers::file::get_file,
		crate::handlers::filter::list_filters,
		crate::handlers::filter::upload_filter,
		crate::handlers::filter::delete_filter,
	),
	components(
		schemas(
			crate::dto::experiment::CreateExperimentRequest,
			crate::dto::experiment::UpdateResultsRequest,
			crate::dto::experiment::ClaimExperimentRequest,
			crate::dto::watermark::WatermarkConfig,
			crate::dto::filter::FilterSummary,
			crate::dto::filter::FilterListResponse,
			crate::entities::experiment::Model,
			crate::entities::experiment::ExperimentStatus,
			crate::entities::experiment::MiaMethod,
			crate::entities::task::Task,
		)
	),
	tags(
		(name = "Experiments", description = "実験管理API"),
		(name = "Tasks", description = "タスク管理API"),
		(name = "Files", description = "ファイル管理API"),
		(name = "Filters", description = "フィルタ画像管理API")
	)
)]
pub struct ApiDoc; // utoipaで生成されたOpenAPIドキュメントを保持する構造体

const SWAGGER_UI_PATH: &str = "/docs";
const OPENAPI_JSON_PATH: &str = "/api/openapi.json";

/// ルーティング
pub fn app_routes(app_state: AppState, health_state: HealthState) -> Router {
  let api_router = Router::new()
    .route(
      "/api/experiments",
      get(get_all_experiments)
        .post(create_experiment)
        .put(reflect_experiment_results),
    )
    .route("/api/experiments/claim", put(claim_experiment))
    .route("/api/experiments/{id}", delete(delete_experiment))
    .route("/api/tasks", get(get_all_tasks))
    .route("/api/tasks/{id}", delete(delete_task))
    // {*key}は任意のパスを受け取れる test/sample.logなど / を含めることができる
    // 今回はkeyをURLエンコードしているため * である必要はない
    //一部プロキシは%2Fですら特別扱いするためちゃんとやるならクエリとかが良い
    .route("/api/files/{key}", get(get_file))
    .route("/api/filters", get(list_filters))
    .route(
      "/api/filters/{id}",
      delete(delete_filter).post(upload_filter),
    )
    .with_state(app_state);

  let health_router = Router::new()
    .route("/health/live", get(liveness))
    .route("/health/ready", get(readiness))
    .with_state(health_state);

  Router::new()
    .merge(health_router)
    .merge(SwaggerUi::new(SWAGGER_UI_PATH).url(OPENAPI_JSON_PATH, ApiDoc::openapi())) // ドキュメント生成用
    .merge(api_router) // 実際のAPIルーティング mergeによりドキュメント生成用と実際のAPIルーティングを結合
}
