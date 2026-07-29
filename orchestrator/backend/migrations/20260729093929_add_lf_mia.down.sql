-- Add down migration script here
-- lf_mia を使用している行を online_lira に戻す
UPDATE experiments
SET method = 'online_lira'
WHERE method = 'lf_mia';

-- PostgreSQL は ENUM 値の直接削除をサポートしないため、型を再作成する
CREATE TYPE mia_method_new AS ENUM (
    'offline_lira',
    'online_lira',
    'shokri'
);

ALTER TABLE experiments
  ALTER COLUMN method TYPE mia_method_new
  USING method::text::mia_method_new;

DROP TYPE mia_method;

ALTER TYPE mia_method_new RENAME TO mia_method;