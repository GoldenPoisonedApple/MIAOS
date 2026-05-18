// src/test_utils.rs (共通モジュール)
#![cfg(test)]

use std::sync::Once;

use crate::dto::experiment::{CreateExperimentRequest, UpdateResultsRequest};
use crate::entities::experiment::ExperimentStatus;
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

/// テスト用の実験結果を反映するrequestを作成する
pub fn update_experiment_request_factory(experiment_id: i64, status: ExperimentStatus) -> UpdateResultsRequest {
	let request = UpdateResultsRequest {
		experiment_id: experiment_id,
		worker_name: "test_worker".to_string(),
		global_auc: Some(0.5),
		tpr_at_1_fpr: Some(0.5),
		threshold_at_1_fpr: Some(0.5),
		tpr_at_01_fpr: Some(0.5),
		threshold_at_01_fpr: Some(0.5),
		other_metrics: serde_json::json!({}),
		total_time: Some(10.0),
		files: serde_json::json!({}),
		status: status,
		error_message: None,
	};
	request
}

/// テスト用の実験を作成するrequestを作成する
pub fn create_experiment_request_factory(name: &str) -> CreateExperimentRequest {
	let request = CreateExperimentRequest {
		name: name.to_string(),
		notes: Some("backend_test".to_string()),
		..Default::default()
	};

	request
}