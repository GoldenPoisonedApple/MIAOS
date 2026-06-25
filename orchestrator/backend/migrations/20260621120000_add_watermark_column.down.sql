-- watermark を hyperparameters に戻す
UPDATE experiments
-- jsonb_build_object: キーと値を指定して JSONB オブジェクトを作成
-- ||: 左辺と右辺を結合
SET hyperparameters = hyperparameters || jsonb_build_object('watermark', watermark)
WHERE watermark != '{}'::jsonb; -- watermark が {} でない場合のみ更新

-- インデックス削除
DROP INDEX IF EXISTS idx_experiments_watermark;

-- カラム削除
ALTER TABLE experiments DROP COLUMN watermark;
