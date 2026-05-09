use async_trait::async_trait;
use sea_orm::{DatabaseConnection, ActiveModelTrait, Database, ConnectOptions};
use std::time::Duration;

use crate::dto::experiment::CreateExperimentRequest;
use crate::entities::experiment::{ActiveModel, Model};

#[cfg_attr(test, mockall::automock)]
#[async_trait] // 非同期関数を含むトレイト用のマクロ
pub trait ExperimentRepositoryTrait: Send + Sync {
  async fn create(
    &self,
    request: CreateExperimentRequest,
  ) -> Result<Model, sea_orm::DbErr>;
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

  // /// IDによる検索 (SELECT)
  // ///
  // /// 戻り値Option<Calligraphy>
  // async fn find_by_id(&self, user_id: Uuid) -> Result<Option<Calligraphy>, sqlx::Error> {
  //   sqlx::query_as!(
  //     Calligraphy,
  //     r#"
	// 					SELECT user_id, user_name, content, NULL::inet AS ip_address, NULL::text AS user_agent, NULL::varchar AS accept_language, created_at, updated_at
	// 					FROM calligraphy
	// 					WHERE user_id = $1
	// 					"#,
  //     user_id
  //   )
  //   .fetch_optional(&self.pool)
  //   .await
  // }

  // /// 全件取得 (一覧表示用)
  // ///
  // /// 作成日時の新しい順（降順）で取得する。
  // async fn find_all(&self) -> Result<Vec<Calligraphy>, sqlx::Error> {
  //   sqlx::query_as!(
  //     Calligraphy,
  //     r#"
  //           SELECT user_id, user_name, content, NULL::inet AS ip_address, NULL::text AS user_agent, NULL::varchar AS accept_language, created_at, updated_at
  //           FROM calligraphy
  //           ORDER BY created_at DESC
  //           LIMIT 100 -- 安全のため上限を設定（必要に応じてページネーションに変更）
  //           "#
  //   )
  //   .fetch_all(&self.pool)
  //   .await
  // }

  // /// 削除
  // /// 戻り値は影響を受けた行数
  // async fn delete(&self, user_id: Uuid) -> Result<u64, sqlx::Error> {
  //   let result = sqlx::query!(
  //     r#"
	// 		DELETE FROM calligraphy
	// 		WHERE user_id = $1
	// 		"#,
  //     user_id
  //   )
  //   .execute(&self.pool)
  //   .await?;

  //   Ok(result.rows_affected())
  // }
}


#[cfg(test)]
mod tests {
  use super::*;
	use sea_orm::{EntityTrait, ColumnTrait, QueryFilter};
  use crate::entities::experiment::{MiaMethod, ExperimentStatus, Entity, Column};

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

  #[tokio::test]
  async fn test_create_experiment() {

		// Arrange
		let repository = setup().await;
		let request = CreateExperimentRequest {
			name: "test_experiment".to_string(),
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
		// Act
		let result = repository.create(request).await.unwrap();
		// Assert
		assert_eq!(result.name, "test_experiment");
		assert_eq!(result.status, ExperimentStatus::Waiting);
  }
}