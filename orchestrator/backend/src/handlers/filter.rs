use std::sync::Arc;

use axum::extract::{Multipart, State};
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
  path = "/api/filters",
  responses(
    (status = 200, description = "アップロード成功", body = FilterSummary),
    (status = 400, description = "バリデーションエラー"),
    (status = 409, description = "フィルタ ID が既に存在"),
    (status = 500, description = "サーバー内部エラー")
  ),
  tag = "Filters"
)]
pub async fn upload_filter(
  State(service): State<Arc<FilterService<StorageRepository>>>,
  mut multipart: Multipart,
) -> Result<Json<FilterSummary>, ServerError> {
  let mut filter_id: Option<String> = None;
  let mut file_bytes: Option<Vec<u8>> = None;

  while let Some(field) = multipart
    .next_field()
    .await
    .map_err(|e| ServerError::DataFormatError(format!("multipart error: {e}")))?
  {
    let name = field.name().unwrap_or("").to_string();
    match name.as_str() {
      "id" => {
        let text = field
          .text()
          .await
          .map_err(|e| ServerError::DataFormatError(format!("id field error: {e}")))?;
        filter_id = Some(text);
      }
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

  let id = filter_id
    .ok_or_else(|| ServerError::DataFormatError("multipart field 'id' is required".to_string()))?;
  let bytes = file_bytes.ok_or_else(|| {
    ServerError::DataFormatError("multipart field 'file' is required".to_string())
  })?;

  service.upload_filter(&id, bytes).await?;
  Ok(Json(FilterSummary { id }))
}
