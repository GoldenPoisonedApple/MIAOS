// src/test_utils.rs (共通モジュール)
#![cfg(test)]

use crate::repositories::task::{TaskRepository, TaskRepositoryTrait};
use crate::repositories::experiment::{ExperimentRepository, ExperimentRepositoryTrait};

/// テスト用の実験データをすべて削除する
pub async fn remove_test_experiments(experiment_repository: &ExperimentRepository) {
	let experiments = experiment_repository.find_all().await.unwrap();
	for experiment in experiments {
		if experiment.notes == Some("backend_test".to_string()) {
			experiment_repository.delete_from_id(experiment.id).await.unwrap();
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
