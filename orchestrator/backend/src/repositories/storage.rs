use crate::error::ServerError;
use async_trait::async_trait;
use aws_sdk_s3::error::{ProvideErrorMetadata, SdkError};
use aws_sdk_s3::{operation::get_object::GetObjectOutput, primitives::ByteStream, Client};

#[cfg_attr(test, mockall::automock)]
#[async_trait] // 非同期関数を含むトレイト用のマクロ
pub trait StorageRepositoryTrait: Send + Sync {
  /// オブジェクトを取得する
  async fn get_object(&self, key: &str) -> Result<GetObjectOutput, ServerError>;

  /// オブジェクトを削除する
  async fn delete_object(&self, key: &str) -> Result<(), ServerError>;

  /// プレフィックス配下のオブジェクトキー一覧を返す
  async fn list_objects(&self, prefix: &str) -> Result<Vec<String>, ServerError>;

  /// オブジェクトをアップロードする
  async fn put_object(
    &self,
    key: &str,
    body: ByteStream,
    content_type: &str,
  ) -> Result<(), ServerError>;

  /// オブジェクトが存在するか
  async fn object_exists(&self, key: &str) -> Result<bool, ServerError>;
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
  /// オブジェクトを取得する
  /// * key: &str - オブジェクトのキー
  /// * 戻り値: Result<GetObjectOutput, ServerError> - オブジェクトの取得結果
  async fn get_object(&self, key: &str) -> Result<GetObjectOutput, ServerError> {
    match self
      .client
      .get_object()
      .bucket(&self.bucket)
      .key(key)
      .send()
      .await
    {
      Ok(output) => Ok(output),
      Err(SdkError::ServiceError(err)) => {
        let inner = err.err();
        // NotFoundを検出
        if inner.is_no_such_key()
          || inner.code() == Some("NoSuchKey")
          || err.raw().status().as_u16() == 404
        {
          Err(ServerError::NotFound(format!("key not found: {key}")))
        } else {
          Err(ServerError::S3Error(format!("S3 error: {inner}")))
        }
      }
      Err(e) => Err(ServerError::S3Error(format!("S3 error: {e}"))),
    }
  }

  /// オブジェクトを削除する
  /// * key: &str - オブジェクトのキー
  async fn delete_object(&self, key: &str) -> Result<(), ServerError> {
    self
      .client
      .delete_object()
      .bucket(&self.bucket)
      .key(key)
      .send()
      .await
      .map_err(|e| ServerError::S3Error(format!("S3 delete error: {e}")))?;

    Ok(())
  }

  /// プレフィックス配下のオブジェクトキー一覧を返す
  /// * prefix: &str - プレフィックス
  /// * 戻り値: Result<Vec<String>, ServerError> - オブジェクトキー一覧
  async fn list_objects(&self, prefix: &str) -> Result<Vec<String>, ServerError> {
    let mut keys = Vec::new();
    // 一回のリクエストで取得できない場合は、継続トークンを使用して次のリクエストを行う
    let mut continuation_token: Option<String> = None;

    loop {
      // リクエストを作成
      let mut request = self
        .client
        .list_objects_v2()
        .bucket(&self.bucket)
        .prefix(prefix);

      // 継続トークンがある場合は、継続トークン情報追加
      if let Some(token) = continuation_token {
        request = request.continuation_token(token);
      }

      // リクエストを送信
      let output = request
        .send()
        .await
        .map_err(|e| ServerError::S3Error(format!("S3 list error: {e}")))?;

      // オブジェクトキー一覧を取得
      if let Some(contents) = output.contents {
        for obj in contents {
          if let Some(key) = obj.key {
            if !key.ends_with('/') {
              keys.push(key);
            }
          }
        }
      }

      // 一回のリクエストで取得できない場合は、継続トークンを使用して次のリクエストを行う
      // is_truncated: さらに返せるキーがある場合true
      if output.is_truncated == Some(true) {
        continuation_token = output.next_continuation_token;
      } else {
        break;
      }
    }

    Ok(keys)
  }

  /// オブジェクトをアップロードする
  /// * key: &str - オブジェクトのキー
  /// * body: ByteStream - オブジェクトのボディ
  /// * content_type: &str - オブジェクトのコンテンツタイプ
  /// * 戻り値: Result<(), ServerError> - オブジェクトのアップロード結果
  async fn put_object(
    &self,
    key: &str,
    body: ByteStream,
    content_type: &str,
  ) -> Result<(), ServerError> {
    self
      .client
      .put_object()
      .bucket(&self.bucket)
      .key(key)
      .body(body)
      .content_type(content_type)
      .send()
      .await
      .map_err(|e| ServerError::S3Error(format!("S3 put error: {e}")))?;
    Ok(())
  }

