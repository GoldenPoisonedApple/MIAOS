use crate::dto::experiment::CreateExperimentRequest;
use crate::entities::experiment::Model;

use crate::repositories::experiment::ExperimentRepositoryTrait;

/// ビジネスロジックを担当するサービス
pub struct ExperimentService<R: ExperimentRepositoryTrait> {
	repository: R,
}

impl<R: ExperimentRepositoryTrait> ExperimentService<R> {
	pub fn new(repository: R) -> Self {
		Self { repository }
	}

	/// 実験の作成
	/// * request: CreateExperimentRequest - 実験の作成リクエスト
	/// * 戻り値: Result<Model, sea_orm::DbErr> - 実験の作成結果
	pub async fn create(&self, request: CreateExperimentRequest) -> Result<Model, sea_orm::DbErr> {
		let result = self.repository.create(request).await?;
		Ok(result)
	}
}