use celery::prelude::*;
use serde::{Deserialize, Serialize};
use crate::dto::task::CreateTaskRequest;
use crate::entities::experiment::MiaMethod;

// Pythonのタスク名と一致させる
#[celery::task(name = "mia_tasks.run_attack")]
async fn run_attack(params: CreateTaskRequest) {}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let app = celery::app!(
        broker = RedisBroker { std::env::var("REDIS_URL").unwrap() },
        tasks = [run_attack],
				task_routes = []
    ).await?;

    let params = CreateTaskRequest {
        experiment_id: 1,
        name: "test".to_string(),
        notes: Some("test".to_string()),
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

    app.send_task(run_attack::new(params)).await?;

    Ok(())
}