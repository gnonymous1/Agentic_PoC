-- =============================================================================
-- GNONE — Analytics & Audit Tables
-- Schema version: 002
-- =============================================================================

BEGIN;

-- ═════════════════════════════════════════════════════════════════════════════
-- TABLE 6: content_analytics_events  — Immutable event log for BI
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE content_analytics_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    event_type      TEXT NOT NULL CHECK (event_type IN (
                        'content_generated', 'content_approved',
                        'content_rejected', 'content_published',
                        'critic_cycle', 'error'
                    )),
    platform        TEXT,
    model_used      TEXT,
    latency_ms      NUMERIC(10, 2),
    token_count     INTEGER CHECK (token_count IS NULL OR token_count >= 0),
    refinement_cycle INTEGER NOT NULL DEFAULT 0,
    approved        BOOLEAN,
    error_type      TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
) PARTITION BY RANGE (created_at);

CREATE INDEX idx_analytics_client_event
    ON content_analytics_events (client_id, event_type, created_at DESC);

-- Monthly partitions for the analytics events table
CREATE TABLE content_analytics_events_2026_05
    PARTITION OF content_analytics_events
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

CREATE TABLE content_analytics_events_2026_06
    PARTITION OF content_analytics_events
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

-- ═════════════════════════════════════════════════════════════════════════════
-- TABLE 7: cost_tracking  — Model usage and cost per request
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE cost_tracking (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    request_id      TEXT NOT NULL,
    model           TEXT NOT NULL,
    tokens_input    INTEGER NOT NULL CHECK (tokens_input >= 0),
    tokens_output   INTEGER NOT NULL CHECK (tokens_output >= 0),
    estimated_cost  NUMERIC(12, 6) NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_cost_tracking_client
    ON cost_tracking (client_id, created_at DESC);
CREATE INDEX idx_cost_tracking_model
    ON cost_tracking (model, created_at DESC);

-- ═════════════════════════════════════════════════════════════════════════════
-- TABLE 8: audit_log  — Immutable audit trail for compliance
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_type      TEXT NOT NULL CHECK (actor_type IN ('client', 'system', 'admin')),
    actor_id        TEXT NOT NULL,
    action          TEXT NOT NULL,
    resource_type   TEXT NOT NULL,
    resource_id     TEXT,
    details         JSONB DEFAULT '{}',
    ip_address      INET,
    correlation_id  UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_actor
    ON audit_log (actor_type, actor_id, created_at DESC);
CREATE INDEX idx_audit_resource
    ON audit_log (resource_type, resource_id, created_at DESC);
CREATE INDEX idx_audit_correlation
    ON audit_log (correlation_id);

-- ═════════════════════════════════════════════════════════════════════════════
-- TABLE 9: api_usage_quotas  — Daily and monthly usage tracking
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE api_usage_quotas (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    date            DATE NOT NULL,
    model           TEXT NOT NULL,
    requests_count  INTEGER NOT NULL DEFAULT 0,
    tokens_total    BIGINT NOT NULL DEFAULT 0,
    UNIQUE (client_id, date, model)
);

CREATE INDEX idx_quota_client_date
    ON api_usage_quotas (client_id, date DESC);

COMMIT;
