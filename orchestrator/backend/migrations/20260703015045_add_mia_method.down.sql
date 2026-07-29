-- Add down migration script here
-- online_lira を使用している行を offline_lira に戻す
UPDATE experiments
SET method = 'offline_lira'
WHERE method = 'online_lira';

-- PostgreSQL は ENUM 値の直接削除をサポートしないため、型を再作成する
CREATE TYPE mia_method_new AS ENUM (
    'offline_lira',
    'shokri'
);

ALTER TABLE experiments
  ALTER COLUMN method TYPE mia_method_new
  USING method::text::mia_method_new;

DROP TYPE mia_method;

ALTER TYPE mia_method_new RENAME TO mia_method;