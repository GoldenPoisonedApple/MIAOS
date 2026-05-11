use crate::repositories::experiment::ExperimentRepository;
use crate::repositories::task::TaskRepository;
use crate::services::experiment::ExperimentService;
use std::sync::Arc;

// DIコンテナの役割を果たす
/// AppState: アプリケーションの状態を保持する
#[derive(Clone)]
pub struct AppState {
	/// 実験サービス
  // Serviceを#[derive(Clone)]で実装しても良いが、Cloneコストがあるので、Arc(可変アクセスを持たない)
  // リポジトリの中身は全てArcでラップされているので
  pub experiment_service: Arc<ExperimentService<ExperimentRepository, TaskRepository>>,
}
