use std::env;

use thiserror::Error;

/// 起動時に必要な環境変数をまとめた設定
#[derive(Debug, Clone)]
pub struct AppConfig {
  // サーバー
  pub log_level: String,
  pub server_port: u16,

  // PostgreSQL
  pub database_url: String,

  // Redis / Celery
  pub redis_url: String,

  // MinIO (S3 互換)
  pub minio_access_key: String,
  pub minio_secret_key: String,
  pub minio_endpoint: String,
  pub minio_region: String,
  pub minio_bucket_name: String,
}

#[derive(Debug, Error)]
pub enum ConfigError {
  #[error("missing required environment variable: {0}")]
  Missing(&'static str),

  #[error("invalid value for {name}: {reason}")]
  Invalid { name: &'static str, reason: String },
}

impl AppConfig {
  /// 本番・開発: 環境変数から読み込む
  pub fn from_env() -> Result<Self, ConfigError> {
    Ok(Self {
      log_level: env::var("LOG_LEVEL").unwrap_or_else(|_| "info".to_string()),
      server_port: parse_port(env::var("SERVER_PORT").ok().as_deref())?,

      database_url: required("DATABASE_URL")?,
      redis_url: required("REDIS_URL")?,

      minio_access_key: required("MINIO_ACCESS_KEY")?,
      minio_secret_key: required("MINIO_SECRET_KEY")?,
      minio_endpoint: required("MINIO_ENDPOINT")?,
      minio_region: env::var("MINIO_REGION").unwrap_or_else(|_| "us-east-1".to_string()),
      minio_bucket_name: required("MINIO_BUCKET_NAME")?,
    })
  }

  /// 統合テスト用: テスト用の環境変数があればそれを使用
  pub fn test_defaults() -> Result<Self, ConfigError> {
    Ok(Self {
      log_level: "debug".to_string(),
      server_port: 3000,
      database_url: required("DATABASE_URL")?,
      redis_url: required("REDIS_URL")?,
      minio_access_key: required("MINIO_ACCESS_KEY")?,
      minio_secret_key: required("MINIO_SECRET_KEY")?,
      minio_endpoint: required("MINIO_ENDPOINT")?,
      minio_region: env::var("MINIO_REGION").unwrap_or_else(|_| "us-east-1".to_string()),
      minio_bucket_name: required("MINIO_BUCKET_NAME")?,
    })
  }
}

/// 環境変数が必須の場合
/// * 引数: name - 環境変数の名前
/// * 戻り値: String - 環境変数の値
fn required(name: &'static str) -> Result<String, ConfigError> {
  env::var(name).map_err(|_| ConfigError::Missing(name))
}

// /// 環境変数が必須ではない場合
// /// * 引数: name - 環境変数の名前
// /// * 引数: default - デフォルト値
// /// * 戻り値: String - 環境変数の値
// fn env_or(name: &str, default: &str) -> String {
//   env::var(name).unwrap_or_else(|_| default.to_string())
// }

/// ポート番号のパース
fn parse_port(value: Option<&str>) -> Result<u16, ConfigError> {
  match value {
    None => Ok(3000),
    Some(s) => s.parse::<u16>().map_err(|e| ConfigError::Invalid {
      name: "SERVER_PORT",
      reason: e.to_string(),
    }),
  }
}
