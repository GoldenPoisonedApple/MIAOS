use crate::dto::health::ReadinessResponse;
use crate::error::ServerError;
use crate::infrastructure::{ping_database, ping_redis, ping_storage};
use crate::state::HealthState;
use std::collections::HashMap;

/// リーディネスチェックを実行
pub async fn check_readiness(state: &HealthState) -> ReadinessResponse {
  // 非同期処理を並行実行
  let (db, redis, storage) = tokio::join!(
    ping_database(&state.db_pool),
    ping_redis(&state.redis_pool),
    ping_storage(&state.client, &state.bucket_name),
  );

  // チェック結果をハッシュマップに格納
  let mut checks = HashMap::new();
  checks.insert("database".to_string(), check_label(db));
  checks.insert("redis".to_string(), check_label(redis));
  checks.insert("storage".to_string(), check_label(storage));

  // 全てのチェックが成功したかどうかを判断
  let all_ok = checks.values().all(|s| s == "ok");
  let status = if all_ok {
    "ok".into()
  } else {
    "degraded".into()
  };
  // リーディネスレスポンスを返す
  ReadinessResponse { status, checks }
}

/// チェック結果のラベルを取得
fn check_label(result: Result<(), ServerError>) -> String {
  if result.is_ok() {
    "ok".into()
  } else {
    "error".into()
  }
}
