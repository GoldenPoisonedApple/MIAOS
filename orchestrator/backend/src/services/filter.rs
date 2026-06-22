use aws_sdk_s3::primitives::ByteStream;
use image::GenericImageView;
use regex::Regex;
use std::sync::LazyLock;

use crate::dto::filter::FilterSummary;
use crate::error::ServerError;
use crate::repositories::storage::StorageRepositoryTrait;

/// フィルタ画像のプレフィックス
const FILTERS_PREFIX: &str = "filters/";

/// フィルタIDの正規表現
// LazyLock: 最初に使われたときだけ初期化
// +: 一文字以上
static FILTER_ID_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^[a-zA-Z0-9_-]+$").unwrap());

/// フィルタ画像の管理サービス
pub struct FilterService<S: StorageRepositoryTrait> {
  storage_repository: S,
}

impl<S: StorageRepositoryTrait> FilterService<S> {
  pub fn new(storage_repository: S) -> Self {
    Self { storage_repository }
  }

  /// 登録済みフィルタ一覧
  /// * 戻り値: Result<Vec<FilterSummary>, ServerError> - 登録済みフィルタ一覧
  pub async fn list_filters(&self) -> Result<Vec<FilterSummary>, ServerError> {
    let keys = self.storage_repository.list_objects(FILTERS_PREFIX).await?;


    let mut filters: Vec<FilterSummary> = keys
      .iter()
      // keyからフィルタIDを抽出、Someの時は FilterSummary { id }を生成
      .filter_map(|key| filter_id_from_key(key).map(|id| FilterSummary { id }))
      .collect();
    // フィルタIDでソート
    // cmp: 比較関数
    filters.sort_by(|a, b| a.id.cmp(&b.id));
    Ok(filters)
  }

  /// フィルタ PNG をアップロードする
  /// * id: &str - フィルタID
  /// * bytes: Vec<u8> - フィルタPNGのバイト列
  /// * 戻り値: Result<(), ServerError> - フィルタPNGのアップロード結果
  pub async fn upload_filter(&self, id: &str, bytes: Vec<u8>) -> Result<(), ServerError> {
    validate_filter_id(id)?;
    validate_png_dimensions(&bytes)?;

    let key = filter_object_key(id);
    if self.storage_repository.object_exists(&key).await? {
      return Err(ServerError::Conflict(format!(
        "filter already exists: {id}"
      )));
    }

    let body = ByteStream::from(bytes);
    self
      .storage_repository
      .put_object(&key, body, "image/png")
      .await
  }

  /// フィルタPNGを削除する
  /// * id: &str - フィルタID
  /// * 戻り値: Result<(), ServerError> - フィルタPNGの削除結果
  pub async fn delete_filter(&self, id: &str) -> Result<(), ServerError> {
    validate_filter_id(id)?;
    let key = filter_object_key(id);
    if !self.storage_repository.object_exists(&key).await? {
      return Err(ServerError::NotFound(format!(
        "filter not found: {id}"
      )));
    }
    
    self.storage_repository.delete_object(&key).await
  }
}

/// フィルタオブジェクトキーを生成する
/// * id: &str - フィルタID
/// * 戻り値: String - フィルタオブジェクトキー
fn filter_object_key(id: &str) -> String {
  format!("{FILTERS_PREFIX}{id}.png")
}

/// オブジェクトキーからフィルタIDを抽出する
/// * key: &str - オブジェクトキー
/// * 戻り値: Option<String> - フィルタID
fn filter_id_from_key(key: &str) -> Option<String> {
  key
    .strip_prefix(FILTERS_PREFIX)?
    .strip_suffix(".png")
    .map(str::to_string)
}

/// フィルタIDのバリデーション
/// * id: &str - フィルタID
/// * 戻り値: Result<(), ServerError> - フィルタIDのバリデーション結果
fn validate_filter_id(id: &str) -> Result<(), ServerError> {
  // 空文字列または正規表現にマッチしない場合はエラー
  if id.is_empty() || !FILTER_ID_RE.is_match(id) {
    return Err(ServerError::InvalidPath(format!(
      "invalid filter id: {id} (allowed: [a-zA-Z0-9_-]+)"
    )));
  }
  Ok(())
}

fn validate_png_dimensions(bytes: &[u8]) -> Result<(), ServerError> {
  // PNGシグネチャ検証
  const PNG_SIGNATURE: &[u8] = &[0x89, b'P', b'N', b'G', 0x0d, 0x0a, 0x1a, 0x0a];
  if bytes.len() < PNG_SIGNATURE.len() || &bytes[..PNG_SIGNATURE.len()] != PNG_SIGNATURE {
    return Err(ServerError::DataFormatError(
      "only PNG images are allowed".to_string(),
    ));
  }

  // PNGとしてデコード可能か検証
  let img = image::load_from_memory(bytes)
    .map_err(|e| ServerError::DataFormatError(format!("invalid image: {e}")))?;

  // 画像サイズ検証 32x32のみ許可
  if img.dimensions() != (32, 32) {
    return Err(ServerError::DataFormatError(format!(
      "image must be 32x32, got {}x{}",
      img.dimensions().0,
      img.dimensions().1
    )));
  }

  Ok(())
}

#[cfg(test)]
mod tests {
  use super::*;

  #[test]
  fn filter_object_key_format() {
    assert_eq!(filter_object_key("circle"), "filters/circle.png");
  }

  #[test]
  fn filter_id_from_key_parses() {
    assert_eq!(
      filter_id_from_key("filters/circle.png").as_deref(),
      Some("circle")
    );
  }

  #[test]
  fn validate_filter_id_rejects_invalid() {
    assert!(validate_filter_id("bad id").is_err());
    assert!(validate_filter_id("circle").is_ok());
  }
}
