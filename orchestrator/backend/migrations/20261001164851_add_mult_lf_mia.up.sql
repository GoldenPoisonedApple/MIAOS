-- Add up migration script here
ALTER TYPE mia_method ADD VALUE IF NOT EXISTS 'lf_mult_mia';
ALTER TYPE mia_method ADD VALUE IF NOT EXISTS 'lf_mult_diff_mia';