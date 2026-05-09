use axum::{routing::get, Router};
use sqlx::postgres::PgPoolOptions;
use std::net::SocketAddr;
use tokio::net::TcpListener;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
  const SERVER_PORT: u16 = 3000;
	const MAX_CONNECTIONS: u32 = 5;
  // 構造化ログの初期化
  // RUST_LOG環境変数でレベル制御可能 (デフォルトは debug)
  tracing_subscriber::registry()
    .with(
      tracing_subscriber::EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| "server=debug".into()),
    )
    .with(tracing_subscriber::fmt::layer())
    .init();

  // DB接続
  let db_url = std::env::var("DATABASE_URL").expect("DATABASE_URL must be set");
  let pool = PgPoolOptions::new()
    .max_connections(MAX_CONNECTIONS)
    .connect(&db_url)
    .await?;
  tracing::info!("Connected to database");

  let app = Router::new()
    .route("/", get(|| async { "Hello, World!" }))
    .with_state(pool);
  let addr = SocketAddr::from(([0, 0, 0, 0], SERVER_PORT));
  tracing::info!("Listening on {}", addr);

  // サーバ起動
  let listener = TcpListener::bind(addr).await.unwrap();
  axum::serve(listener, app).await.unwrap();

  Ok(())
}
