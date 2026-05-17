use tokio::net::TcpListener;
use std::sync::Arc;
use std::net::SocketAddr;

use server::infrastructure::{establish_db_connection, establish_redis_connection, establish_celery_app, establish_storage_client, get_bucket_name};
use server::repositories::experiment::ExperimentRepository;
use server::repositories::storage::StorageRepository;
use server::repositories::task::TaskRepository;
use server::services::experiment::ExperimentService;
use server::services::file::StorageService;
use server::state::AppState;
use server::routes::app_routes;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
	// ロガー
	tracing_subscriber::fmt::init();
	tracing::info!("Starting server...");
	
	// DB
	let pool = establish_db_connection().await;
  let experiment_repository = ExperimentRepository::new(pool);
	// Redis
  let pool = establish_redis_connection().await;
  let celery_app = establish_celery_app().await;
  let task_repository = TaskRepository::new(pool, celery_app);
	// サービス組み立て
  let experiment_service = Arc::new(ExperimentService::new(
    experiment_repository,
    task_repository,
  ));
	// MINIO接続
	let client = establish_storage_client().await;
	let storage_repository = StorageRepository::new(client, get_bucket_name());
	let storage_service = Arc::new(StorageService::new(storage_repository));

	// 状態
	let state = AppState {
		experiment_service: experiment_service,
		storage_service: storage_service,
	};

	// ルーティング
	let app = app_routes(state);

  // サーバ起動
	const SERVER_PORT: u16 = 3000;
  let addr = SocketAddr::from(([0, 0, 0, 0], SERVER_PORT));
  let listener = TcpListener::bind(addr).await.unwrap();
  axum::serve(listener, app).await.unwrap();

  Ok(())
}
