use serde::{Deserialize, Serialize};
use utoipa::ToSchema;

/// 登録済みフィルタの概要
#[derive(Debug, Serialize, Deserialize, ToSchema)]
pub struct FilterSummary {
  /// フィルタ ID（MinIO キー `filters/{id}.png` の {id} 部分）
  pub id: String,
}

/// フィルタ一覧レスポンス
#[derive(Debug, Serialize, ToSchema)]
pub struct FilterListResponse {
  pub filters: Vec<FilterSummary>,
}
