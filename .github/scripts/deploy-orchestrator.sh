#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy-common.sh
source "${SCRIPT_DIR}/deploy-common.sh"

cd orchestrator

# 新イメージを取得
# upだけでも良いがpull失敗なのかbuild失敗なのかを切り分けられる
docker compose -f compose.base.yaml -f compose.deploy.yaml pull backend frontend

# サービスを再起動（既存コンテナを置き換え）
# --no-deps: 依存サービス(postgres等)は再起動しない
# --remove-orphans: 不要なコンテナを削除
docker compose -f compose.base.yaml -f compose.deploy.yaml \
  up -d --no-deps --remove-orphans backend frontend

# ヘルスチェック
docker compose -f compose.base.yaml -f compose.deploy.yaml up -d --wait --wait-timeout 120 backend

prune_dangling_images
