#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy-common.sh
source "${SCRIPT_DIR}/deploy-common.sh"

cd worker

# 新イメージを取得
docker compose -f compose.base.yaml -f compose.deploy.yaml pull ito_research

# 現在のコンテナを graceful stop
#    SIGTERM → Celery warm shutdown（実行中タスク完了後に終了）
#    stop_grace_period をcompose.deploy.yamlで設定しておくこと
docker compose -f compose.base.yaml -f compose.deploy.yaml stop ito_research

# 新イメージで起動
docker compose -f compose.base.yaml -f compose.deploy.yaml up -d --no-deps --wait --wait-timeout 120 ito_research

prune_dangling_images
