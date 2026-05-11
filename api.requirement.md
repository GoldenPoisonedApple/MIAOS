# Tracking API 要求仕様書

## 1. 概要

本システム（Tracking API）は、複数台のワーカーPCで並列実行されている機械学習タスク（Membership Inference Attack）の実行結果やメタデータを受け取り、PostgreSQLデータベースに保存するためのバックエンドAPIです。
Rust (Axum等) を用いて構築し、マスターノード（ksl-v03: `133.44.75.128`）上でDockerコンテナとして稼働させることを想定しています。

## 2. 背景・目的

- ワーカー（Celery）が直接PostgreSQLに接続すると、並列実行時のコネクション逼迫やパスワード配布のセキュリティリスクが生じます。
- そのため、ワーカーはタスク完了時に本APIへJSON形式で結果をPOST送信し、API側で安全にDBへの書き込み（INSERT）を行うアーキテクチャとしています。

## 3. API仕様

### 3.1 タスク結果の保存

- **エンドポイント:** `POST /api/v1/tracking`
- **Content-Type:** `application/json`
- **想定されるリクエストボディ (JSON):**
Pythonのワーカーから以下のような構造のJSONが送信されます。

```json
{
  "worker_id": "nn11",
  "minio_path": "exp/2026-05-08_12-00-00_a1b2c3",
  "metrics": {
    "global_auc": 0.5432,
    "tpr_at_1_fpr": 0.0521,
    "tpr_at_01_fpr": 0.0065,
    "tpr_at_001_fpr": 0.0035,
    "threshold_at_1_fpr": 2.1245,
    "threshold_at_01_fpr": 4.7866,
    "threshold_at_001_fpr": 5.3627,
    "total_time_sec": 227.11
  },
  "artifacts": [
    "dataset.json",
    "execution.log",
    "roc_curve_Offline LiRA.png",
    "score_distribution_lira.png",
    "shadow_models.pth",
    "target_model.pth"
  ],
  "parameters": {
    "experiment_name": "2026-05-08_12-00-00_a1b2c3",
    "assigned_model_path": "",
    "notes": "test",
    "load_target_model": false,
    "load_shadow_models": false,
    "load_attack_models": false,
    "mia_method": "Offline LiRA",
    "num_shadow_models": 10,
    "num_classes": 100,
    "batch_size": 256,
    "max_epochs": 20,
    "num_workers": 0,
    "target_train_size": 10520,
    "target_test_size": 10520,
    "shadow_train_size": 10520,
    "shadow_test_size": 10520,
    "seed": 42
  }
}
```

### 3.2 期待されるレスポンス

- **成功時:** `200 OK` または `201 Created` (ボディは任意、例えば `{"status": "success"}`)
- **バリデーションエラー時:** `400 Bad Request`
- **サーバー内部エラー時:** `500 Internal Server Error`

## 4. データベース設計（テーブル定義案）

ダッシュボード等での一覧表示のしやすさ（SQLのJOINの手軽さ、見やすさ）を重視し、**「すべての手法で共通する情報をまとめたメインテーブル」** と **「攻撃手法ごとに特有のパラメータやファイル有無を持つ詳細テーブル」** に分ける設計（クラス継承パターン）を推奨します。

### テーブル1: `experiments` (全手法共通)

実験の基本情報、すべての攻撃手法で共通するパラメータ、および共通の評価指標・生成ファイル有無を管理します。一覧表示の際はこのテーブルをメインで参照します。


