# 分散タスク処理システム 設計書

## 1. システム全体像

本システムは、複数台のPCリソースを有効活用して機械学習やセキュリティ評価のプログラム（Membership Inference Attack等）を効率的に並列実行するための「マスター・ワーカー型」分散処理基盤です。

Celery + Redisをベースとし、共有ストレージへのアクセス制限やファイル競合問題を解決するために、ファイル入出力をMinIO経由で行うアーキテクチャを採用しています。

## 2. ノード構成と役割

### 2.1 マスターノード (ksl-v03: 133.44.75.128)
タスクの管理とデータの集約を担う専用のVM（仮想マシン）サーバーです。
* **Redis (キュー)**: タスクの実行条件と、ワーカーのキュー待ち行列を管理します。
* **MinIO (オブジェクトストレージ)**: `kslib` (NAS) をバックエンドの保存先としてマウントし、画像やモデルファイルなどの大きなバイナリデータを保存・配信します。（S3互換APIとして直接ワーカーから通信）
* **PostgreSQL (リレーショナルデータベース)**: 実行ごとのハイパーパラメータ、精度（メトリクス）、実行時間、ステータス、MinIO上のファイルパスなど、構造化されたデータを保存します。
* **Tracking API (Rust/Axum等のバックエンド)**: ワーカーから実行メタデータ（JSON）を受け取り、PostgreSQLに保存するためのAPIサーバー。DBとの直接の密結合を防ぎます。
* **可視化・管理サーバー (将来構築)**: タスクの投入や、情報を可視化するダッシュボード。（Tracking APIを拡張して実装可能）

### 2.2 ワーカーノード (nn01, nn02, nn11, t43)
タスクを取得し、実際の演算処理を行うPC群です。
* **Celeryワーカー (Dockerコンテナ)**:
  * 環境構築済みのDockerコンテナ内で起動しっぱなし（常駐）にします。
  * 本部(ksl-v03)のRedisを常に監視し、空きがあればタスクを取得します。
  * 実行時は、タスクごとにローカルディスク（`/tmp/task_<UUID>`など）に一時ディレクトリを作成し、共有ストレージ(NAS)上でのファイル競合を防ぎます。

## 3. ディレクトリ構成

コードの保守性と拡張性を高めるため、機能ごとにパッケージ分割された構成を採用しています。

```text
mia-dev/
 ┣ 📂 src/
 ┃ ┣ 📂 core/    (config.py, pipeline.py)
 ┃ ┣ 📂 attacks/ (mia_attack.py, mia_lira.py, mia_shokri.py)
 ┃ ┣ 📂 models/  (target_model.py, attack_model.py)
 ┃ ┣ 📂 data/    (dataset.py)
 ┃ ┣ 📂 utils/   (minio_utils.py)
 ┃ ┗ 📂 workers/ (celery_tasks.py)
 ┣ 📂 tests/     (test_celery.py)
 ┣ 📂 scripts/   (run_local.py)
 ┗ 📂 docs/      (system_architecture.md, command.bash 等)
```

## 4. タスク実行のワークフロー

1. **タスク投入**: ユーザーまたは管理スクリプトが、一意な `experiment_name`（タイムスタンプ等）を付与した実行条件をマスターのRedisに `send_task` で送信する。
2. **タスク取得**: 待機中のワーカー（Celery）がRedisから条件を取得する。
3. **環境準備 (キャッシュ機能)**: 
   * ワーカーはローカルの一時実行ディレクトリ（`tempfile.TemporaryDirectory`）を作成する。
   * 依存モデルの指定（`assigned_model_path`）がある場合、MinIOからローカルキャッシュにダウンロードし、パスを解決する。
4. **プログラム実行**: ワーカープロセス上で `pipeline.py` (run_experiment) が呼ばれ、機械学習の学習・攻撃・評価が実行される。結果はすべて一時ディレクトリに出力される。
5. **結果保存 (MinIOへのアップロード)**:
   * 実行が完了すると、一時ディレクトリ内のすべての成果物（モデル、ログ、画像等）がMinIOの `exp/<experiment_name>` 配下にアップロードされる。
6. **後処理**: 一時ディレクトリが削除され（自動クリーンアップ）、次のタスクを待機する。

## 5. 懸念事項の解決策（振り返り）
* **NASでのファイル衝突**: 実行時のファイル書き出しを各PCのローカルディスクに行うことで解決。
* **ネットワークアクセス制限**: `kslib` にアクセスできないPCも、ksl-v03に立てたMinIO(HTTP)を経由することでアクセス可能に。
* **モデルのアーキテクチャ互換性**: Dockerfileを共通化し、PyTorchのモデル保存・読み込みを `state_dict` 形式に統一。
* **GPUリソースの競合**: ワーカーのプロセス起動を `-P solo` に固定し、1コンテナ1タスクを保証。（PyTorchのCUDA初期化エラー防止策）
* **Boto3 (MinIO) のパースエラー**: S3クライアント（Connection）をアップロードごとに再生成することで通信エラーを回避。
* **ログ消失問題**: `run_experiment` の最後にタスク専用ロガーを確実に `flush()` および `close()` してからアップロードすることで解決。

---

### ToDo
- [ ] Tracking APIと連携し、MinIOやRedisから情報を読み取ってタスクの進捗を確認できるダッシュボードを作成する。

## 自分用メモ
- ワーカーの起動コマンド: `docker run --rm -it --gpus all -v $(pwd):/workspace -e PYTHONPATH=/workspace --env-file .env mia_worker:latest bash -c "celery -A src.workers.celery_tasks worker --loglevel=info -P solo"`
- テストタスクの送信: `python tests/test_celery.py`