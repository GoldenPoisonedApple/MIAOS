use crate::error::ServerError;
use async_trait::async_trait;
use aws_sdk_s3::{operation::get_object::GetObjectOutput, Client};

#[async_trait] // 非同期関数を含むトレイト用のマクロ
pub trait StorageRepositoryTrait: Send + Sync {
  /// オブジェクトを取得する
  async fn get_object(&self, key: &str) -> Result<GetObjectOutput, ServerError>;
}

/// ストレージへのアクセスを担当するリポジトリ
#[derive(Clone)]
pub struct StorageRepository {
  client: Client,
  bucket: String,
}

impl StorageRepository {
  /// コンストラクタ
  pub fn new(client: Client, bucket: String) -> Self {
    Self { client, bucket }
  }
}

#[async_trait]
impl StorageRepositoryTrait for StorageRepository {
  async fn get_object(&self, key: &str) -> Result<GetObjectOutput, ServerError> {
    self
      .client
      .get_object()
      .bucket(&self.bucket)
      .key(key)
      .send()
      .await
      .map_err(|e| {
        // NoSuchKey は 404 として扱う
        if e.to_string().contains("NoSuchKey") {
          ServerError::NotFound(format!("key not found: {key}"))
        } else {
          ServerError::S3Error(e)
        }
      })
  }
}

#[cfg(test)]
mod tests {
  use super::*;
  use crate::infrastructure::{establish_storage_client, get_bucket_name};

  /// オブジェクトの取得テスト
  #[tokio::test]
  async fn test_get_object() {
    let client = establish_storage_client().await;
    let repository = StorageRepository::new(client, get_bucket_name());
    let object = repository.get_object("test/sample.log").await.unwrap();
    assert_eq!(object.content_length(), Some("hello world".len() as i64)); // 正常に取得できていること
  }
}
