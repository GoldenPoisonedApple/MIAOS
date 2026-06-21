use crate::repositories::experiment::ExperimentRepository;
use crate::repositories::storage::StorageRepository;
use crate::repositories::task::TaskRepository;
use crate::services::experiment::ExperimentService;
use crate::services::file::StorageService;
use crate::services::filter::FilterService;
use axum::extract::FromRef;
use sea_orm::DatabaseConnection;
use std::sync::Arc;

// DIコンテナの役割を果たす
/// AppState: アプリケーションの状態を保持する
#[derive(Clone)]
pub struct AppState {
  /// 実験サービス
  // Serviceを#[derive(Clone)]で実装しても良いが、Cloneコストがあるので、Arc(可変アクセスを持たない)
  // リポジトリの中身は全てArcでラップされているので
  pub experiment_service: Arc<ExperimentService<ExperimentRepository, TaskRepository>>,
  /// ストレージサービス
  pub storage_service: Arc<StorageService<StorageRepository>>,
  /// フィルタサービス
  pub filter_service: Arc<FilterService<StorageRepository>>,
}

// #[derive(FromRef)]で生成されるやつ
// forの型を要求されたときに生成する
// From: 所有権を消費
// FromRef: 所有権を保持しクローン
impl FromRef<AppState> for Arc<ExperimentService<ExperimentRepository, TaskRepository>> {
  fn from_ref(app: &AppState) -> Self {
    app.experiment_service.clone()
  }
}
impl FromRef<AppState> for Arc<StorageService<StorageRepository>> {
  fn from_ref(app: &AppState) -> Self {
    app.storage_service.clone()
  }
}
impl FromRef<AppState> for Arc<FilterService<StorageRepository>> {
  fn from_ref(app: &AppState) -> Self {
    app.filter_service.clone()
  }
}

/// ヘルスチェックの状態を保持する
#[derive(Clone)]
pub struct HealthState {
  pub db_pool: DatabaseConnection,
  pub redis_pool: deadpool_redis::Pool,
  pub client: aws_sdk_s3::Client,
  pub bucket_name: String,
}
