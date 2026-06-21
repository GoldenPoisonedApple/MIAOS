use mimalloc::MiMalloc;
use std::net::SocketAddr;
use std::sync::Arc;
use tokio::net::TcpListener;
use tower_http::trace::TraceLayer;

use server::config::app::AppConfig;
use server::infrastructure::{
  establish_celery_app, establish_db_connection, establish_redis_connection,
  establish_storage_client,
};
use server::repositories::experiment::ExperimentRepository;
use server::repositories::storage::StorageRepository;
use server::repositories::task::TaskRepository;
use server::routes::app_routes;
use server::services::experiment::ExperimentService;
use server::services::file::StorageService;
use server::services::filter::FilterService;
use server::state::{AppState, HealthState};

// メモリ管理最適化
#[global_allocator]
static GLOBAL: MiMalloc = MiMalloc;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
  // アプリ設定読み込み
  let config = AppConfig::from_env().map_err(|e| -> Box<dyn std::error::Error> {
    tracing::error!("Failed to load application configuration: {}", e);
    Box::new(e)
  })?;

  // ロガー
  let log_level = config.log_level.clone();
  tracing_subscriber::fmt()
    .with_env_filter(tracing_subscriber::EnvFilter::new(log_level))
    .init();
  tracing::info!("Starting server...");

  // DB
  let db_pool = establish_db_connection(&config).await?;
  // Redis
  let redis_pool = establish_redis_connection(&config).await?;
  let celery_app = establish_celery_app(&config).await?;
  // MINIO
  let client = establish_storage_client(&config).await;
  let bucket_name = config.minio_bucket_name.clone();

  // migrate適用
  tracing::info!("Running database migrations...");
  sqlx::migrate!("./migrations")
    .run(db_pool.get_postgres_connection_pool()) // プールの参照取得
    .await?;
  tracing::info!("Migrations completed.");

  // 状態
  let health_state = HealthState {
    db_pool: db_pool.clone(),
    redis_pool: redis_pool.clone(),
    client: client.clone(),
    bucket_name: bucket_name.clone(),
  };
  let storage_repository = StorageRepository::new(client.clone(), bucket_name.clone());
  let app_state = AppState {
    experiment_service: Arc::new(ExperimentService::new(
      ExperimentRepository::new(db_pool),
      TaskRepository::new(redis_pool, celery_app),
    )),
    storage_service: Arc::new(StorageService::new(storage_repository.clone())),
    filter_service: Arc::new(FilterService::new(storage_repository)),
  };

  // ルーティング
  let app = app_routes(app_state, health_state).layer(TraceLayer::new_for_http()); // リクエストのトレースを有効化

  // サーバ起動
  let addr = SocketAddr::from(([0, 0, 0, 0], config.server_port));
  let listener = TcpListener::bind(addr).await?;
  axum::serve(listener, app).await?;

  Ok(())
}
