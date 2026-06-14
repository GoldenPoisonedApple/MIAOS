use async_trait::async_trait;
use sea_orm::{ActiveModelTrait, DatabaseConnection, EntityTrait};

use crate::dto::experiment::CreateExperimentRequest;
use crate::entities::experiment::{ActiveModel, Entity, Model};
use crate::error::ServerError;

#[async_trait] // 非同期関数を含むトレイト用のマクロ
pub trait ExperimentRepositoryTrait: Send + Sync {
  async fn create(&self, request: CreateExperimentRequest) -> Result<Model, ServerError>;
  async fn update(&self, model: Model) -> Result<Model, ServerError>;
  async fn find_by_id(&self, id: i64) -> Result<Model, ServerError>;
  async fn find_all(&self) -> Result<Vec<Model>, ServerError>;
  async fn delete_from_id(&self, id: i64) -> Result<u64, ServerError>;
}

/// Experimentsテーブルへのアクセスを担当するリポジトリ
/// DatabaseConnectionは内部でArc(参照カウント)を使用しているため、Cloneコストは低い
/// つまりconnというよりかはpoolと言った方が正しい
#[derive(Clone)]
pub struct ExperimentRepository {
  pool: DatabaseConnection,
}

impl ExperimentRepository {
  /// コンストラクタ
  pub fn new(pool: DatabaseConnection) -> Self {
    Self { pool }
  }
}

#[async_trait]
impl ExperimentRepositoryTrait for ExperimentRepository {
  /// 新規実験の作成 (INSERT)
  /// * request: CreateExperimentRequest - 実験の作成リクエスト
  /// * 戻り値: Result<Model, ServerError> - 実験の作成結果
  async fn create(&self, request: CreateExperimentRequest) -> Result<Model, ServerError> {
    // DTOをActiveModelに変換
    let active_model = ActiveModel::from(request);
    // データベースに保存 Okの場合Modelが返る
    let result = active_model.insert(&self.pool).await?;

    Ok(result)
  }

  /// 実験の結果を更新
  /// * model: Model - 更新する実験モデル
  /// * 戻り値: Result<Model, ServerError> - 実験の結果更新結果
  async fn update(&self, model: Model) -> Result<Model, ServerError> {
    // ModelをActiveModelに変換 変更を通知してやらんと変更されない仕様なので
    let active_model = model.into_active_model_for_update();
    // IDに合致する実験を更新
    let result = active_model.update(&self.pool).await?;
    Ok(result)
  }

  /// 指定されたIDの実験を取得
  /// * id: i64 - 取得する実験のID
  /// * 戻り値: Result<Model, ServerError> - 実験の取得結果
  async fn find_by_id(&self, id: i64) -> Result<Model, ServerError> {
    match Entity::find_by_id(id).one(&self.pool).await? {
      Some(experiment) => Ok(experiment),
      None => Err(ServerError::NotFound(format!(
        "Experiment with id {} not found",
        id
      ))),
    }
  }

  /// すべての実験を取得
  /// * 戻り値: Result<Vec<Model>, ServerError> - 実験の一覧取得結果
  async fn find_all(&self) -> Result<Vec<Model>, ServerError> {
    let experiments = Entity::find().all(&self.pool).await?;
    Ok(experiments)
  }

  /// 指定されたIDの実験を削除
  /// * id: i64 - 削除する実験のID
  /// * 戻り値: Result<u64, ServerError> - 実験の削除件数
  async fn delete_from_id(&self, id: i64) -> Result<u64, ServerError> {
    let result = Entity::delete_by_id(id).exec(&self.pool).await?;
    // 削除件数が0件の場合はエラーを返す
    if result.rows_affected == 0 {
      return Err(ServerError::NotFound(format!(
        "Experiment with id {} not found",
        id
      )));
    }
    Ok(result.rows_affected)
  }
}

