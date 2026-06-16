-- 005_content_cache.sql
-- Semantic content cache table for deduplication and fast retrieval.

CREATE TABLE IF NOT EXISTS content_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_hash TEXT NOT NULL,
    topic TEXT NOT NULL,
    brand_voice TEXT NOT NULL DEFAULT '',
    content_json JSONB NOT NULL,
    embedding VECTOR(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + interval '1 hour'
);

CREATE INDEX idx_content_cache_topic_hash ON content_cache (topic_hash);
