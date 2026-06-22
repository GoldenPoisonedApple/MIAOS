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
      return Err(ServerError::NotFound(format!("filter not found: {id}")));
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
  use crate::error::ServerError;
  use crate::repositories::storage::MockStorageRepositoryTrait;
  use mockall::predicate::*;

  /// 32x32 の有効な PNG バイト列を生成する（フィルタ API テスト用）
  fn sample_32x32_png() -> Vec<u8> {
    use image::{ImageBuffer, ImageFormat, Rgba};
    use std::io::Cursor;

    let img: ImageBuffer<Rgba<u8>, Vec<u8>> =
      ImageBuffer::from_fn(32, 32, |x, y| Rgba([x as u8, y as u8, 0, 255]));
    let mut bytes = Vec::new();
    img
      .write_to(&mut Cursor::new(&mut bytes), ImageFormat::Png)
      .unwrap();
    bytes
  }

  /// フィルタ一覧を取得し、フィルタIDでソートする
  #[tokio::test]
  async fn list_filters_sorts_and_parses_keys() {
    let mut mock = MockStorageRepositoryTrait::new();
    mock
      .expect_list_objects()
      .with(eq("filters/"))
      .times(1)
      .returning(|_| {
        Ok(vec![
          "filters/b.png".to_string(),
          "filters/a.png".to_string(),
          "filters/invalid.txt".to_string(),
        ])
      });

    let service = FilterService::new(mock);
    let filters = service.list_filters().await.unwrap();

    assert_eq!(filters.len(), 2);
    assert_eq!(filters[0].id, "a");
    assert_eq!(filters[1].id, "b");
  }

  /// フィルタPNGをアップロードし、フィルタが存在しない場合は成功する
  #[tokio::test]
  async fn upload_filter_succeeds_when_not_exists() {
    let png = sample_32x32_png();
    let mut mock = MockStorageRepositoryTrait::new();
    mock
      .expect_object_exists()
      .with(eq("filters/circle.png"))
      .times(1)
      .returning(|_| Ok(false));
    mock
      .expect_put_object()
      .withf(|key, _body, content_type| key == "filters/circle.png" && content_type == "image/png")
      .times(1)
      .returning(|_, _, _| Ok(()));

    let service = FilterService::new(mock);
    service.upload_filter("circle", png).await.unwrap();
  }

  /// フィルタPNGをアップロードし、フィルタが存在する場合はエラーを返す
  #[tokio::test]
  async fn upload_filter_returns_conflict_when_exists() {
    let png = sample_32x32_png();
    let mut mock = MockStorageRepositoryTrait::new();
    mock
      .expect_object_exists()
      .with(eq("filters/circle.png"))
      .times(1)
      .returning(|_| Ok(true));
    mock.expect_put_object().times(0);

    let service = FilterService::new(mock);
    let err = service.upload_filter("circle", png).await.unwrap_err();
    assert!(matches!(err, ServerError::Conflict(_)));
  }

  /// フィルタIDが無効な場合はエラーを返す
  #[tokio::test]
  async fn upload_filter_rejects_invalid_id() {
    let png = sample_32x32_png();
    let mock = MockStorageRepositoryTrait::new();
    let service = FilterService::new(mock);
    let err = service.upload_filter("bad id", png).await.unwrap_err();
    assert!(matches!(err, ServerError::InvalidPath(_)));
  }

  /// フィルタPNGが無効な場合はエラーを返す
  #[tokio::test]
  async fn upload_filter_rejects_invalid_png() {
    let mut mock = MockStorageRepositoryTrait::new();
    mock.expect_object_exists().times(0);
    let service = FilterService::new(mock);
    let err = service
      .upload_filter("circle", b"not-png".to_vec())
      .await
      .unwrap_err();
    assert!(matches!(err, ServerError::DataFormatError(_)));
  }

  /// フィルタPNGを削除し、フィルタが存在する場合は成功する
  #[tokio::test]
  async fn delete_filter_succeeds_when_exists() {
    let mut mock = MockStorageRepositoryTrait::new();
    mock
      .expect_object_exists()
      .with(eq("filters/circle.png"))
      .times(1)
      .returning(|_| Ok(true));
    mock
      .expect_delete_object()
      .with(eq("filters/circle.png"))
      .times(1)
      .returning(|_| Ok(()));

    let service = FilterService::new(mock);
    service.delete_filter("circle").await.unwrap();
  }

  /// フィルタPNGを削除し、フィルタが存在しない場合はエラーを返す
  #[tokio::test]
  async fn delete_filter_returns_not_found_when_missing() {
    let mut mock = MockStorageRepositoryTrait::new();
    mock
      .expect_object_exists()
      .with(eq("filters/circle.png"))
      .times(1)
      .returning(|_| Ok(false));
    mock.expect_delete_object().times(0);

    let service = FilterService::new(mock);
    let err = service.delete_filter("circle").await.unwrap_err();
    assert!(matches!(err, ServerError::NotFound(_)));
  }

  /// フィルタIDが無効な場合はエラーを返す
  #[tokio::test]
  async fn delete_filter_rejects_invalid_id() {
    let mock = MockStorageRepositoryTrait::new();
    let service = FilterService::new(mock);
    let err = service.delete_filter("bad id").await.unwrap_err();
    assert!(matches!(err, ServerError::InvalidPath(_)));
  }

  #[cfg(feature = "integration-test")]
  mod integration_tests {
    use super::*;
    use crate::config::app::AppConfig;
    use crate::infrastructure::establish_storage_client;
    use crate::repositories::storage::StorageRepository;

    /// 結合テスト用の一意なフィルタ ID（`[a-zA-Z0-9_-]+` 準拠）
    fn unique_filter_id(prefix: &str) -> String {
      format!("{prefix}_{}", uuid::Uuid::new_v4().simple())
    }

    async fn setup_repository() -> StorageRepository {
      let config = AppConfig::test_defaults().unwrap();
      let client = establish_storage_client(&config).await;
      StorageRepository::new(client, config.minio_bucket_name.clone())
    }

    /// upload → list → delete → list の一連フロー
    #[tokio::test]
    async fn filter_crud_flow() {
      let repository = setup_repository().await;
      let service = FilterService::new(repository);
      let id = unique_filter_id("filter_crud");
      let png = sample_32x32_png();

      service.upload_filter(&id, png).await.unwrap();
      let filters = service.list_filters().await.unwrap();
      assert!(filters.iter().any(|f| f.id == id));

      service.delete_filter(&id).await.unwrap();
      let filters = service.list_filters().await.unwrap();
      assert!(!filters.iter().any(|f| f.id == id));

      let err = service.delete_filter(&id).await.unwrap_err();
      assert!(matches!(err, crate::error::ServerError::NotFound(_)));
    }

    /// 重複アップロードは 409
    #[tokio::test]
    async fn upload_filter_conflict_on_duplicate() {
      let repository = setup_repository().await;
      let service = FilterService::new(repository);
      let id = unique_filter_id("filter_dup");
      let png = sample_32x32_png();

      service.upload_filter(&id, png.clone()).await.unwrap();
      let err = service.upload_filter(&id, png).await.unwrap_err();
      assert!(matches!(err, crate::error::ServerError::Conflict(_)));

      service.delete_filter(&id).await.unwrap();
    }
  }
}
