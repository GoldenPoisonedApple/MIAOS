use crate::dto::task::CreateTaskRequest;
use crate::error::ServerError;
use aws_sdk_s3::config::{BehaviorVersion, Credentials, Region};
use aws_sdk_s3::Client;
use deadpool_redis::{Config, Pool, Runtime};
use sea_orm::{ConnectOptions, Database, DatabaseConnection};
use std::sync::Arc;
use std::time::Duration;

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

/// MINIO接続を確立する
/// * 戻り値: Client - MINIO接続
pub async fn establish_storage_client() -> Client {
  let access_key = std::env::var("MINIO_ACCESS_KEY").expect("MINIO_ACCESS_KEY must be set");
  let secret_key = std::env::var("MINIO_SECRET_KEY").expect("MINIO_SECRET_KEY must be set");
  let endpoint = std::env::var("MINIO_ENDPOINT").expect("MINIO_ENDPOINT must be set");
  let region = std::env::var("MINIO_REGION").unwrap_or_else(|_| "us-east-1".to_string()); // MINIOではregionが必須ではないので

  let credentials = Credentials::new(
    access_key, secret_key,
    None, // session_token: 一時認証トークン。MinIOでは通常不要
    None, // expiry: 認証情報の有効期限
    "minio",
  );

  let sdk_config = aws_sdk_s3::config::Builder::new()
    .behavior_version(BehaviorVersion::v2026_01_12()) // latest()は良くないっぽいので固定
    .endpoint_url(endpoint)
    .region(Region::new(region))
    .credentials_provider(credentials)
    // MinIOはpath-styleアクセスが必要 (virtual-hosted-styleは使えない)
    .force_path_style(true)
    .build();

  Client::from_conf(sdk_config)
}

/// Bucketの名前取得
/// * 戻り値: String - Bucketの名前
pub fn get_bucket_name() -> String {
  std::env::var("MINIO_BUCKET_NAME").expect("MINIO_BUCKET_NAME must be set")
}

/// DBヘルスチェック
pub async fn ping_database(db: &DatabaseConnection) -> Result<(), ServerError> {
  db.ping().await?;
  Ok(())
}
/// Redisヘルスチェック
pub async fn ping_redis(pool: &Pool) -> Result<(), ServerError> {
  let _ = pool
    .get()
    .await
    .map_err(|e| ServerError::PoolError(e.to_string()))?;
  Ok(())
}
/// Storageヘルスチェック
pub async fn ping_storage(client: &Client, bucket: &str) -> Result<(), ServerError> {
  let _ = client
    .head_bucket()
    .bucket(bucket)
    .send()
    .await
    .map_err(|e| ServerError::S3Error(format!("S3 error: {e}")))?;
  Ok(())
}
