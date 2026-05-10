use async_trait::async_trait;
use sea_orm::{DatabaseConnection, ActiveModelTrait, ColumnTrait, QueryFilter, EntityTrait, Set};
use time::OffsetDateTime;

use crate::dto::experiment::{CreateExperimentRequest, UpdateResultsRequest};
use crate::entities::experiment::{ActiveModel, Model, Entity, ExperimentStatus};

#[async_trait] // 非同期関数を含むトレイト用のマクロ
pub trait ExperimentRepositoryTrait: Send + Sync {
  async fn create(&self, request: CreateExperimentRequest) -> Result<Model, sea_orm::DbErr>;
	async fn update_results(&self, request: UpdateResultsRequest) -> Result<Model, sea_orm::DbErr>;
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

	/// 実験の結果を更新
	/// * request: UpdateResultsRequest - 実験の結果更新リクエスト
	/// * 戻り値: Result<Model, sea_orm::DbErr> - 実験の結果更新結果
	async fn update_results(
		&self,
		request: UpdateResultsRequest,
	) -> Result<Model, sea_orm::DbErr> {
		let experiment_id = request.experiment_id; // 実験IDをキープ
		// DTOをActiveModelに変換
		let mut active_model = ActiveModel::from(request);
		// ステータスをSucceededに更新
		active_model.status = Set(ExperimentStatus::Succeeded);
		// 完了時刻セット
		active_model.completed_at = Set(Some(OffsetDateTime::now_utc()));
		// リクエストのIDに合致する実験を更新
		let result = active_model.update(&self.conn).await;
		match result {
			Ok(model) => Ok(model),
			Err(sea_orm::DbErr::RecordNotUpdated) => {
					// 更新対象が見つからなかった場合のエラーハンドリング
					Err(sea_orm::DbErr::RecordNotFound(format!("Experiment with id {} not found", experiment_id)))
			}
			Err(e) => Err(e),
		}
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
		// リポジトリインスタンス作成
		let repository = ExperimentRepository::new(conn);
		// テストデータの削除
		teardown(&repository).await;

		repository
	}

	/// 後処理
	async fn teardown(repository: &ExperimentRepository) {
		Entity::delete_many()
			.filter(Column::Notes.eq("backend_test"))
			.exec(&repository.conn).await.unwrap();
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
	/// requestファクトリ
	fn update_request(experiment_id: i64) -> UpdateResultsRequest {
		let request = UpdateResultsRequest {
			experiment_id: experiment_id,
			worker_name: "test_worker".to_string(),
			global_auc: 0.5,
			tpr_at_1_fpr: 0.5,
			tpr_at_01_fpr: 0.5,
			other_metrics: serde_json::json!({}),
			total_time: 10.0,
			minio_path: "test_minio_path".to_string(),
			dataset_json_path: "test_dataset_json_path".to_string(),
			execution_log_path: "test_execution_log_path".to_string(),
			other_files: serde_json::json!({}),
		};
		request
	}

	/// 実験の作成テスト
  #[tokio::test]
  async fn test_create() {

		// Arrange
		let repository = setup().await;
		let request = create_request("test_experiment");
		let total = repository.find_all().await.unwrap().len();
		// Act
		let result = repository.create(request).await.unwrap();
		// Assert
		assert_eq!(result.name, "test_experiment"); // 実験名が一致する事
		assert_eq!(result.status, ExperimentStatus::Waiting); // デフォルトステータスがWAITINGである事
		let created_total = repository.find_all().await.unwrap().len();
		assert_eq!(created_total, total + 1); // 実験の数が1増えている事
		teardown(&repository).await;
  }

	/// 実験の結果更新テスト
  #[tokio::test]
  async fn test_update_results() {
    // Arrange
    let repository = setup().await;
		let request = create_request("test_experiment"); // 実験を作成
		let result = repository.create(request).await.unwrap();
    let request = update_request(result.id); // リクエスト作成
    // Act
    let result = repository.update_results(request).await.unwrap();
		// Assert
		assert_eq!(result.status, ExperimentStatus::Succeeded); // ステータスがSUCCEEDEDである事
		assert!(result.completed_at.is_some()); // 完了時刻がセットされている事
		assert_eq!(result.worker_name, Some("test_worker".to_string())); // パラメータが更新されていること
		teardown(&repository).await;
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
		teardown(&repository).await;
  }

	/// 実験の削除テスト
  #[tokio::test]
  async fn test_delete_from_id() {
    // Arrange
    let repository = setup().await;
    let request = create_request("test_experiment");
    let result = repository.create(request).await.unwrap();
		let total = repository.find_all().await.unwrap().len();
    // Act
    let deleted_total = repository.delete_from_id(result.id).await.unwrap();
    // Assert
    assert_eq!(deleted_total, 1); // 削除された実験の数が1件である事
		let experiments = repository.find_all().await.unwrap();
		let deleted_total = experiments.len();
		assert_eq!(deleted_total, total - 1); // 実験の数が1減っている事
		assert!(!experiments.iter().any(|experiment| experiment.id == result.id)); // 削除された実験が存在しない事
		teardown(&repository).await;
  }
}