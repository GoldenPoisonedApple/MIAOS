use axum::{routing::get, Router};
use tokio::net::TcpListener;
use std::net::SocketAddr;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};


#[tokio::main]
async fn main() {
		// 構造化ログの初期化
		// RUST_LOG環境変数でレベル制御可能 (デフォルトは debug)
		tracing_subscriber::registry()
			.with(
				tracing_subscriber::EnvFilter::try_from_default_env()
					.unwrap_or_else(|_| "server=debug".into()),
			)
			.with(tracing_subscriber::fmt::layer())
			.init();

    let app = Router::new().route("/", get(|| async { "Hello, World!" }));
		let addr = SocketAddr::from(([0, 0, 0, 0], 3000));
		println!("Listening on {}", addr);
		
		// サーバ起動
    let listener = TcpListener::bind(addr).await.unwrap();
		axum::serve(listener, app).await.unwrap();
}
