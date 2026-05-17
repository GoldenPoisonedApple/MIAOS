use aws_sdk_s3::operation::get_object::GetObjectOutput;

use crate::error::ServerError;
use crate::repositories::storage::StorageRepositoryTrait;

/// ビジネスロジックを担当するサービス
pub struct StorageService<S: StorageRepositoryTrait> {
  storage_repository: S,
}

impl<S: StorageRepositoryTrait> StorageService<S> {
  pub fn new(storage_repository: S) -> Self {
    Self { storage_repository }
  }

	/// オブジェクトを取得する
	/// * key: &str - オブジェクトのキー
	/// * 戻り値: Result<GetObjectOutput, ServerError> - オブジェクトの取得結果
  pub async fn fetch(&self, key: &str) -> Result<GetObjectOutput, ServerError> {
		// 無効なパスの場合はエラーを返す
    if key.contains("..") {
      return Err(ServerError::InvalidPath(format!("invalid key: {key}")));
    }
    self.storage_repository.get_object(key).await
  }
}
