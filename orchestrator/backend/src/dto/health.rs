use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Serialize, Deserialize)]
pub struct LivenessResponse {
  pub status: String, // "ok" | "error"
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ReadinessResponse {
  pub status: String,           // "ok" | "degraded"
  pub checks: HashMap<String, String>,  // "database" -> "ok" | "error"
}