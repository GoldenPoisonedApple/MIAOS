-- Add down migration script here
DROP TABLE experiments;
DROP TYPE experiment_status;
DROP TYPE mia_method;

-- インデックスは自動的に削除されるらしい