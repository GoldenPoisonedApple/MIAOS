# Worker `src` パッケージ概要

MIAOS ワーカーは、Celery 経由で実験ジョブを受け取り、メンバーシップ推論攻撃（MIA）の実験を実行して結果を MinIO と MIAOS API に返す Python パッケージです。以下は `worker/src` 直下のディレクトリ構成と役割です。

## ディレクトリ構成

| パス | 役割 |
|------|------|
| `core/` | 環境変数・定数・実験パイプラインの中核 |
| `data/` | CIFAR-100 データセットの分割と DataLoader 構築 |
| `models/` | ターゲット CNN と Shokri 用の攻撃ネットワーク |
| `attacks/` | MIA の抽象基底クラスと具体手法（LiRA / Shokri） |
| `workers/` | Celery アプリとタスク定義 |
| `utils/` | MinIO（S3 互換）へのアップロード・ダウンロード |
| `server_client/` | MIAOS API 向けの自動生成 HTTP クライアントとモデル |

## 処理の流れ（エントリポイント）

1. **`workers/celery_tasks.py`** の Celery タスク `mia_tasks.run_attack`（`execute_attack_task`）が Redis ブローカーからパラメータを受け取る。
2. `Client(base_url=cfg.MIAOS_API_URL)` で API クライアントを生成し、`claim_experiment` で実験の受領を通知する。
3. **`main()`** が `CreateExperimentRequest.from_dict(params)` でリクエストを復元する。
4. `base_experiment_id` がある場合は **`utils/minio_utils.download_model_dir`** で先行実験のアーティファクトを `./cache/<experiment_id>/` に取得し、ターゲット／シャドウ／攻撃モデルや `dataset.json` の読み込み元とする。
5. **`core/pipeline.run_experiment`** を一時ディレクトリ上で実行し、成果物とメトリクスを得る。
6. **`minio_utils.upload_results_dir`** で一時ディレクトリ全体を MinIO の `{experiment_id}/` プレフィックス付きでアップロードする。
7. **`reflect_experiment_results`** で AUC・TPR・閾値・ファイル一覧などを API に POST する。例外時は `FAILED` と `error_message` を送る。

## `core/`

### `config.py`

- `python-dotenv` で `.env` を読み込み、Redis・MinIO・MIAOS API の URL／認証、ワーカー識別子 `PC_NAME` を設定する。
- `DEVICE` は CUDA が利用可能なら GPU、否则 CPU。
- データ・モデル保存の相対パス（`DATA_DIR`, `MODEL_DIR`, `LOCAL_CACHE_DIR`）と、保存ファイル名（`TARGET_MODEL_NAME` 等）、`NUM_CLASSES`（100）、`ATTACK_MODEL_EPOCHS` などを定義する。
- **`MIAMethod`** 列挙型はパイプライン外の参照用。実際の分岐は `server_client.models.MiaMethod`（API スキーマ側）と整合させている。

### `pipeline.py` — `run_experiment`

`CreateExperimentRequest` と作業ディレクトリ `work_dir`、オプションの `assigned_model_path`（ベース実験のキャッシュパス）、`experiment_id` を受け取り、以下のフェーズで進む。

1. **Phase 1**: `dataset` を構築し、`request.method` に応じて `MIA_LIRA` または `MIA_Shokri` を選択する。
2. **Phase 2**: ターゲットモデル `TargetCNN` を学習するか、`load_target_model` なら MinIO 由来の `target_model.pth` を読み込む。
3. **Phase 3**: シャドウモデルを複数学習するか、`load_shadow_model` なら `shadow_models.pth`（state_dict のリスト）から復元する。
4. **Phase 4**: 選択した MIA クラスの `attack()` でメンバーシップスコアと真値ラベルを得る。
5. **Phase 5**: `comprehensive_evaluate` で ROC・AUC・所定 FPR における TPR／閾値を計算し、`roc_curve.png` を `work_dir` に保存する。

ログは `work_dir/execution.log` と標準出力の両方に出力される。

**補足**: `attack()` の戻り値は `(スコア配列, 真値配列)` の順である。`pipeline` では変数名が `member_trues, member_scores` だが、実際に渡している第1引数はスコア、第2は真値であり、`MIA_Attack.comprehensive_evaluate(self, scores, trues)` の引数順と一致している。

## `data/`

### `dataset.py`

