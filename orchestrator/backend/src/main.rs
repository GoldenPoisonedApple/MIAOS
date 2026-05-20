use std::net::SocketAddr;
use std::sync::Arc;
use tokio::net::TcpListener;
use tower_http::trace::TraceLayer;

use server::infrastructure::{
  establish_celery_app, establish_db_connection, establish_redis_connection,
  establish_storage_client, get_bucket_name,
};
use server::repositories::experiment::ExperimentRepository;
use server::repositories::storage::StorageRepository;
use server::repositories::task::TaskRepository;
use server::routes::app_routes;
use server::services::experiment::ExperimentService;
use server::services::file::StorageService;
use server::state::AppState;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
  // ロガー
  tracing_subscriber::fmt()
    .with_max_level(tracing::Level::DEBUG)
    .init();
  tracing::info!("Starting server...");

  // DB
  let db_pool = establish_db_connection().await;
  // migrate適用
  tracing::info!("Running database migrations...");
  sqlx::migrate!("./migrations")
    .run(db_pool.get_postgres_connection_pool()) // プールの参照取得
    .await
    .unwrap();
  tracing::info!("Migrations completed.");
  let experiment_repository = ExperimentRepository::new(db_pool);
  // Redis
  let redis_pool = establish_redis_connection().await;
  let celery_app = establish_celery_app().await;
  let task_repository = TaskRepository::new(redis_pool, celery_app);
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
    experiment_service,
    storage_service,
  };

  // ルーティング
  let app = app_routes(state).layer(TraceLayer::new_for_http()); // リクエストのトレースを有効化

  // サーバ起動
  const SERVER_PORT: u16 = 3000;
  let addr = SocketAddr::from(([0, 0, 0, 0], SERVER_PORT));
  let listener = TcpListener::bind(addr).await.unwrap();
  axum::serve(listener, app).await.unwrap();

  Ok(())
}
