use std::sync::Arc;

use axum::extract::{Multipart, Path, State};
use axum::http::StatusCode;
use axum::Json;

use crate::dto::filter::{FilterListResponse, FilterSummary};
use crate::error::ServerError;
use crate::repositories::storage::StorageRepository;
use crate::services::filter::FilterService;

/// 登録済みフィルタ一覧
#[utoipa::path(
  get,
  path = "/api/filters",
  responses(
    (status = 200, description = "フィルタ一覧", body = FilterListResponse),
    (status = 500, description = "サーバー内部エラー")
  ),
  tag = "Filters"
)]
pub async fn list_filters(
  State(service): State<Arc<FilterService<StorageRepository>>>,
) -> Result<Json<FilterListResponse>, ServerError> {
  let filters = service.list_filters().await?;
  Ok(Json(FilterListResponse { filters }))
}

/// フィルタ画像をアップロードする
#[utoipa::path(
  post,
  path = "/api/filters/{id}",
  params(
    ("id" = String, Path, description = "フィルタ ID（`[a-zA-Z0-9_-]+`）")
  ),
  responses(
    (status = 201, description = "アップロード成功", body = FilterSummary),
    (status = 400, description = "バリデーションエラー"),
    (status = 409, description = "フィルタ ID が既に存在"),
    (status = 500, description = "サーバー内部エラー")
  ),
  tag = "Filters"
)]
pub async fn upload_filter(
  State(service): State<Arc<FilterService<StorageRepository>>>,
  Path(id): Path<String>,
  mut multipart: Multipart,
) -> Result<(StatusCode, Json<FilterSummary>), ServerError> {
  let mut file_bytes: Option<Vec<u8>> = None;

  while let Some(field) = multipart
    .next_field()
    .await
    .map_err(|e| ServerError::DataFormatError(format!("multipart error: {e}")))?
  {
    let name = field.name().unwrap_or("").to_string();
    match name.as_str() {
      // フィルタPNGフィールド
      "file" => {
        let bytes = field
          .bytes()
          .await
          .map_err(|e| ServerError::DataFormatError(format!("file field error: {e}")))?;
        file_bytes = Some(bytes.to_vec());
      }
      _ => {}
    }
  }

  let bytes = file_bytes.ok_or_else(|| {
    ServerError::DataFormatError("multipart field 'file' is required".to_string())
  })?;

  // フィルタPNGをアップロード
  service.upload_filter(&id, bytes).await?;
  Ok((StatusCode::CREATED, Json(FilterSummary { id })))
}

/// フィルタPNGを削除する
#[utoipa::path(
  delete,
  path = "/api/filters/{id}",
  params(
    ("id" = String, Path, description = "フィルタ ID")
  ),
  responses(
    (status = 200, description = "削除成功", body = FilterSummary),
    (status = 404, description = "フィルタが見つからない"),
    (status = 500, description = "サーバー内部エラー")
  ),
  tag = "Filters"
)]
pub async fn delete_filter(
  State(service): State<Arc<FilterService<StorageRepository>>>,
  Path(id): Path<String>,
) -> Result<Json<FilterSummary>, ServerError> {
  service.delete_filter(&id).await?;
  Ok(Json(FilterSummary { id }))
}
