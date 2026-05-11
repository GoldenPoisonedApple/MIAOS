use sea_orm::{ConnectOptions, Database, DatabaseConnection};
use std::time::Duration;
use deadpool_redis::{Config, Runtime, Pool};
use crate::dto::task::CreateTaskRequest;
use std::sync::Arc;

const MAX_CONNECTIONS: u32 = 5;

/// DB接続を確立する
/// * 戻り値: DatabaseConnection - DB接続
pub async fn establish_db_connection() -> DatabaseConnection {
	// URL取得
  let database_url = std::env::var("DATABASE_URL").expect("DATABASE_URL must be set");
	// 接続設定
  let mut connect_options = ConnectOptions::new(database_url);
  connect_options
    .max_connections(MAX_CONNECTIONS)
    .min_connections(1)
    .acquire_timeout(Duration::from_secs(10))
    .connect_timeout(Duration::from_secs(10))
    .idle_timeout(Duration::from_secs(10))
    .max_lifetime(Duration::from_secs(10))
    .sqlx_logging(true); // 実行されたSQLのログ出力
	// 接続確立
  let pool = Database::connect(connect_options).await.unwrap();
  tracing::info!("Connected to database via SeaORM");
  pool
}

/// Redis接続を確立する
/// * 戻り値: Pool - Redis接続
pub async fn establish_redis_connection() -> Pool {
	// URL取得
	let redis_url = std::env::var("REDIS_URL").expect("REDIS_URL must be set");
	// 接続設定
	let cfg = Config::from_url(&redis_url);
	let pool = cfg.create_pool(Some(Runtime::Tokio1)).unwrap();
	tracing::info!("Connected to Redis via Deadpool");
	pool
}

/// 追加するタスク
#[celery::task(name = "mia_tasks.run_attack")]
pub async fn run_attack(_params: CreateTaskRequest) {}

/// Celeryアプリを初期化する
/// * 戻り値: Arc<celery::Celery> - Celeryアプリ
pub async fn establish_celery_app() -> Arc<celery::Celery> {
	// URL取得
	let redis_url = std::env::var("REDIS_URL").expect("REDIS_URL must be set");
	// アプリの初期化
	let celery_app = celery::app!(
		broker = RedisBroker { redis_url },
		tasks = [run_attack],
		task_routes = []
	)
	.await
	.unwrap();
	tracing::info!("Celery App created successfully");
	celery_app
}
