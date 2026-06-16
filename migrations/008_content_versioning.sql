-- =============================================================================
-- GNONE — Content Versioning with Diff Tracking
-- Platform: PostgreSQL 16+
-- =============================================================================

BEGIN;

-- ═════════════════════════════════════════════════════════════════════════════
-- TABLE 1: content_versions    — Immutable version history for all content
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE content_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    parent_version_id   UUID REFERENCES content_versions(id) ON DELETE SET NULL,
    content_type        TEXT NOT NULL
                            CHECK (content_type IN (
                                'social_post', 'blog_article', 'email_draft',
                                'meeting_summary', 'voice_script', 'ad_copy',
                                'press_release', 'newsletter', 'knowledge_chunk'
                            )),
    version_number      INTEGER NOT NULL DEFAULT 1
                            CHECK (version_number > 0),
    title               TEXT NOT NULL,
    content_body        JSONB NOT NULL,
    content_hash        TEXT NOT NULL,
    diff_from_parent    JSONB,
    change_summary      TEXT,
    change_author       TEXT NOT NULL DEFAULT 'system',
    change_reason       TEXT,
    status              TEXT NOT NULL DEFAULT 'draft'
                            CHECK (status IN ('draft', 'review', 'approved', 'published', 'archived')),
    critic_score        FLOAT
                            CHECK (critic_score IS NULL OR critic_score BETWEEN 0 AND 100),
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_content_versions_client ON content_versions (client_id, content_type);
CREATE INDEX idx_content_versions_parent ON content_versions (parent_version_id);
CREATE INDEX idx_content_versions_hash ON content_versions (content_hash);
CREATE INDEX idx_content_versions_status ON content_versions (client_id, status);
CREATE INDEX idx_content_versions_created ON content_versions (client_id, created_at DESC);

-- ═════════════════════════════════════════════════════════════════════════════
-- TABLE 2: content_diffs         — Granular diff tracking between versions
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE content_diffs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_version_id  UUID NOT NULL REFERENCES content_versions(id) ON DELETE CASCADE,
    from_version_id     UUID REFERENCES content_versions(id) ON DELETE SET NULL,
    to_version_id       UUID NOT NULL REFERENCES content_versions(id) ON DELETE CASCADE,
    diff_type           TEXT NOT NULL
                            CHECK (diff_type IN ('addition', 'deletion', 'modification', 'reorder')),
    field_path          TEXT NOT NULL,
    old_value           JSONB,
    new_value           JSONB,
    diff_patch          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_content_diffs_version ON content_diffs (content_version_id);
CREATE INDEX idx_content_diffs_from_to ON content_diffs (from_version_id, to_version_id);
CREATE INDEX idx_content_diffs_type ON content_diffs (diff_type);

-- ═════════════════════════════════════════════════════════════════════════════
-- TABLE 3: content_review_log    — Audit trail for review/approval cycles
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE content_review_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_version_id  UUID NOT NULL REFERENCES content_versions(id) ON DELETE CASCADE,
    reviewer_id         TEXT,
    action              TEXT NOT NULL
                            CHECK (action IN ('submitted', 'approved', 'rejected', 'requested_changes', 'published')),
    comment             TEXT,
    critic_feedback     JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_content_review_log_version ON content_review_log (content_version_id);
CREATE INDEX idx_content_review_log_action ON content_review_log (action);
CREATE INDEX idx_content_review_log_created ON content_review_log (created_at DESC);

-- ═════════════════════════════════════════════════════════════════════════════
-- TABLE 4: content_branches      — Branching for parallel content development
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE content_branches (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    branch_name         TEXT NOT NULL,
    root_version_id     UUID NOT NULL REFERENCES content_versions(id) ON DELETE CASCADE,
    tip_version_id      UUID REFERENCES content_versions(id) ON DELETE SET NULL,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_by          TEXT NOT NULL DEFAULT 'system',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at           TIMESTAMPTZ
);

CREATE INDEX idx_content_branches_client ON content_branches (client_id, is_active);
CREATE INDEX idx_content_branches_name ON content_branches (client_id, branch_name);

