-- Add up migration script here
CREATE TYPE experiment_status AS ENUM (
    'WAITING',
    'RUNNING',
    'SUCCEEDED',
    'FAILED'
);
CREATE TYPE mia_method AS ENUM (
    'offline_lira',
    'shokri'
);


-- 実験条件
CREATE TABLE experiments (
	id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	name TEXT NOT NULL, -- 実験名
	notes TEXT, -- 備考
	method mia_method NOT NULL, -- 攻撃手法

	-- ----------------------------
	-- 条件
	-- ----------------------------
	batch_size INT NOT NULL, -- バッチサイズ
	max_epochs INT NOT NULL, -- 最大エポック数
	num_shadow_models INT NOT NULL, -- シャドウモデル数
	target_train_size INT NOT NULL, -- ターゲットモデルのトレーニングサイズ
	target_test_size INT NOT NULL, -- ターゲットモデルのテストサイズ
	shadow_train_size INT NOT NULL, -- シャドウモデルのトレーニングサイズ
	shadow_test_size INT NOT NULL, -- シャドウモデルのテストサイズ
	seed INT NOT NULL, -- シード値
	-- num_workers INT NOT NULL, -- worker数
	-- num_classes INT NOT NULL, -- クラス数
	-- その他のハイパーパラメータ
	hyperparameters JSONB NOT NULL DEFAULT '{}',

	-- ----------------------------
	-- データ流用
	-- ----------------------------
	-- 特定実行時のデータを流用し、実行効率化 条件と判断
	base_experiment_id BIGINT REFERENCES experiments(id), -- 既存実験結果を流用する実験結果
	load_target_model BOOLEAN NOT NULL DEFAULT FALSE, -- ターゲットモデルを読み込むかどうか
	load_shadow_model BOOLEAN NOT NULL DEFAULT FALSE, -- シャドウモデルを読み込むかどうか
	load_attack_model BOOLEAN NOT NULL DEFAULT FALSE, -- 攻撃モデルを読み込むかどうか

	-- ----------------------------
	-- 環境
	-- ----------------------------
	status experiment_status NOT NULL DEFAULT 'WAITING', -- ステータス
	worker_name TEXT, -- 作業PC名
	completed_at TIMESTAMPTZ, -- 完了日時
	error_message TEXT, -- エラーメッセージ

	-- ----------------------------
	-- 結果
	-- ----------------------------
	-- 実験後に送信されてくる実験結果
	global_auc DOUBLE PRECISION, -- 全体のAUC
	tpr_at_1_fpr DOUBLE PRECISION, -- 1%FPRでのTPR
	tpr_at_01_fpr DOUBLE PRECISION, -- 0.1%FPRでのTPR
	tpr_at_001_fpr DOUBLE PRECISION, -- 0.01%FPRでのTPR
	-- 拡張メトリクス (今後指標が増えた時用)
	other_metrics JSONB DEFAULT '{}', -- その他のメトリクス
	-- トータルの実行時間(秒)
	total_time DOUBLE PRECISION,

	-- ----------------------------
	-- ファイル
	-- ----------------------------
	-- 生成されたファイル群
	dataset_json_path TEXT, -- データセットのパス
	execution_log_path TEXT, -- 実行ログのパス
	other_files JSONB DEFAULT '{}', -- その他のファイルのパス

	-- メタ情報
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW() -- 作成日時
);

-- インデックス
CREATE INDEX idx_experiments_status ON experiments(status);
CREATE INDEX idx_experiments_method ON experiments (method);
CREATE INDEX idx_experiments_created_at ON experiments(created_at DESC);

-- JSONB内部の検索を高速化するGINインデックス
CREATE INDEX idx_experiments_hyperparameters ON experiments USING GIN (hyperparameters);
CREATE INDEX idx_experiments_other_metrics ON experiments USING GIN (other_metrics);