use async_trait::async_trait;
use sea_orm::{DatabaseConnection, ActiveModelTrait, ColumnTrait, QueryFilter, EntityTrait};

use crate::dto::experiment::CreateExperimentRequest;
use crate::entities::experiment::{ActiveModel, Model, Entity};

#[async_trait] // 非同期関数を含むトレイト用のマクロ
pub trait ExperimentRepositoryTrait: Send + Sync {
  async fn create(
    &self,
    request: CreateExperimentRequest,
  ) -> Result<Model, sea_orm::DbErr>;
	async fn find_all(&self) -> Result<Vec<Model>, sea_orm::DbErr>;
	async fn delete_from_id(&self, id: i64) -> Result<u64, sea_orm::DbErr>;
}

/// Experimentsテーブルへのアクセスを担当するリポジトリ
/// DatabaseConnectionは内部でArc(参照カウント)を使用しているため、Cloneコストは低い
#[derive(Clone)]
pub struct ExperimentRepository {
  conn: DatabaseConnection,
}

impl ExperimentRepository {
  /// コンストラクタ
  pub fn new(conn: DatabaseConnection) -> Self {
    Self { conn }
  }
}

#[async_trait]
impl ExperimentRepositoryTrait for ExperimentRepository {
  /// 新規実験の作成 (INSERT)
	/// * request: CreateExperimentRequest - 実験の作成リクエスト
	/// * 戻り値: Result<Model, sea_orm::DbErr> - 実験の作成結果
  async fn create(
		&self,
		request: CreateExperimentRequest,
	) -> Result<Model, sea_orm::DbErr> {
    // DTOをActiveModelに変換
    let active_model = ActiveModel::from(request);
    // データベースに保存 戻り値はResult<Model, sea_orm::DbErr> 戻り値はResult<Model, sea_orm::DbErr>
    active_model.insert(&self.conn).await
  }

	/// すべての実験を取得
	/// * 戻り値: Result<Vec<Model>, sea_orm::DbErr> - 実験の一覧取得結果
	async fn find_all(&self) -> Result<Vec<Model>, sea_orm::DbErr> {
		let experiments = Entity::find().all(&self.conn).await?;
		Ok(experiments)
	}

	/// 指定されたIDの実験を削除
	/// * id: i64 - 削除する実験のID
	/// * 戻り値: Result<u64, sea_orm::DbErr> - 実験の削除件数
	async fn delete_from_id(&self, id: i64) -> Result<u64, sea_orm::DbErr> {
		let result = Entity::delete_by_id(id).exec(&self.conn).await?;
		// 削除件数が0件の場合はエラーを返す
		if result.rows_affected == 0 {
			return Err(sea_orm::DbErr::RecordNotFound("Experiment not found".to_string()));
		}
		Ok(result.rows_affected)
	}
}


#[cfg(test)]
mod tests {
  use super::*;
	use sea_orm::{Database, ConnectOptions};
	use std::time::Duration;

  use crate::entities::experiment::{MiaMethod, ExperimentStatus, Column};


	/// DBテストの前処理
	async fn setup() -> ExperimentRepository {
		// DB接続
		let database_url = std::env::var("DATABASE_URL").expect("DATABASE_URL must be set");
		let mut connect_options = ConnectOptions::new(database_url);
		connect_options.max_connections(1)
			.min_connections(1)
			.acquire_timeout(Duration::from_secs(10))
			.connect_timeout(Duration::from_secs(10))
			.idle_timeout(Duration::from_secs(10))
			.max_lifetime(Duration::from_secs(10))
			.sqlx_logging(true);	// 実行されたSQLのログ出力
		let conn = Database::connect(connect_options).await.unwrap();
		tracing::info!("Connected to database via SeaORM");
		// テストデータの削除
		Entity::delete_many()
			.filter(Column::Notes.eq("backend_test"))
			.exec(&conn).await.unwrap();
		// リポジトリインスタンス作成
		let repository = ExperimentRepository::new(conn);

		repository
	}

	/// requestファクトリー
	fn create_request(name: &str) -> CreateExperimentRequest {
		let request = CreateExperimentRequest {
			name: name.to_string(),
			notes: Some("backend_test".to_string()),
			method: MiaMethod::OfflineLira,
			batch_size: 10,
			max_epochs: 10,
			num_shadow_models: 10,
			target_train_size: 10,
			target_test_size: 10,
			shadow_train_size: 10,
			shadow_test_size: 10,
			seed: 10,
			hyperparameters: serde_json::json!({}),
			base_experiment_id: None,
			load_target_model: false,
			load_shadow_model: false,
			load_attack_model: false,
		};

		request
	}

	/// 実験の作成テスト
  #[tokio::test]
  async fn test_create() {

		// Arrange
		let repository = setup().await;
		let request = create_request("test_experiment");
		// Act
		let result = repository.create(request).await.unwrap();
		// Assert
		assert_eq!(result.name, "test_experiment");
		assert_eq!(result.status, ExperimentStatus::Waiting);
  }

	/// 実験の一覧取得テスト
  #[tokio::test]
  async fn test_find_all() {
    // Arrange
    let repository = setup().await;
		let request1 = create_request("test_experiment1");
		let request2 = create_request("test_experiment2");
		repository.create(request1).await.unwrap();
		repository.create(request2).await.unwrap();
    // Act
    let result = repository.find_all().await.unwrap();
    // Assert
    assert_eq!(result.len(), 2);
    assert_eq!(result[0].name, "test_experiment1");
    assert_eq!(result[1].name, "test_experiment2");
  }

	/// 実験の削除テスト
  #[tokio::test]
  async fn test_delete_from_id() {
    // Arrange
    let repository = setup().await;
    let request = create_request("test_experiment");
    let result = repository.create(request).await.unwrap();
    // Act
    let result = repository.delete_from_id(result.id).await.unwrap();
    // Assert
    assert_eq!(result, 1);
  }
}