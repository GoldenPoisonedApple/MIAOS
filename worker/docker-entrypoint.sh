#!/bin/bash
# -e: エラーが発生したらスクリプトを終了
# -u: 未定義の変数が使用されたらエラー
# -o pipefail: パイプラインのエラーをキャッチ
set -euo pipefail

# ボリュームのマウント先（無ければ作成）
mkdir -p /workspace/data /workspace/cache

# 名前付きボリュームは root 所有のためappuser に揃える
chown -R appuser:appuser /workspace/data /workspace/cache

# 以降は非 root で本来のコマンド（celery）を実行
# "$@" スクリプトに渡された全ての変数
exec gosu appuser "$@"