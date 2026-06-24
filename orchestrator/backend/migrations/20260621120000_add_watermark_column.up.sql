-- カラム追加
ALTER TABLE experiments
  ADD COLUMN watermark JSONB NOT NULL DEFAULT '{}';

-- 既存データの透かし設定を移行
UPDATE experiments
SET
	-- 抽出
  watermark = hyperparameters->'watermark',
	-- hyperparameters から watermark を削除
  hyperparameters = hyperparameters - 'watermark'
WHERE hyperparameters ? 'watermark'; -- hyperparameters に watermark が存在する場合のみ更新

-- インデックス追加
CREATE INDEX idx_experiments_watermark ON experiments USING GIN (watermark);
