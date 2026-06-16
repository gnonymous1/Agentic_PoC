-- =============================================================================
-- GNONE — Webhook Subscription Management
-- Platform: PostgreSQL 16+
-- =============================================================================

BEGIN;

-- ═════════════════════════════════════════════════════════════════════════════
-- TABLE 1: webhook_subscriptions  — Registered webhook endpoints per client
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE webhook_subscriptions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    url                 TEXT NOT NULL
                            CHECK (url ~ '^https?://'),
    description         TEXT,
    secret              TEXT NOT NULL DEFAULT encode(gen_random_bytes(32), 'hex'),
    events              TEXT[] NOT NULL
                            CHECK (array_length(events, 1) > 0),
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    content_type        TEXT NOT NULL DEFAULT 'application/json'
                            CHECK (content_type IN ('application/json', 'application/x-www-form-urlencoded')),
    retry_policy        JSONB NOT NULL DEFAULT '{
        "max_retries": 3,
        "backoff_multiplier": 2,
        "initial_delay_seconds": 5,
        "timeout_seconds": 30
    }'::jsonb,
    headers             JSONB DEFAULT '{}',
    last_triggered_at   TIMESTAMPTZ,
    last_success_at     TIMESTAMPTZ,
    last_failure_at     TIMESTAMPTZ,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_webhook_subs_client ON webhook_subscriptions (client_id, active);
CREATE INDEX idx_webhook_subs_events ON webhook_subscriptions USING GIN (events);
CREATE INDEX idx_webhook_subs_failures ON webhook_subscriptions (consecutive_failures DESC)
    WHERE consecutive_failures > 0;

