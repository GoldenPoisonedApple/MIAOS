use tokio::net::TcpListener;
use std::sync::Arc;
use axum::Router;
use std::net::SocketAddr;

use server::infrastructure::{establish_db_connection, establish_redis_connection, establish_celery_app};
use server::repositories::experiment::ExperimentRepository;
use server::repositories::task::TaskRepository;
use server::services::experiment::ExperimentService;
use server::state::AppState;
use server::routes::experiment::app_routes;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
	// インフラの初期化
	let conn = establish_db_connection().await;
  let pool = establish_redis_connection().await;
  let celery_app = establish_celery_app().await;
	// リポジトリ組み立て
  let experiment_repository = ExperimentRepository::new(conn);
  let task_repository = TaskRepository::new(pool, celery_app);
	// サービス組み立て
  let service = Arc::new(ExperimentService::new(
    experiment_repository,
    task_repository,
  ));

	// 状態
	let state = AppState {
		experiment_service: service,
	};

	// ルーティング /api 以下のルーティングを設定
	let app = Router::new()
		.nest("/api", app_routes(state));

  // サーバ起動
	const SERVER_PORT: u16 = 3000;
  let addr = SocketAddr::from(([0, 0, 0, 0], SERVER_PORT));
  let listener = TcpListener::bind(addr).await.unwrap();
  axum::serve(listener, app).await.unwrap();

  Ok(())
}
