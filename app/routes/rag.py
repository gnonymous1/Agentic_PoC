"""
GNONE — RAG API Routes

FastAPI routes for document upload, RAG search, and knowledge base management.
"""

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.services.rag_pipeline import RAGResponse, rag_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    client_id: str = Field(default="default", max_length=64)
    n_results: int = Field(default=10, ge=1, le=50)
    source_type: str | None = None
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class IngestTextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=100000)
    title: str = Field(..., min_length=1, max_length=256)
    client_id: str = Field(default="default", max_length=64)
    source_type: str = Field(default="text", max_length=64)
    metadata: dict | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[dict]
    context: str
    total_chunks_searched: int
    search_time_ms: float


class IngestResponse(BaseModel):
    filename: str | None = None
    title: str | None = None
    chunks_ingested: int
    collection: str
    metadata: dict | None = None


class KBStatsResponse(BaseModel):
    name: str
    count: int
    metadata: dict


@router.post("/ingest/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    client_id: str = Form(default="default"),
    source_type: str = Form(default="document"),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    allowed = {".pdf", ".txt", ".md", ".csv"}
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(allowed)}",
        )

    try:
        content = await file.read()
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            result = rag_pipeline.ingest_file(
                filepath=tmp_path,
                client_id=client_id,
                source_type=source_type,
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        return IngestResponse(
            filename=result["filename"],
            chunks_ingested=result["chunks_ingested"],
            collection=result["collection"],
            metadata=result.get("metadata"),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("File ingestion failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")


@router.post("/ingest/text", response_model=IngestResponse)
async def ingest_text(request: IngestTextRequest):
    try:
        result = rag_pipeline.ingest_text(
            text=request.text,
            title=request.title,
            client_id=request.client_id,
            source_type=request.source_type,
            extra_metadata=request.metadata,
        )
        return IngestResponse(
            title=result["title"],
            chunks_ingested=result["chunks_ingested"],
            collection=result["collection"],
        )
    except Exception as exc:
        logger.error("Text ingestion failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    try:
        result: RAGResponse = rag_pipeline.search(
            query=request.query,
            client_id=request.client_id,
            n_results=request.n_results,
            source_type=request.source_type,
            similarity_threshold=request.similarity_threshold,
        )

        return SearchResponse(
            query=result.query,
            results=[
                {
                    "document": r.document,
                    "metadata": r.metadata,
                    "similarity": r.similarity,
                    "source": r.source,
                    "chunk_index": r.chunk_index,
                }
                for r in result.results
            ],
            context=result.context,
            total_chunks_searched=result.total_chunks_searched,
            search_time_ms=result.search_time_ms,
        )
    except Exception as exc:
        logger.error("RAG search failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}")


@router.get("/search")
async def search_get(
    query: str = Query(..., min_length=1, max_length=2000),
    client_id: str = Query(default="default", max_length=64),
    n_results: int = Query(default=10, ge=1, le=50),
    source_type: str | None = Query(default=None),
    similarity_threshold: float = Query(default=0.7, ge=0.0, le=1.0),
):
    request = SearchRequest(
        query=query,
        client_id=client_id,
        n_results=n_results,
        source_type=source_type,
        similarity_threshold=similarity_threshold,
    )
    return await search(request)


@router.get("/kb/stats/{client_id}", response_model=KBStatsResponse)
async def get_kb_stats(client_id: str):
    try:
        stats = rag_pipeline.get_knowledge_base_stats(client_id)
        return KBStatsResponse(
            name=stats["name"],
            count=stats["count"],
            metadata=stats.get("metadata", {}),
        )
    except Exception as exc:
        logger.error("Failed to get KB stats: %s", exc)
        raise HTTPException(status_code=500, detail=f"Stats retrieval failed: {exc}")


@router.get("/kb/collections")
async def list_collections():
    try:
        collections = rag_pipeline.list_collections()
        return {"collections": collections, "count": len(collections)}
    except Exception as exc:
        logger.error("Failed to list collections: %s", exc)
        raise HTTPException(status_code=500, detail=f"Collection listing failed: {exc}")


@router.delete("/kb/{client_id}")
async def delete_client_kb(client_id: str):
    try:
        deleted_count = rag_pipeline.delete_client_data(client_id)
        return {
            "client_id": client_id,
            "deleted_chunks": deleted_count,
            "status": "success",
        }
    except Exception as exc:
        logger.error("Failed to delete client KB: %s", exc)
        raise HTTPException(status_code=500, detail=f"KB deletion failed: {exc}")
