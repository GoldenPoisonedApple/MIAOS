#!/usr/bin/env bash
# デプロイ共通処理（orchestrator / worker で共有）
# 呼び出し元で git checkout 済み・カレントがリポジトリルートであること
set -euo pipefail

# 環境変数がセットされているか確認
: "${GITHUB_SHA:?GITHUB_SHA is required}"
: "${GITHUB_TOKEN:?GITHUB_TOKEN is required}"
: "${GITHUB_ACTOR:?GITHUB_ACTOR is required}"
: "${REGISTRY:?REGISTRY is required}"
: "${IMAGE_PREFIX:?IMAGE_PREFIX is required}"

# Docker image は大文字禁止: 小文字に変換
export IMAGE_PREFIX="${IMAGE_PREFIX,,}"
# CD Build が付与するタグと一致させる
export IMAGE_TAG="${GITHUB_SHA:0:7}"

# ghcr.ioにログイン
# --password-stdin: 標準入力からパスワードを読み込む セキュリティ上の利点: historyにパスワードが残らない
echo "$GITHUB_TOKEN" | docker login "$REGISTRY" -u "$GITHUB_ACTOR" --password-stdin

prune_dangling_images() {
  # 不要になったイメージの削除
  # -f: 強制的に削除
  # --filter "dangling=true": 未使用のイメージを削除
  docker image prune -f --filter "dangling=true"
}
