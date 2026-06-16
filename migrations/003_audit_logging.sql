-- =============================================================================
-- GNONE — Advanced Audit, Retention, and Security Policies
-- Schema version: 003
-- =============================================================================

BEGIN;

-- ═════════════════════════════════════════════════════════════════════════════
-- Row-Level Security (RLS) — Multi-tenant data isolation
-- ═════════════════════════════════════════════════════════════════════════════

ALTER TABLE oauth_vault ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE proxy_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE corporate_knowledge_vectors ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_analytics_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE cost_tracking ENABLE ROW LEVEL SECURITY;

-- RLS policies ensure clients can only see their own data
CREATE POLICY tenant_isolation_oauth_vault
    ON oauth_vault
    USING (client_id = current_setting('app.current_client_id')::UUID);

CREATE POLICY tenant_isolation_agent_profiles
    ON agent_profiles
    USING (client_id = current_setting('app.current_client_id')::UUID);

CREATE POLICY tenant_isolation_proxy_sessions
    ON proxy_sessions
    USING (client_id = current_setting('app.current_client_id')::UUID);

CREATE POLICY tenant_isolation_knowledge_vectors
    ON corporate_knowledge_vectors
    USING (client_id = current_setting('app.current_client_id')::UUID);

CREATE POLICY tenant_isolation_analytics
    ON content_analytics_events
    USING (client_id = current_setting('app.current_client_id')::UUID);

CREATE POLICY tenant_isolation_cost
    ON cost_tracking
    USING (client_id = current_setting('app.current_client_id')::UUID);

-- ═════════════════════════════════════════════════════════════════════════════
-- Automated Data Retention — Drop partitions older than 90 days
-- ═════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION drop_old_analytics_partitions()
RETURNS void AS $$
DECLARE
    partition_name TEXT;
BEGIN
    FOR partition_name IN
        SELECT inhrelid::regclass::text
        FROM pg_inherits
        WHERE inhparent = 'content_analytics_events'::regclass
          AND split_part(inhrelid::regclass::text, '_', -2) || '-' ||
              split_part(inhrelid::regclass::text, '_', -1) || '-01'::date
              < now() - interval '90 days'
    LOOP
        EXECUTE format('DROP TABLE IF EXISTS %I', partition_name);
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ═════════════════════════════════════════════════════════════════════════════
-- Trigger: auto-partition analytics on insert
-- ═════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION auto_create_analytics_partition()
RETURNS TRIGGER AS $$
DECLARE
    partition_date  DATE;
    partition_name  TEXT;
    partition_start TEXT;
    partition_end   TEXT;
BEGIN
    partition_date := DATE(NEW.created_at);
    partition_name := 'content_analytics_events_' ||
                      TO_CHAR(partition_date, 'YYYY_MM');
    partition_start := TO_CHAR(partition_date, 'YYYY-MM-01');
    partition_end := TO_CHAR(partition_date + interval '1 month', 'YYYY-MM-01');

    IF NOT EXISTS (
        SELECT 1 FROM pg_class WHERE relname = partition_name
    ) THEN
        EXECUTE format(
            'CREATE TABLE %I PARTITION OF content_analytics_events '
            'FOR VALUES FROM (%L) TO (%L)',
            partition_name, partition_start, partition_end
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_auto_partition_analytics
    BEFORE INSERT ON content_analytics_events
    FOR EACH ROW EXECUTE FUNCTION auto_create_analytics_partition();

COMMIT;
