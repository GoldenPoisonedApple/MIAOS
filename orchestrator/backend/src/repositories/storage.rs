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
          ServerError::S3Error(format!("S3 error: {e}"))
        }
      })
  }
}

#[cfg(all(test, feature = "integration-test"))]
// 結合テストのみ 本当は#[tokio::test]の真上に置くが、ここのテストは他に無いので, useとかがwarningになってうるさいからここ
// サブモジュールにまとめて、下みたいな書き方もできる
// --features integration-test オプションで実行可能
// #[cfg(feature = "integration-test")]
// mod integration {
//   use super::*;
//   use crate::infrastructure::{establish_storage_client, get_bucket_name};
//   use aws_sdk_s3::primitives::ByteStream;
//   #[tokio::test]
//   async fn test_get_object() { ... }
// }
// test 属性もオンになっていないと test_utilが cfg(test)月なので読み込めない
mod tests {
  use super::*;
  use crate::config::app::AppConfig;
  use crate::infrastructure::establish_storage_client;
  use aws_sdk_s3::primitives::ByteStream;

  /// オブジェクトの取得テスト
  #[tokio::test]
  async fn test_get_object() {
    // Arrange
    let config = AppConfig::test_defaults().unwrap();
    let client = establish_storage_client(&config).await;
    let bucket_name = config.minio_bucket_name.clone();
    // 読み取るためのサンプルファイルをstorageに作成
    let file_path = "test/sample.log";
    let file_content = "hello world";
    let body = ByteStream::from(file_content.as_bytes().to_vec());
    client
      .put_object()
      .bucket(bucket_name.clone())
      .key(file_path)
      .body(body)
      .send()
      .await
      .unwrap();
    let repository = StorageRepository::new(client.clone(), bucket_name.clone());
    // Act
    let object = repository.get_object(file_path).await.unwrap();
    // Assert
    let content = object.body.collect().await.unwrap().into_bytes();
    let content = String::from_utf8(content.to_vec()).unwrap();
    assert_eq!(content, file_content); // 正常に取得できていること
                                       // ファイルを削除
    client
      .delete_object()
      .bucket(bucket_name)
      .key(file_path)
      .send()
      .await
      .unwrap();
  }
}
