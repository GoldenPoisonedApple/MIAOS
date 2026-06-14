use crate::config::app::AppConfig;
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
pub async fn establish_db_connection(
  config: &AppConfig,
) -> Result<DatabaseConnection, ServerError> {
  // URL取得
  let database_url = config.database_url.clone();
  // 接続設定
  let mut connect_options = ConnectOptions::new(database_url);
  connect_options
    .max_connections(MAX_CONNECTIONS)
    .min_connections(1)
    .acquire_timeout(Duration::from_secs(10)) // 接続取得時のタイムアウト
    .connect_timeout(Duration::from_secs(10)) // 接続時のタイムアウト
    .idle_timeout(Duration::from_secs(30 * 60)) // 接続保持時のタイムアウト
    .max_lifetime(Duration::from_secs(60 * 60)) // 接続保持時の最大生存期間
    .sqlx_logging(true); // 実行されたSQLのログ出力
                         // 接続確立
  let pool = Database::connect(connect_options).await?;
  tracing::info!("Connected to database via SeaORM");
  Ok(pool)
}

/// Redis接続を確立する
/// * 戻り値: Pool - Redis接続
pub async fn establish_redis_connection(config: &AppConfig) -> Result<Pool, ServerError> {
  // URL取得
  let redis_url = config.redis_url.clone();
  // 接続設定
  let cfg = Config::from_url(&redis_url);
  let pool = cfg
    .create_pool(Some(Runtime::Tokio1))
    .map_err(|e| ServerError::PoolError(e.to_string()))?;
  tracing::info!("Connected to Redis via Deadpool");
  Ok(pool)
}

/// 追加するタスク
#[celery::task(name = "mia_tasks.run_attack")]
pub async fn run_attack(_params: CreateTaskRequest) {}

/// Celeryアプリを初期化する
/// * 戻り値: Arc<celery::Celery> - Celeryアプリ
pub async fn establish_celery_app(config: &AppConfig) -> Result<Arc<celery::Celery>, ServerError> {
  // URL取得
  let redis_url = config.redis_url.clone();
  // アプリの初期化
  let celery_app = celery::app!(
    broker = RedisBroker { redis_url },
    tasks = [run_attack],
    task_routes = []
  )
  .await
  .map_err(ServerError::CeleryError)?;
  tracing::info!("Celery App created successfully");
  Ok(celery_app)
}

/// MINIO接続を確立する
/// * 戻り値: Client - MINIO接続
pub async fn establish_storage_client(config: &AppConfig) -> Client {
  let access_key = config.minio_access_key.clone();
  let secret_key = config.minio_secret_key.clone();
  let endpoint = config.minio_endpoint.clone();
  let region = config.minio_region.clone(); // MINIOではregionが必須ではないので

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

  // こいつがResultを返さずにPanicするのでResultできん
  Client::from_conf(sdk_config)
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