  /// オブジェクトが存在するか
  /// * key: &str - オブジェクトのキー
  /// * 戻り値: Result<bool, ServerError> - オブジェクトの存在有無
  async fn object_exists(&self, key: &str) -> Result<bool, ServerError> {
    match self
      .client
      .head_object()
      .bucket(&self.bucket)
      .key(key)
      .send()
      .await
    {
      Ok(_) => Ok(true),
      Err(SdkError::ServiceError(err)) => {
        let inner = err.err();
        // NotFoundを検出
        if inner.is_not_found()
          || inner.code() == Some("NoSuchKey")
          || err.raw().status().as_u16() == 404
        {
          Ok(false)
        } else {
          Err(ServerError::S3Error(format!("S3 head error: {inner}")))
        }
      }
      Err(e) => Err(ServerError::S3Error(format!("S3 head error: {e}"))),
    }
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
  use uuid::Uuid;

  /// 結合テスト用の一意なオブジェクトキー
  /// * prefix: &str - プレフィックス
  /// * 戻り値: String - 一意なオブジェクトキー
  pub fn unique_storage_key(prefix: &str) -> String {
    format!("{prefix}/{}", Uuid::new_v4())
  }

  async fn setup_repository() -> StorageRepository {
    let config = AppConfig::test_defaults().unwrap();
    let client = establish_storage_client(&config).await;
    StorageRepository::new(client, config.minio_bucket_name.clone())
  }

  /// put → get で内容が一致すること
  #[tokio::test]
  async fn test_put_and_get_object() {
    let repository = setup_repository().await;
    let key = unique_storage_key("test/storage");
    let file_content = "hello world";
    let body = ByteStream::from(file_content.as_bytes().to_vec());

    repository
      .put_object(&key, body, "text/plain")
      .await
      .unwrap();

    let object = repository.get_object(&key).await.unwrap();
    let content = object.body.collect().await.unwrap().into_bytes();
    let content = String::from_utf8(content.to_vec()).unwrap();
    assert_eq!(content, file_content);

    repository.delete_object(&key).await.unwrap();
  }

  /// オブジェクトの取得テスト
  #[tokio::test]
  async fn test_get_object() {
    let repository = setup_repository().await;
    let key = unique_storage_key("test/storage");
    let file_content = "hello world";
    let body = ByteStream::from(file_content.as_bytes().to_vec());
    repository
      .put_object(&key, body, "text/plain")
      .await
      .unwrap();

    let object = repository.get_object(&key).await.unwrap();
    let content = object.body.collect().await.unwrap().into_bytes();
    let content = String::from_utf8(content.to_vec()).unwrap();
    assert_eq!(content, file_content);

    repository.delete_object(&key).await.unwrap();
  }

  /// delete 後は get で NotFound になること
  #[tokio::test]
  async fn test_delete_object() {
    let repository = setup_repository().await;
    let key = unique_storage_key("test/storage");
    let body = ByteStream::from(b"delete me".to_vec());
    repository
      .put_object(&key, body, "text/plain")
      .await
      .unwrap();

    repository.delete_object(&key).await.unwrap();

    let err = repository.get_object(&key).await.unwrap_err();
    assert!(matches!(err, ServerError::NotFound(_)));
  }

  /// object_exists が存在・非存在を正しく返すこと
  #[tokio::test]
  async fn test_object_exists() {
    let repository = setup_repository().await;
    let key = unique_storage_key("test/storage");
    let body = ByteStream::from(b"exists".to_vec());

    assert!(!repository.object_exists(&key).await.unwrap());

    repository
      .put_object(&key, body, "text/plain")
      .await
      .unwrap();
    assert!(repository.object_exists(&key).await.unwrap());

    repository.delete_object(&key).await.unwrap();
    assert!(!repository.object_exists(&key).await.unwrap());
  }

  /// list_objects がプレフィックス配下を列挙し、ディレクトリプレースホルダを除外すること
  #[tokio::test]
  async fn test_list_objects() {
    let repository = setup_repository().await;
    let prefix = unique_storage_key("test/list");
    let key_a = format!("{prefix}/a.log");
    let key_b = format!("{prefix}/b.log");

    repository
      .put_object(&key_a, ByteStream::from(b"a".to_vec()), "text/plain")
      .await
      .unwrap();
    repository
      .put_object(&key_b, ByteStream::from(b"b".to_vec()), "text/plain")
      .await
      .unwrap();

    let keys = repository.list_objects(&prefix).await.unwrap();
    assert!(keys.contains(&key_a));
    assert!(keys.contains(&key_b));
    assert!(!keys.iter().any(|k| k.ends_with('/')));

    repository.delete_object(&key_a).await.unwrap();
    repository.delete_object(&key_b).await.unwrap();
  }
}
