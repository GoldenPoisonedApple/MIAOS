use crate::dto::health::{LivenessResponse, ReadinessResponse};
use crate::services::health::check_readiness;
use crate::state::HealthState;
use axum::{extract::State, http::StatusCode, Json};

/// ライブネスチェック
pub async fn liveness() -> (StatusCode, Json<LivenessResponse>) {
  (
    StatusCode::OK,
    Json(LivenessResponse {
      status: "ok".to_string(),
    }),
  )
}

/// リーディネスチェック
pub async fn readiness(
  State(health_state): State<HealthState>,
) -> (StatusCode, Json<ReadinessResponse>) {
  let response = check_readiness(&health_state).await;
  (StatusCode::OK, Json(response))
}