-- ═════════════════════════════════════════════════════════════════════════════
-- Function: Compute SHA-256 hash of content body
-- ═════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION compute_content_hash(p_content JSONB)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
    RETURN encode(sha256(p_content::bytea), 'hex');
END;
$$;

-- ═════════════════════════════════════════════════════════════════════════════
-- Function: Get version chain for a piece of content
-- ═════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION get_version_chain(
    p_version_id UUID,
    p_direction TEXT DEFAULT 'backward'
)
RETURNS TABLE (
    version_id UUID,
    version_number INTEGER,
    title TEXT,
    content_hash TEXT,
    change_author TEXT,
    change_summary TEXT,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    IF p_direction = 'backward' THEN
        RETURN QUERY
        WITH RECURSIVE chain AS (
            SELECT cv.id, cv.version_number, cv.title, cv.content_hash,
                   cv.change_author, cv.change_summary, cv.created_at,
                   cv.parent_version_id
            FROM content_versions cv
            WHERE cv.id = p_version_id
            UNION ALL
            SELECT cv.id, cv.version_number, cv.title, cv.content_hash,
                   cv.change_author, cv.change_summary, cv.created_at,
                   cv.parent_version_id
            FROM content_versions cv
            JOIN chain c ON cv.id = c.parent_version_id
        )
        SELECT version_id, version_number, title, content_hash,
               change_author, change_summary, created_at
        FROM chain
        ORDER BY version_number DESC;
    ELSE
        RETURN QUERY
        WITH RECURSIVE chain AS (
            SELECT cv.id, cv.version_number, cv.title, cv.content_hash,
                   cv.change_author, cv.change_summary, cv.created_at,
                   cv.parent_version_id
            FROM content_versions cv
            WHERE cv.id = p_version_id
            UNION ALL
            SELECT cv.id, cv.version_number, cv.title, cv.content_hash,
                   cv.change_author, cv.change_summary, cv.created_at,
                   cv.parent_version_id
            FROM content_versions cv
            JOIN chain c ON cv.parent_version_id = c.version_id
        )
        SELECT version_id, version_number, title, content_hash,
               change_author, change_summary, created_at
        FROM chain
        ORDER BY version_number ASC;
    END IF;
END;
$$;

-- ═════════════════════════════════════════════════════════════════════════════
-- Function: Get latest version per content type for a client
-- ═════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION get_latest_content_versions(
    p_client_id UUID,
    p_content_type TEXT DEFAULT NULL,
    p_limit INTEGER DEFAULT 20
)
RETURNS TABLE (
    id UUID,
    content_type TEXT,
    title TEXT,
    version_number INTEGER,
    status TEXT,
    critic_score FLOAT,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT ON (cv.content_type)
        cv.id, cv.content_type, cv.title, cv.version_number,
        cv.status, cv.critic_score, cv.created_at
    FROM content_versions cv
    WHERE cv.client_id = p_client_id
      AND (p_content_type IS NULL OR cv.content_type = p_content_type)
    ORDER BY cv.content_type, cv.version_number DESC, cv.created_at DESC
    LIMIT p_limit;
END;
$$;

-- ═════════════════════════════════════════════════════════════════════════════
-- Trigger: Auto-compute content_hash on insert
-- ═════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION trg_compute_content_hash_fn()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.content_hash := compute_content_hash(NEW.content_body);
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_content_versions_compute_hash
    BEFORE INSERT ON content_versions
    FOR EACH ROW
    EXECUTE FUNCTION trg_compute_content_hash_fn();

-- ═════════════════════════════════════════════════════════════════════════════
-- Trigger: Auto-increment version number
-- ═════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION trg_auto_version_number_fn()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_max_version INTEGER;
BEGIN
    IF NEW.parent_version_id IS NOT NULL THEN
        SELECT COALESCE(MAX(version_number), 0) + 1
        INTO v_max_version
        FROM content_versions
        WHERE parent_version_id = NEW.parent_version_id
           OR id = NEW.parent_version_id;
        NEW.version_number := v_max_version;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_content_versions_auto_number
    BEFORE INSERT ON content_versions
    FOR EACH ROW
    EXECUTE FUNCTION trg_auto_version_number_fn();

COMMIT;
