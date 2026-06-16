-- =============================================================================
-- GNONE — Multi-Tenant B2B SaaS Schema
 -- Platform: PostgreSQL 16+
-- Extensions: pgcrypto, pgvector
-- =============================================================================

BEGIN;

-- ── Extensions ──────────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ── Enum Types ──────────────────────────────────────────────────────────────

CREATE TYPE session_status AS ENUM (
    'PENDING_REVIEW',
    'ACTIVE',
    'COMPLETED',
    'FAILED'
);

CREATE TYPE platform_enum AS ENUM (
    'META_GRAPH',
    'X_API',
    'GOOGLE_BLOGGER',
    'LINKEDIN_ENTERPRISE'
);

-- ═════════════════════════════════════════════════════════════════════════════
-- TABLE 1: clients           — Enterprise account management
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE clients (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_name            TEXT NOT NULL,
    org_slug            TEXT NOT NULL UNIQUE,
    billing_email       TEXT NOT NULL,
    subscription_tier   TEXT NOT NULL DEFAULT 'starter'
                            CHECK (subscription_tier IN ('starter', 'growth', 'enterprise')),
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    daily_content_quota INTEGER NOT NULL DEFAULT 50
                            CHECK (daily_content_quota > 0),
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_clients_org_slug ON clients (org_slug);
CREATE INDEX idx_clients_is_active ON clients (is_active) WHERE is_active = TRUE;

-- ═════════════════════════════════════════════════════════════════════════════
-- TABLE 2: oauth_vault       — Encrypted API authorization keys
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE oauth_vault (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    platform            platform_enum NOT NULL,
    platform_label      TEXT NOT NULL DEFAULT '',  -- human-friendly name, e.g. "Meta Business Suite — Acme FB Page"
    encrypted_token     BYTEA NOT NULL,            -- AES-256-GCM ciphertext
    encrypted_iv        BYTEA NOT NULL,            -- 12-byte IV used for GCM
    encrypted_tag       BYTEA NOT NULL,            -- 16-byte GCM authentication tag
    token_type          TEXT NOT NULL DEFAULT 'bearer',
    token_expires_at    TIMESTAMPTZ,
    refresh_token_hash  TEXT,                      -- SHA-256 hash of refresh token (not stored plaintext)
    scopes              TEXT[] DEFAULT '{}',
    is_revoked          BOOLEAN NOT NULL DEFAULT FALSE,
    last_used_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_oauth_vault_client ON oauth_vault (client_id, platform);
CREATE INDEX idx_oauth_vault_expiry ON oauth_vault (token_expires_at)
    WHERE token_expires_at IS NOT NULL AND is_revoked = FALSE;

/*
 * ── Architectural Note: AES-256-GCM Application-Level Encryption ───────────
 *
 * The `encrypted_token`, `encrypted_iv`, and `encrypted_tag` columns store
 * the raw bytes produced by AES-256-GCM.  PostgreSQL-side pgcrypto is NOT
 * used for OAuth secrets; encryption/decryption happens entirely at the
 * application layer so the database never holds the key.
 *
 * Recommended implementation pattern (Python / cryptography library):
 *
 *   from cryptography.hazmat.primitives.ciphers.aead import AESGCM
 *   import os
 *
 *   # Load 32-byte key from a hardware-backed vault (e.g. AWS KMS, Azure Key
 *   # Vault, HashiCorp Vault).  NEVER store the key in the database or in
 *   # application environment variables in plaintext.
 *   key: bytes = load_master_key_from_vault()
 *
 *   def encrypt_token(plaintext: str) -> tuple[bytes, bytes, bytes]:
 *       aesgcm = AESGCM(key)
 *       iv = os.urandom(12)          # 96-bit nonce
 *       ciphertext = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
 *       tag = ciphertext[-16:]        # last 16 bytes = auth tag
 *       ct = ciphertext[:-16]         # everything before = ciphertext
 *       return ct, iv, tag
 *
 *   def decrypt_token(ct: bytes, iv: bytes, tag: bytes) -> str:
 *       aesgcm = AESGCM(key)
 *       plaintext = aesgcm.decrypt(iv, ct + tag, None)
 *       return plaintext.decode("utf-8")
 *
 * Key rotation:
 *   - Keep a key_version column (INTEGER) referencing a versioned key ring.
 *   - On rotation, read each row, decrypt with the old key, re-encrypt with
 *     the new key, and increment key_version.
 *   - Zero-downtime rotation is achieved by allowing both old and new key
 *     versions during the transition window.
 */

-- ═════════════════════════════════════════════════════════════════════════════
-- TABLE 3: agent_profiles    — Custom agent configuration per client
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE agent_profiles (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    agent_name          TEXT NOT NULL,
    system_prompt       TEXT NOT NULL,               -- custom persona / voice instruction
    voice_clone_id      TEXT,                        -- ElevenLabs / Play.ht voice ID
    voice_speed         REAL DEFAULT 1.0
                            CHECK (voice_speed BETWEEN 0.5 AND 2.0),
    -- Strict business guardrails (validated at runtime by the critic engine)
    guardrails          JSONB NOT NULL DEFAULT '{
        "banned_phrases": [],
        "required_disclaimers": [],
        "min_negotiation_floor_price": 0,
        "max_negotiation_ceiling_price": 0,
        "allowed_platforms": [],
        "brand_tone": "professional",
        "geo_restrictions": []
    }'::jsonb,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_agent_profiles_client ON agent_profiles (client_id, is_active);

-- ═════════════════════════════════════════════════════════════════════════════
-- TABLE 4: proxy_sessions    — Real-time WebRTC meeting tracking
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE proxy_sessions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    agent_profile_id    UUID REFERENCES agent_profiles(id) ON DELETE SET NULL,
    recall_session_id   TEXT UNIQUE,                 -- Recall.ai container session ID
    livekit_room_name   TEXT,
    meeting_platform    TEXT NOT NULL DEFAULT 'zoom'
                            CHECK (meeting_platform IN ('zoom', 'google_meet', 'teams', 'webex')),
    meeting_title       TEXT,
    -- Status lifecycle
    status              session_status NOT NULL DEFAULT 'PENDING_REVIEW',
    started_at          TIMESTAMPTZ,
    ended_at            TIMESTAMPTZ,
    duration_seconds    INTEGER
                            CHECK (duration_seconds IS NULL OR duration_seconds > 0),
    -- Generated artifacts
    transcript_text     TEXT,                        -- full meeting transcript
    transcript_summary  TEXT,                        -- LLM-generated executive summary
    -- Revenue tracking
    revenue_closed      NUMERIC(12, 2) DEFAULT 0.00
                            CHECK (revenue_closed >= 0),
    deal_currency       TEXT DEFAULT 'USD',
    deal_stage          TEXT DEFAULT 'discovery'
                            CHECK (deal_stage IN ('discovery', 'negotiation', 'closed_won', 'closed_lost')),
    -- Metadata
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_proxy_sessions_client ON proxy_sessions (client_id, status);
CREATE INDEX idx_proxy_sessions_status ON proxy_sessions (status)
    WHERE status IN ('ACTIVE', 'PENDING_REVIEW');
CREATE INDEX idx_proxy_sessions_revenue ON proxy_sessions (revenue_closed DESC)
    WHERE status = 'COMPLETED' AND revenue_closed > 0;

-- ═════════════════════════════════════════════════════════════════════════════
-- TABLE 5: corporate_knowledge_vectors  — pgvector-powered semantic retrieval
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE corporate_knowledge_vectors (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    source_type         TEXT NOT NULL DEFAULT 'document'
                            CHECK (source_type IN (
                                'document', 'email_thread', 'meeting_transcript',
                                'contract_clause', 'playbook', 'faq', 'rfp_response'
                            )),
    title               TEXT NOT NULL,
    content_chunk       TEXT NOT NULL,               -- the raw text segment
    -- 1536-dimensional embedding (compatible with OpenAI / Gemini / Cohere)
    embedding           VECTOR(1536) NOT NULL,
    token_count         INTEGER NOT NULL DEFAULT 0
                            CHECK (token_count >= 0),
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- HNSW index for approximate nearest-neighbor search using cosine distance.
-- `vector_cosine_ops` provides the operator class for cosine similarity.
-- This index supports real-time (< 50 ms) semantic lookups during live
-- client calls, enabling the agent to retrieve relevant documentation
-- on the fly.
CREATE INDEX idx_corporate_knowledge_hnsw
    ON corporate_knowledge_vectors
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

CREATE INDEX idx_ckv_client_source
    ON corporate_knowledge_vectors (client_id, source_type);

-- ═════════════════════════════════════════════════════════════════════════════
-- Trigger: auto-update updated_at columns
-- ═════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_clients_updated_at
    BEFORE UPDATE ON clients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_oauth_vault_updated_at
    BEFORE UPDATE ON oauth_vault
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_agent_profiles_updated_at
    BEFORE UPDATE ON agent_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_proxy_sessions_updated_at
    BEFORE UPDATE ON proxy_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMIT;
