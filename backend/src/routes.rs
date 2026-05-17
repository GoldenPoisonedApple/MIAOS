use axum::{
  routing::{get, delete, put},
  Router,
};
use utoipa::OpenApi;
use utoipa_swagger_ui::SwaggerUi;

use crate::state::AppState;

use crate::handlers::experiment::{
  create_experiment,
	delete_experiment, delete_task,
	get_all_experiments,
	get_all_tasks,
  reflect_experiment_results,
  claim_experiment,
};

use crate::handlers::file::get_file;

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
	),
	components(
		schemas(
			crate::dto::experiment::CreateExperimentRequest,
			crate::dto::experiment::UpdateResultsRequest,
			crate::dto::experiment::ClaimExperimentRequest,
			crate::entities::experiment::Model,
			crate::entities::experiment::ExperimentStatus,
			crate::entities::experiment::MiaMethod,
			crate::entities::task::Task,
		)
	),
	tags(
		(name = "Experiments", description = "実験管理API"),
		(name = "Tasks", description = "タスク管理API"),
		(name = "Files", description = "ファイル管理API")
	)
)]
pub struct ApiDoc; // utoipaで生成されたOpenAPIドキュメントを保持する構造体


const SWAGGER_UI_PATH: &str = "/docs";
const OPENAPI_JSON_PATH: &str = "/api-docs/openapi.json";


/// ルーティング
pub fn app_routes(state: AppState) -> Router {

  let api_router = Router::new()
    .route(
      "/api/experiments",
      get(get_all_experiments).post(create_experiment).put(reflect_experiment_results),
    )
		.route(
			"/api/experiments/claim",
			put(claim_experiment),
		)
    .route(
      "/api/experiments/{id}",
      delete(delete_experiment),
    )
    .route(
      "/api/tasks",
      get(get_all_tasks),
    )
    .route(
      "/api/tasks/{id}",
      delete(delete_task),
    )
		.route(
			// *keyは任意のパスを受け取れる test/sample.logなど / を含めることができる
			// 今回はkeyをURLエンコードしているため * である必要はない
			//一部プロキシは%2Fですら特別扱いするためちゃんとやるならクエリとかが良い
			"/api/files/{*key}",
			get(get_file),
		)
    .with_state(state);

  Router::new()
    .merge(SwaggerUi::new(SWAGGER_UI_PATH).url(OPENAPI_JSON_PATH, ApiDoc::openapi())) // ドキュメント生成用
    .merge(api_router) // 実際のAPIルーティング mergeによりドキュメント生成用と実際のAPIルーティングを結合
}
