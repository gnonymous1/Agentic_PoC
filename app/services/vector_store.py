"""
pgvector client for real-time semantic documentation retrieval.
Supports cosine similarity ANN search using the HNSW index.
"""

from dataclasses import dataclass

from app.infrastructure.db import db


@dataclass
class KnowledgeChunk:
    id: str
    client_id: str
    title: str
    content_chunk: str
    source_type: str
    similarity: float


async def search_similar(
    client_id: str,
    embedding: list[float],
    limit: int = 5,
    source_type: str | None = None,
) -> list[KnowledgeChunk]:
    """
    Cosine similarity search against corporate_knowledge_vectors.
    Uses the HNSW index for sub-50ms retrieval.
    """
    source_filter = ""
    params: list = [embedding, client_id, limit]

    if source_type:
        source_filter = "AND source_type = $4"
        params.append(source_type)

    query = f"""
        SELECT
            id,
            client_id,
            title,
            content_chunk,
            source_type,
            1 - (embedding <=> $1::vector) AS similarity
        FROM corporate_knowledge_vectors
        WHERE client_id = $2
          {source_filter}
        ORDER BY embedding <=> $1::vector
        LIMIT $3
    """

    rows = await db.fetch(query, *params)
    return [
        KnowledgeChunk(
            id=row["id"],
            client_id=row["client_id"],
            title=row["title"],
            content_chunk=row["content_chunk"],
            source_type=row["source_type"],
            similarity=float(row["similarity"]),
        )
        for row in rows
    ]


async def insert_chunk(
    client_id: str,
    title: str,
    content_chunk: str,
    embedding: list[float],
    source_type: str = "document",
    metadata: dict | None = None,
) -> str:
    query = """
        INSERT INTO corporate_knowledge_vectors
            (client_id, title, content_chunk, embedding, source_type, metadata, token_count)
        VALUES ($1, $2, $3, $4::vector, $5, $6::jsonb, $7)
        RETURNING id
    """
    row = await db.fetchrow(
        query,
        client_id,
        title,
        content_chunk,
        embedding,
        source_type,
        metadata or {},
        len(content_chunk.split()),
    )
    return row["id"]
