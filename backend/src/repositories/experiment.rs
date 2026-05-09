use async_trait::async_trait;
use sea_orm::{DatabaseConnection, Set, ActiveModelTrait};

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
  ///
  /// 引数
  /// * `id` - 実験ID
  /// * `name` - 実験名
  /// * `notes` - 備考
  /// * `method` - 攻撃手法
  /// * `batch_size` - バッチサイズ
  /// * `max_epochs` - 最大エポック数
  /// * `num_shadow_models` - シャドウモデル数
  /// * `target_train_size` - ターゲットモデルのトレーニングサイズ
  /// * `target_test_size` - ターゲットモデルのテストサイズ
  /// * `shadow_train_size` - シャドウモデルのトレーニングサイズ
  /// * `shadow_test_size` - シャドウモデルのテストサイズ
  async fn create(
    &self,
    request: CreateExperimentRequest,
  ) -> Result<Model, sea_orm::DbErr> {
    // DTOをActiveModelに変換
    let active_model = ActiveModel::from(request);
    // データベースに保存 戻り値はResult<Model, sea_orm::DbErr>
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