#[cfg(test)]
mod tests {
  use super::*;
  use crate::entities::experiment::ExperimentStatus;
  use crate::test_utils::create_experiment_request_factory;
  use sea_orm::SqlxPostgresConnector;

  /// DBテストの前処理
  async fn setup(pool: sqlx::PgPool) -> ExperimentRepository {
    // DB接続
    let db = SqlxPostgresConnector::from_sqlx_postgres_pool(pool);
    // リポジトリインスタンス作成
    ExperimentRepository::new(db)
  }

  /// 実験の作成テスト
  #[sqlx::test]
  async fn test_create(pool: sqlx::PgPool) {
    // Arrange
    let repository = setup(pool).await;
    let request = create_experiment_request_factory("test_experiment");
    let total = repository.find_all().await.unwrap().len();
    // Act
    let result = repository.create(request).await.unwrap();
    // Assert
    assert_eq!(result.name, "test_experiment"); // 実験名が一致する事
    assert_eq!(result.status, ExperimentStatus::Waiting); // デフォルトステータスがWAITINGである事
    let created_total = repository.find_all().await.unwrap().len();
    assert_eq!(created_total, total + 1); // 実験の数が1増えている事
  }

  /// 実験の結果更新テスト
  #[sqlx::test]
  async fn test_update(pool: sqlx::PgPool) {
    // Arrange
    let repository = setup(pool).await;
    let request = create_experiment_request_factory("test_experiment"); // 実験を作成
    let mut model = repository.create(request).await.unwrap();
    model.name = "test_experiment_updated".to_string(); // 実験名を更新
                                                        // Act
    let result = repository.update(model).await.unwrap();
    // Assert
    assert_eq!(result.name, "test_experiment_updated"); // 実験名が更新されている事
  }

  /// 実験の取得テスト
  #[sqlx::test]
  async fn test_find_by_id(pool: sqlx::PgPool) {
    // Arrange
    let repository = setup(pool).await;
    let request = create_experiment_request_factory("test_experiment");
    let result = repository.create(request).await.unwrap();
    // Act
    let result = repository.find_by_id(result.id).await.unwrap();
    // Assert
    assert_eq!(result.name, "test_experiment"); // 実験名が一致する事
  }

  /// 実験の一覧取得テスト
  #[sqlx::test]
  async fn test_find_all(pool: sqlx::PgPool) {
    // Arrange
    let repository = setup(pool).await;
    let request1 = create_experiment_request_factory("test_experiment1");
    let request2 = create_experiment_request_factory("test_experiment2");
    repository.create(request1).await.unwrap();
    repository.create(request2).await.unwrap();
    // Act
    let results = repository.find_all().await.unwrap();
    // Assert
    // テストデータのみ抽出
    let mut verifications = Vec::new();
    for result in results {
      if result.notes == Some("backend_test".to_string()) {
        verifications.push(result);
      }
    }
    assert_eq!(verifications.len(), 2); // テストデータの数が2件である事
    assert_eq!(verifications[0].name, "test_experiment1"); // 1件目の実験名が一致する事
    assert_eq!(verifications[1].name, "test_experiment2"); // 2件目の実験名が一致する事
  }

  /// 実験の削除テスト
  #[sqlx::test]
  async fn test_delete_from_id(pool: sqlx::PgPool) {
    // Arrange
    let repository = setup(pool).await;
    let request = create_experiment_request_factory("test_experiment");
    let result = repository.create(request).await.unwrap();
    let total = repository.find_all().await.unwrap().len();
    // Act
    let deleted_total = repository.delete_from_id(result.id).await.unwrap();
    // Assert
    assert_eq!(deleted_total, 1); // 削除された実験の数が1件である事
    let experiments = repository.find_all().await.unwrap();
    let deleted_total = experiments.len();
    assert_eq!(deleted_total, total - 1); // 実験の数が1減っている事
    assert!(!experiments
      .iter()
      .any(|experiment| experiment.id == result.id)); // 削除された実験が存在しない事
  }
}
