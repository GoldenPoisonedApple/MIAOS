use axum::{
  http::StatusCode,
  response::{IntoResponse, Response},
};
use thiserror::Error;

#[derive(Error, Debug)]
pub enum ServerError {
  /// DBエラー
  #[error("Database error: {0}")]
  DatabaseError(#[from] sea_orm::DbErr),

  /// Redisエラー
  #[error("Redis error: {0}")]
  RedisError(#[from] redis::RedisError),

  /// Celeryエラー
  #[error("Celery error: {0}")]
  CeleryError(#[from] celery::error::CeleryError),

  /// S3エラー
  #[error("S3 error: {0}")]
  S3Error(#[from] aws_sdk_s3::error::SdkError<aws_sdk_s3::operation::get_object::GetObjectError>),

  /// Poolエラー
  #[error("Pool error: {0}")]
  PoolError(String),

  /// JSONエラー
  #[error("JSON error: {0}")]
  JsonError(#[from] serde_json::Error),

  /// Base64デコードエラー
  #[error("Base64 decode error: {0}")]
  Base64Error(#[from] base64::DecodeError),
  /// UTF-8変換エラー
  #[error("UTF-8 conversion error: {0}")]
  Utf8Error(#[from] std::string::FromUtf8Error),
  /// UUIDエラー
  #[error("UUID error: {0}")]
  UuidError(#[from] uuid::Error),

  /// データ構造の不整合エラー（JSON内の期待するキーがない場合など）
  #[error("Data format error: {0}")]
  DataFormatError(String),

  /// 無効なパスエラー
  #[error("Invalid path: {0}")]
  InvalidPath(String),

  /// Not Foundエラー
  #[error("Not found: {0}")]
  NotFound(String),

  /// 内部エラー
  #[error("Internal server error: {0}")]
  Internal(String),
}

// Axumのハンドラから直接このエラーを返せるようにする設定
impl IntoResponse for ServerError {
  fn into_response(self) -> Response {
    let (status, message) = match self {
      ServerError::NotFound(msg) => (StatusCode::NOT_FOUND, msg),
      ServerError::DatabaseError(_) | ServerError::RedisError(_) | ServerError::PoolError(_) => (
        StatusCode::INTERNAL_SERVER_ERROR,
        "Internal Database Error".to_string(),
      ),
      _ => (
        StatusCode::INTERNAL_SERVER_ERROR,
        "Internal Server Error".to_string(),
      ),
    };

    (status, message).into_response()
  }
}