-- ═════════════════════════════════════════════════════════════════════════════
-- TABLE 2: webhook_deliveries    — Delivery attempt log for audit & replay
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE webhook_deliveries (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id     UUID NOT NULL REFERENCES webhook_subscriptions(id) ON DELETE CASCADE,
    event_type          TEXT NOT NULL,
    payload             JSONB NOT NULL,
    attempt_number      INTEGER NOT NULL DEFAULT 1
                            CHECK (attempt_number > 0),
    status              TEXT NOT NULL
                            CHECK (status IN ('pending', 'delivered', 'failed', 'cancelled')),
    http_status_code    INTEGER,
    response_body       TEXT,
    error_message       TEXT,
    request_headers     JSONB,
    response_headers    JSONB,
    sent_at             TIMESTAMPTZ,
    responded_at        TIMESTAMPTZ,
    next_retry_at       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_webhook_deliveries_sub ON webhook_deliveries (subscription_id, status);
CREATE INDEX idx_webhook_deliveries_event ON webhook_deliveries (event_type);
CREATE INDEX idx_webhook_deliveries_pending ON webhook_deliveries (status, next_retry_at)
    WHERE status = 'pending' AND next_retry_at IS NOT NULL;
CREATE INDEX idx_webhook_deliveries_created ON webhook_deliveries (created_at DESC);

-- ═════════════════════════════════════════════════════════════════════════════
-- TABLE 3: webhook_event_types   — Registry of supported event types
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE webhook_event_types (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_name          TEXT NOT NULL UNIQUE,
    description         TEXT,
    payload_schema      JSONB,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed supported event types
INSERT INTO webhook_event_types (event_name, description) VALUES
    ('content.generated', 'New content piece has been generated'),
    ('content.approved', 'Content passed critic review and was approved'),
    ('content.published', 'Content was published to a platform'),
    ('content.rejected', 'Content failed critic review'),
    ('session.started', 'A new meeting proxy session has started'),
    ('session.completed', 'A meeting proxy session has completed'),
    ('session.revenue_closed', 'Revenue was attributed to a session'),
    ('agent.error', 'An agent encountered a critical error'),
    ('token.expiring', 'An OAuth token is expiring within 24 hours'),
    ('quota.warning', 'Client daily content quota is above 80%'),
    ('quota.exceeded', 'Client has exceeded daily content quota'),
    ('health.degraded', 'System health check reported degradation'),
    ('billing.invoice_created', 'A new billing invoice was generated'),
    ('webhook.delivery_failed', 'Webhook delivery failed after all retries');

-- ═════════════════════════════════════════════════════════════════════════════
-- Function: Get pending deliveries for retry
-- ═════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION get_pending_webhook_deliveries(
    p_limit INTEGER DEFAULT 100
)
RETURNS TABLE (
    id UUID,
    subscription_id UUID,
    url TEXT,
    secret TEXT,
    event_type TEXT,
    payload JSONB,
    attempt_number INTEGER,
    retry_policy JSONB,
    content_type TEXT,
    headers JSONB
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        wd.id,
        wd.subscription_id,
        ws.url,
        ws.secret,
        wd.event_type,
        wd.payload,
        wd.attempt_number,
        ws.retry_policy,
        ws.content_type,
        ws.headers
    FROM webhook_deliveries wd
    JOIN webhook_subscriptions ws ON ws.id = wd.subscription_id
    WHERE wd.status = 'pending'
      AND ws.active = TRUE
      AND (wd.next_retry_at IS NULL OR wd.next_retry_at <= now())
    ORDER BY wd.created_at ASC
    LIMIT p_limit;
END;
$$;

-- ═════════════════════════════════════════════════════════════════════════════
-- Function: Create a webhook delivery record
-- ═════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION create_webhook_delivery(
    p_subscription_id UUID,
    p_event_type TEXT,
    p_payload JSONB
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_id UUID;
BEGIN
    INSERT INTO webhook_deliveries (subscription_id, event_type, payload)
    VALUES (p_subscription_id, p_event_type, p_payload)
    RETURNING id INTO v_id;

    UPDATE webhook_subscriptions
    SET last_triggered_at = now()
    WHERE id = p_subscription_id;

    RETURN v_id;
END;
$$;

-- ═════════════════════════════════════════════════════════════════════════════
-- Function: Update delivery status after attempt
-- ═════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION update_webhook_delivery_status(
    p_delivery_id UUID,
    p_status TEXT,
    p_http_status_code INTEGER DEFAULT NULL,
    p_response_body TEXT DEFAULT NULL,
    p_error_message TEXT DEFAULT NULL,
    p_next_retry_at TIMESTAMPTZ DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_subscription_id UUID;
    v_attempt_number INTEGER;
BEGIN
    UPDATE webhook_deliveries
    SET
        status = p_status,
        http_status_code = p_http_status_code,
        response_body = p_response_body,
        error_message = p_error_message,
        next_retry_at = p_next_retry_at,
        responded_at = CASE WHEN p_status IN ('delivered', 'failed') THEN now() ELSE responded_at END,
        sent_at = CASE WHEN sent_at IS NULL THEN now() ELSE sent_at END
    WHERE id = p_delivery_id
    RETURNING subscription_id, attempt_number INTO v_subscription_id, v_attempt_number;

    IF p_status = 'delivered' THEN
        UPDATE webhook_subscriptions
        SET
            last_success_at = now(),
            consecutive_failures = 0
        WHERE id = v_subscription_id;
    ELSIF p_status = 'failed' THEN
        UPDATE webhook_subscriptions
        SET
            last_failure_at = now(),
            consecutive_failures = consecutive_failures + 1
        WHERE id = v_subscription_id;
    END IF;
END;
$$;

-- ═════════════════════════════════════════════════════════════════════════════
-- Function: Find subscriptions for a given event
-- ═════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION find_subscriptions_for_event(
    p_client_id UUID,
    p_event_type TEXT
)
RETURNS TABLE (
    id UUID,
    url TEXT,
    secret TEXT,
    content_type TEXT,
    headers JSONB,
    retry_policy JSONB
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN QUERY
    SELECT ws.id, ws.url, ws.secret, ws.content_type, ws.headers, ws.retry_policy
    FROM webhook_subscriptions ws
    WHERE ws.client_id = p_client_id
      AND ws.active = TRUE
      AND p_event_type = ANY(ws.events);
END;
$$;

-- ═════════════════════════════════════════════════════════════════════════════
-- Trigger: Auto-update updated_at
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TRIGGER trg_webhook_subs_updated_at
    BEFORE UPDATE ON webhook_subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMIT;