- CIFAR-100 の train+test を `ConcatDataset` として扱い、`CreateExperimentRequest` の `target_train_size` / `target_test_size` とシードでインデックスを分割する。
- 新規実験では `work_dir` に **`dataset.json`**（ターゲット学習・テスト・シャドウ用プールのインデックス）を書き出す。ベース実験がある場合は `assigned_model_path` 上の `dataset.json` を読み、同一のデータ分割を再現する。
- **`TransformedSubset`**: 学習用は拡張付き `transform_train`、テスト用は `transform_test`。評価・ロジット抽出用ローダー（`get_eval_*`）では、学習分割でも拡張を使わず `transform_test` で順序固定・shuffle 無効にする。
- シャドウ用は `shadow_pool_indices` から `shadow_train_size` / `shadow_test_size` と `seed + i` で毎シャドウ分割を生成する。

## `models/`

- **`target_model.TargetCNN`**: CIFAR-100（3×32×32、100 クラス）向けの畳み込み＋全結合ネットワーク。ターゲット・シャドウの両方に利用される。
- **`attack_model.AttackNet`**: Shokri 手法で、正解クラスに対応する確率ベクトル（次元 `NUM_CLASSES`）からメンバーシップを判定する 2 クラス用の小さな MLP。

## `attacks/`

### `mia_attack.MIA_Attack`（抽象クラス）

- ターゲット／シャドウの学習（AdamW + CosineAnnealingLR）、予測取得、精度計算、ROC 描画とメトリクス集計を共通化する。
- **`attack`** はサブクラスで実装する。シグネチャは実装側で `(shadow_models, target_model)` を受け取る。
- **`comprehensive_evaluate`**: `sklearn.metrics.roc_curve` / `auc` と対数軸の ROC 図保存。1%、0.1%、0.01% FPR 付近の TPR と閾値を算出する。

### `mia_lira.MIA_LIRA`

- Offline LiRA 系: シャドウモデル群で正解クラス確率のロジットを集め、メンバー／非メンバー分布の平均・標準偏差を推定し、ターゲットの z-score を攻撃スコアとする。
- スコア分布のヒストグラムを `score_distribution_lira.png` に保存する。

### `mia_shokri.MIA_Shokri`

- 各シャドウのメンバー／非メンバーについてソフトマックス出力を特徴とし、クラスごとに `AttackNet` を学習する。
- ターゲットの学習・テスト分割についてクラス別に攻撃モデルを適用し、メンバー確率をスコアとして ROC 用データを集約する。

## `utils/minio_utils.py`

- **`get_s3_client`**: `boto3` の S3 クライアントを `cfg.MINIO_URL` 等で構成する。
- **`download_model_dir(experiment_id)`**: バケット内 `"{experiment_id}/"` 配下を `./cache/` に再帰ダウンロード。サイズ一致の簡易キャッシュで再取得を省略可能。
- **`upload_results_dir(local_dir, remote_prefix)`**: ローカルディレクトリを走査し、`mimetypes` で `ContentType` を付与してアップロードする（`.log` は `text/plain` に登録済み）。

## `server_client/`

OpenAPI から生成された **httpx** ベースのクライアント群である。

- **`client.Client` / `AuthenticatedClient`**: 同期・非同期の HTTP セッション管理。
- **`models/`**: `CreateExperimentRequest`、`UpdateResultsRequest`、`MiaMethod`、`ExperimentStatus` など API の入出力型（attrs）。
- **`api/`**: `experiments`（作成・一覧・クレーム・結果反映・削除）、`tasks` などエンドポイントごとの `sync` / `asyncio` 関数。

ワーカー本体では主に `Client`、`CreateExperimentRequest`、`ClaimExperimentRequest`、`UpdateResultsRequest` 関連と、`claim_experiment` / `reflect_experiment_results` が使われる。

## 環境変数（`core/config.py` 参照）

実行前に `.env` などで次を設定する想定である。

- `PC_NAME`: ワーカー識別名（API 報告用）
- `REDIS_URL`: Celery ブローカー
- `MINIO_URL`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET_NAME`
- `MIAOS_API_URL`: オーケストレータ API のベース URL

## モジュール import について

コードは `src.` プレフィックス付きでパッケージを import している（例: `from src.core.pipeline import run_experiment`）。実行時はプロジェクトルートまたは `PYTHONPATH` に `worker` が含まれる構成を前提とする。

## 関連ファイル一覧（抜粋）

```
src/
├── README.md                 # 本ドキュメント
├── core/config.py
├── core/pipeline.py
├── data/dataset.py
├── models/target_model.py
├── models/attack_model.py
├── attacks/mia_attack.py
├── attacks/mia_lira.py
├── attacks/mia_shokri.py
├── workers/celery_tasks.py
├── utils/minio_utils.py
└── server_client/            # 生成クライアント一式
```
