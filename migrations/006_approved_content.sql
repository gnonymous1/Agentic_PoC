-- 006_approved_content.sql
-- Approved content store for few-shot learning and quality improvement.

CREATE TABLE IF NOT EXISTS approved_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    content_json JSONB NOT NULL,
    critic_cycles INTEGER DEFAULT 0,
    prompt_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
