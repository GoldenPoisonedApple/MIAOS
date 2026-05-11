// src/test_utils.rs (共通モジュール)
#![cfg(test)]

use std::sync::Once;

use crate::repositories::experiment::{ExperimentRepository, ExperimentRepositoryTrait};
use crate::repositories::task::{TaskRepository, TaskRepositoryTrait};

static INIT: Once = Once::new();
/// テスト用のロガーを初期化する
/// テストでロガーを使いたい時はそのテストの先頭で呼び出す
pub fn init_test_logger() {
  INIT.call_once(|| {
    // テスト環境用のロガー設定
    let _ = tracing_subscriber::fmt()
      .with_env_filter("debug") // テスト時は強制的にdebugレベルにするなど
      .with_test_writer() // テストの標準出力と連携させる
      .try_init();
  });
}

/// テスト用の実験データをすべて削除する
pub async fn remove_test_experiments(experiment_repository: &ExperimentRepository) {
  let experiments = experiment_repository.find_all().await.unwrap();
  for experiment in experiments {
    if experiment.notes == Some("backend_test".to_string()) {
      experiment_repository
        .delete_from_id(experiment.id)
        .await
        .unwrap();
    }
  }
}

/// テスト用のタスクデータをすべて削除する
pub async fn remove_test_tasks(task_repository: &TaskRepository) {
  let tasks = task_repository.find_all_tasks().await.unwrap();
  for task in tasks {
    if task.args_keyword["_params"]["notes"].as_str().unwrap() == "backend_test" {
      task_repository.delete_by_id(task.id).await.unwrap();
    }
  }
}
