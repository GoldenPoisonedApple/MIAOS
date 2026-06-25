use std::collections::HashMap;

use serde::{Deserialize, Serialize};
use utoipa::ToSchema;

/// 透かし設定（`experiments.watermark` JSONB）
#[derive(Debug, Serialize, Deserialize, Clone, Default, ToSchema)]
pub struct WatermarkConfig {
  /// 透かしを有効にするか
  #[serde(default)]
  pub enabled: bool,
  /// MinIO フィルタ ID（`filters/{id}.png`）
  #[serde(default, skip_serializing_if = "Option::is_none")]
  pub filter_id: Option<String>,
  /// 分割名 → 適用割合（0.0〜1.0）
  #[serde(default)]
  pub apply: HashMap<String, f64>,
  /// シードオフセット
  #[serde(default)]
  pub seed_offset: i32,
}