| カラム名                   | 型                | 制約               | 備考                             |
| ---------------------- | ---------------- | ---------------- | ------------------------------ |
| `id`                   | SERIAL (INT)     | PRIMARY KEY      |                                |
| `experiment_name`      | VARCHAR          | UNIQUE, NOT NULL | タスクの一意な名前                      |
| `worker_id`            | VARCHAR          | NOT NULL         | 実行したPC名 (例: nn11)              |
| `mia_method`           | VARCHAR          | NOT NULL         | 攻撃手法 (Offline LiRA, Shokri 等)  |
| `minio_path`           | VARCHAR          | NOT NULL         | MinIO上の保存先パス                   |
| `notes`                | TEXT             |                  | メモ                             |
| `assigned_model_path`  | VARCHAR          |                  | 指定されたモデルのパス                    |
| `load_target_model`    | BOOLEAN          | NOT NULL         |                                |
| `load_shadow_models`   | BOOLEAN          | NOT NULL         |                                |
| `load_attack_models`   | BOOLEAN          | NOT NULL         |                                |
| `num_classes`          | INT              | NOT NULL         |                                |
| `batch_size`           | INT              | NOT NULL         |                                |
| `max_epochs`           | INT              | NOT NULL         | ターゲット/シャドーモデルのエポック数            |
| `num_shadow_models`    | INT              | NOT NULL         |                                |
| `num_workers`          | INT              | NOT NULL         |                                |
| `target_train_size`    | INT              | NOT NULL         |                                |
| `target_test_size`     | INT              | NOT NULL         |                                |
| `shadow_train_size`    | INT              | NOT NULL         |                                |
| `shadow_test_size`     | INT              | NOT NULL         |                                |
| `seed`                 | INT              | NOT NULL         |                                |
| `global_auc`           | DOUBLE PRECISION |                  |                                |
| `tpr_at_1_fpr`         | DOUBLE PRECISION |                  |                                |
| `tpr_at_01_fpr`        | DOUBLE PRECISION |                  |                                |
| `tpr_at_001_fpr`       | DOUBLE PRECISION |                  |                                |
| `threshold_at_1_fpr`   | DOUBLE PRECISION |                  |                                |
| `threshold_at_01_fpr`  | DOUBLE PRECISION |                  |                                |
| `threshold_at_001_fpr` | DOUBLE PRECISION |                  |                                |
| `total_time_sec`       | DOUBLE PRECISION |                  |                                |
| `has_dataset_json`     | TEXT             |                  | `dataset.json` のパス             |
| `execution_log`        | TEXT             |                  | `execution.log` のパス            |
| `roc_curve_png`        | TEXT             | NOT NULL         | `roc_curve_{手法名}.png` のパス      |
| `target_model_pth`     | TEXT             |                  | `target_model.pth` のパス         |
| `shadow_models_pth`    | TEXT             |                  | `shadow_models.pth` のパス        |
| `created_at`           | TIMESTAMP        | DEFAULT NOW()    | レコード作成日時                       |
| `status`               | VARCHAR          | NOT NULL         | 待機(WAIT), 成功(SUCCESS), 失敗(ERR) |


### テーブル2: `details_offline_lira` (Offline LiRA専用)

`experiments` テーブルに紐づき、Offline LiRA固有の生成ファイル等を管理します。


| カラム名                         | 型            | 制約                  | 備考                                |
| ---------------------------- | ------------ | ------------------- | --------------------------------- |
| `id`                         | SERIAL (INT) | PRIMARY KEY         |                                   |
| `experiment_id`              | INT          | FOREIGN KEY, UNIQUE | `experiments.id` への外部キー(1対1)      |
| `has_score_distribution_png` | TEXT         | NOT NULL            | `score_distribution_lira.png` のパス |


### テーブル3: `details_shokri` (Shokri専用)

`experiments` テーブルに紐づき、Shokri攻撃固有のパラメータや生成ファイルを管理します。


| カラム名                    | 型            | 制約                  | 備考                           |
| ----------------------- | ------------ | ------------------- | ---------------------------- |
| `id`                    | SERIAL (INT) | PRIMARY KEY         |                              |
| `experiment_id`         | INT          | FOREIGN KEY, UNIQUE | `experiments.id` への外部キー(1対1) |
| `attack_model_epochs`   | INT          | NOT NULL            | Shokri専用パラメータ                |
| `has_attack_models_pth` | TEXT         | NOT NULL            | `attack_models.pth` のパス      |


### メリット

- **一覧表示のクリーンさ**: `SELECT * FROM experiments` をするだけで、どの手法の実験であっても共通で比較可能な情報が綺麗に取得できます。関係ない手法のパラメータがNULLとして大量に表示されることはありません。
- **拡張性**: 今後、新しい攻撃手法（例: `MIA_Custom`）を追加した場合も、`experiments` テーブルはいじらずに `details_custom` テーブルを新規作成するだけで対応可能です。

## 5. インフラ要件・非機能要件

- **言語/フレームワーク**: Rust (Axum 等を推奨)
- **実行環境**: Dockerコンテナ化し、ksl-v03サーバー上の既存の `docker-compose.yml` ネットワーク内にデプロイすること。
- **環境変数**: DBの接続文字列 (`DATABASE_URL`) 等はハードコードせず、環境変数から読み込むこと。
- **パフォーマンス要件**: ワーカーからのリクエスト頻度はそれほど高くない（1タスク数分〜数時間）ため、極端な高負荷対策は不要です。確実なエラーハンドリング（DB接続切れ時のリトライ等）を優先してください。

## 6. 今後の展望 (Phase 5向け)

APIの第一段階としては上記の `POST` エンドポイントのみで十分ですが、将来的にはダッシュボード（フロントエンド）から結果を一覧表示するための `GET /api/v1/experiments` エンドポイント等の追加をお願いする可能性があります。