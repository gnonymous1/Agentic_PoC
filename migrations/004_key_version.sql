-- 004_key_version.sql
-- Add key_version column to oauth_vault for key rotation support.

ALTER TABLE oauth_vault ADD COLUMN key_version INTEGER NOT NULL DEFAULT 1;
