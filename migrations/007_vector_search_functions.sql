-- =============================================================================
-- GNONE — Vector Search Functions & Stored Procedures
-- Platform: PostgreSQL 16+ with pgvector
-- =============================================================================

BEGIN;

-- ── 1. Semantic Search with Similarity Threshold ────────────────────────────

CREATE OR REPLACE FUNCTION semantic_search(
    p_client_id UUID,
    p_embedding VECTOR(1536),
    p_limit INTEGER DEFAULT 10,
    p_similarity_threshold FLOAT DEFAULT 0.7,
    p_source_type TEXT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    client_id UUID,
    source_type TEXT,
    title TEXT,
    content_chunk TEXT,
    similarity FLOAT,
    token_count INTEGER,
    metadata JSONB,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN QUERY
    SELECT
        ckv.id,
        ckv.client_id,
        ckv.source_type,
        ckv.title,
        ckv.content_chunk,
        (1 - (ckv.embedding <=> p_embedding))::FLOAT AS similarity,
        ckv.token_count,
        ckv.metadata,
        ckv.created_at
    FROM corporate_knowledge_vectors ckv
    WHERE ckv.client_id = p_client_id
      AND (p_source_type IS NULL OR ckv.source_type = p_source_type)
      AND (1 - (ckv.embedding <=> p_embedding)) >= p_similarity_threshold
    ORDER BY ckv.embedding <=> p_embedding
    LIMIT p_limit;
END;
$$;

-- ── 2. Cross-Client Semantic Search (Admin Only) ────────────────────────────

CREATE OR REPLACE FUNCTION semantic_search_all_clients(
    p_embedding VECTOR(1536),
    p_limit INTEGER DEFAULT 20,
    p_similarity_threshold FLOAT DEFAULT 0.75,
    p_source_type TEXT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    client_id UUID,
    org_name TEXT,
    source_type TEXT,
    title TEXT,
    content_chunk TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN QUERY
    SELECT
        ckv.id,
        ckv.client_id,
        c.org_name,
        ckv.source_type,
        ckv.title,
        ckv.content_chunk,
        (1 - (ckv.embedding <=> p_embedding))::FLOAT AS similarity
    FROM corporate_knowledge_vectors ckv
    JOIN clients c ON c.id = ckv.client_id
    WHERE c.is_active = TRUE
      AND (p_source_type IS NULL OR ckv.source_type = p_source_type)
      AND (1 - (ckv.embedding <=> p_embedding)) >= p_similarity_threshold
    ORDER BY ckv.embedding <=> p_embedding
    LIMIT p_limit;
END;
$$;

-- ── 3. Batch Semantic Search (Multiple Embeddings) ──────────────────────────

CREATE OR REPLACE FUNCTION batch_semantic_search(
    p_client_id UUID,
    p_embeddings VECTOR(1536)[],
    p_limit_per_query INTEGER DEFAULT 5,
    p_similarity_threshold FLOAT DEFAULT 0.7
)
RETURNS TABLE (
    query_index INTEGER,
    id UUID,
    title TEXT,
    content_chunk TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    i INTEGER;
    emb VECTOR(1536);
BEGIN
    FOR i IN 1..array_length(p_embeddings, 1) LOOP
        emb := p_embeddings[i];
        RETURN QUERY
        SELECT
            (i - 1) AS query_index,
            ckv.id,
            ckv.title,
            ckv.content_chunk,
            (1 - (ckv.embedding <=> emb))::FLOAT AS similarity
        FROM corporate_knowledge_vectors ckv
        WHERE ckv.client_id = p_client_id
          AND (1 - (ckv.embedding <=> emb)) >= p_similarity_threshold
        ORDER BY ckv.embedding <=> emb
        LIMIT p_limit_per_query;
    END LOOP;
END;
$$;

-- ── 4. Embedding Generation Wrapper (Application Calls This) ────────────────

CREATE OR REPLACE FUNCTION generate_and_store_embedding(
    p_client_id UUID,
    p_source_type TEXT,
    p_title TEXT,
    p_content TEXT,
    p_embedding VECTOR(1536),
    p_metadata JSONB DEFAULT '{}'::jsonb
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_id UUID;
    v_token_count INTEGER;
BEGIN
    v_token_count := array_length(regexp_split_to_array(p_content, '\s+'), 1);

    INSERT INTO corporate_knowledge_vectors (
        client_id, source_type, title, content_chunk,
        embedding, metadata, token_count
    ) VALUES (
        p_client_id, p_source_type, p_title, p_content,
        p_embedding, p_metadata, v_token_count
    ) RETURNING id INTO v_id;

    RETURN v_id;
END;
$$;

-- ── 5. Update Embedding for Existing Record ─────────────────────────────────

CREATE OR REPLACE FUNCTION update_knowledge_embedding(
    p_id UUID,
    p_embedding VECTOR(1536),
    p_content TEXT DEFAULT NULL,
    p_title TEXT DEFAULT NULL,
    p_metadata JSONB DEFAULT NULL
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE corporate_knowledge_vectors
    SET
        embedding = p_embedding,
        content_chunk = COALESCE(p_content, content_chunk),
        title = COALESCE(p_title, title),
        metadata = COALESCE(p_metadata, metadata),
        token_count = COALESCE(
            array_length(regexp_split_to_array(COALESCE(p_content, content_chunk), '\s+'), 1),
            token_count
        )
    WHERE id = p_id;

    RETURN FOUND;
END;
$$;

-- ── 6. Delete Knowledge Vectors by Client ───────────────────────────────────

CREATE OR REPLACE FUNCTION delete_client_knowledge(p_client_id UUID)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_count INTEGER;
BEGIN
    WITH deleted AS (
        DELETE FROM corporate_knowledge_vectors
        WHERE client_id = p_client_id
        RETURNING id
    )
    SELECT COUNT(*) INTO v_count FROM deleted;

    RETURN v_count;
END;
$$;

-- ── 7. Similarity Distribution Stats ────────────────────────────────────────

CREATE OR REPLACE FUNCTION knowledge_similarity_stats(
    p_client_id UUID,
    p_embedding VECTOR(1536)
)
RETURNS TABLE (
    total_chunks BIGINT,
    avg_similarity FLOAT,
    max_similarity FLOAT,
    min_similarity FLOAT,
    above_threshold BIGINT
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT AS total_chunks,
        AVG(1 - (ckv.embedding <=> p_embedding))::FLOAT AS avg_similarity,
        MAX(1 - (ckv.embedding <=> p_embedding))::FLOAT AS max_similarity,
        MIN(1 - (ckv.embedding <=> p_embedding))::FLOAT AS min_similarity,
        COUNT(*) FILTER (
            WHERE (1 - (ckv.embedding <=> p_embedding)) >= 0.7
        )::BIGINT AS above_threshold
    FROM corporate_knowledge_vectors ckv
    WHERE ckv.client_id = p_client_id;
END;
$$;

-- ── 8. Top-K by Source Type ─────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION top_knowledge_by_source(
    p_client_id UUID,
    p_source_type TEXT,
    p_limit INTEGER DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    title TEXT,
    content_chunk TEXT,
    token_count INTEGER,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN QUERY
    SELECT ckv.id, ckv.title, ckv.content_chunk, ckv.token_count, ckv.created_at
    FROM corporate_knowledge_vectors ckv
    WHERE ckv.client_id = p_client_id
      AND ckv.source_type = p_source_type
    ORDER BY ckv.created_at DESC
    LIMIT p_limit;
END;
$$;

COMMIT;
