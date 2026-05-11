use axum::{
  routing::{get, post, delete, put},
  Router,
};
use crate::state::AppState;

use crate::handlers::experiment::{
  create_experiment,
	delete_experiment, delete_task,
	get_all_experiments,
	get_all_tasks,
  reflect_experiment_results,
};


/// ルーティング
pub fn app_routes(state: AppState) -> Router {

  Router::new()
    .route(
      "/experiments",
      get(get_all_experiments).post(create_experiment).put(reflect_experiment_results),
    )
    .route(
      "/experiments/:id",
      delete(delete_experiment),
    )
    .route(
      "/tasks",
      get(get_all_tasks).delete(delete_task),
    )
    .route(
      "/tasks/:id",
      delete(delete_task),
    )
    .with_state(state.experiment_service)
}
