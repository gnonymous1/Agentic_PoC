"""
GNONE — RAG Pipeline

Full Retrieval-Augmented Generation pipeline with:
- Document ingestion (PDF, TXT, MD, CSV)
- Text chunking with configurable overlap
- Embedding generation via Gemini API
- ChromaDB local vector store (with in-memory fallback)
- Semantic search with metadata filtering
- Context assembly for LLM prompts
- RAG-enhanced research combining web grounding with local knowledge
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from app.services.chroma_store import ChromaStore
from app.services.document_parser import document_parser

logger = logging.getLogger(__name__)


@dataclass
class ChunkingConfig:
    chunk_size: int = 500
    chunk_overlap: int = 50
    min_chunk_size: int = 50
    separators: list[str] = field(default_factory=lambda: [
        "\n\n", "\n", ". ", "! ", "? ", ", ", " ",
    ])


@dataclass
class RAGResult:
    document: str
    metadata: dict
    similarity: float
    source: str
    chunk_index: int


@dataclass
class RAGResponse:
    query: str
    results: list[RAGResult]
    context: str
    total_chunks_searched: int
    search_time_ms: float


class RAGPipeline:
    """
    End-to-end RAG pipeline for document ingestion, embedding,
    storage, and semantic retrieval.
    """

    def __init__(
        self,
        gemini_api_key: str,
        embedding_model: str = "text-embedding-004",
        embedding_dimension: int = 1536,
        chroma_persist_dir: str = "./chroma_data",
        chunking_config: ChunkingConfig | None = None,
        collection_prefix: str = "gnone",
    ):
        self.gemini_api_key = gemini_api_key
        self.embedding_model = embedding_model
        self.embedding_dimension = embedding_dimension
        self.chunking_config = chunking_config or ChunkingConfig()
        self.collection_prefix = collection_prefix
        self.chroma_store = ChromaStore(
            persist_directory=chroma_persist_dir,
            embedding_dimension=embedding_dimension,
        )

    def ingest_file(
        self,
        filepath: str | Path,
        client_id: str = "default",
        source_type: str = "document",
        extra_metadata: dict | None = None,
    ) -> dict:
        logger.info("Ingesting file: %s", filepath)

        doc = document_parser.parse_file(filepath)

        chunks = self.chunk_text(doc.content)
        logger.info(
            "Document '%s' split into %d chunks",
            doc.filename,
            len(chunks),
        )

        embeddings = self.generate_embeddings(chunks)

        ids = []
        metadatas = []
        for i, chunk in enumerate(chunks):
            chunk_id = self._generate_chunk_id(doc.filename, i)
            ids.append(chunk_id)

            chunk_metadata = {
                "client_id": client_id,
                "source_type": source_type,
                "filename": doc.filename,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "char_count": len(chunk),
                "word_count": len(chunk.split()),
            }
            if extra_metadata:
                chunk_metadata.update(extra_metadata)
            metadatas.append(chunk_metadata)

        collection_name = f"{self.collection_prefix}_{client_id}"
        self.chroma_store.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
            collection_name=collection_name,
        )

        return {
            "filename": doc.filename,
            "chunks_ingested": len(chunks),
            "collection": collection_name,
            "metadata": doc.metadata,
        }

    def ingest_text(
        self,
        text: str,
        title: str,
        client_id: str = "default",
        source_type: str = "text",
        extra_metadata: dict | None = None,
    ) -> dict:
        logger.info("Ingesting text: '%s' (%d chars)", title, len(text))

        chunks = self.chunk_text(text)
        embeddings = self.generate_embeddings(chunks)

        ids = []
        metadatas = []
        for i, chunk in enumerate(chunks):
            chunk_id = self._generate_chunk_id(title, i)
            ids.append(chunk_id)

            chunk_metadata = {
                "client_id": client_id,
                "source_type": source_type,
                "title": title,
                "chunk_index": i,
                "total_chunks": len(chunks),
            }
            if extra_metadata:
                chunk_metadata.update(extra_metadata)
            metadatas.append(chunk_metadata)

        collection_name = f"{self.collection_prefix}_{client_id}"
        self.chroma_store.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
            collection_name=collection_name,
        )

        return {
            "title": title,
            "chunks_ingested": len(chunks),
            "collection": collection_name,
        }

    def search(
        self,
        query: str,
        client_id: str = "default",
        n_results: int = 10,
        source_type: str | None = None,
        similarity_threshold: float = 0.7,
    ) -> RAGResponse:
        start_time = time.time()

        query_embedding = self.generate_embeddings([query])

        where_filter: dict = {"client_id": client_id}
        if source_type:
            where_filter["source_type"] = source_type

        results = self.chroma_store.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            where=where_filter,
            collection_name=f"{self.collection_prefix}_{client_id}",
        )

        rag_results = []
        if results.get("ids") and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results.get("distances") else 1.0
                similarity = 1.0 - distance

                if similarity >= similarity_threshold:
                    metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                    document = results["documents"][0][i] if results.get("documents") else ""

                    rag_results.append(RAGResult(
                        document=document,
                        metadata=metadata,
                        similarity=round(similarity, 4),
                        source=metadata.get("filename", metadata.get("title", "unknown")),
                        chunk_index=metadata.get("chunk_index", i),
                    ))

        context = self.assemble_context(rag_results)

        elapsed_ms = (time.time() - start_time) * 1000

        return RAGResponse(
            query=query,
            results=rag_results,
            context=context,
            total_chunks_searched=len(rag_results),
            search_time_ms=round(elapsed_ms, 2),
        )

    def assemble_context(
        self,
        results: list[RAGResult],
        max_context_length: int = 4000,
    ) -> str:
        if not results:
            return ""

        context_parts = []
        current_length = 0

        for result in sorted(results, key=lambda r: r.similarity, reverse=True):
            chunk_text = (
                f"[Source: {result.source} | "
                f"Similarity: {result.similarity:.2f} | "
                f"Chunk: {result.chunk_index}]\n"
                f"{result.document}"
            )

            if current_length + len(chunk_text) > max_context_length:
                remaining = max_context_length - current_length
                if remaining > 100:
                    context_parts.append(chunk_text[:remaining] + "...")
                break

            context_parts.append(chunk_text)
            current_length += len(chunk_text) + 2

        return "\n\n".join(context_parts)

    def build_rag_prompt(
        self,
        query: str,
        context: str,
        system_instruction: str | None = None,
    ) -> str:
        if not context:
            return query

        base_prompt = (
            "You are a knowledgeable assistant. Use the following retrieved "
            "context to answer the question. If the context does not contain "
            "sufficient information, acknowledge this and provide the best "
            "answer you can based on your general knowledge.\n\n"
        )

        if system_instruction:
            base_prompt = system_instruction + "\n\n" + base_prompt

        return (
            f"{base_prompt}"
            f"=== RETRIEVED CONTEXT ===\n{context}\n\n"
            f"=== QUESTION ===\n{query}\n\n"
            f"=== ANSWER ===\n"
        )

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        batch_size = 100
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_embeddings = self._call_gemini_embedding_api(batch)
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    def _call_gemini_embedding_api(self, texts: list[str]) -> list[list[float]]:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/{self.embedding_model}:batchEmbedContents"
        )

        requests = []
        for text in texts:
            requests.append({
                "model": f"models/{self.embedding_model}",
                "content": {"parts": [{"text": text}]},
            })

        payload = {"requests": requests}

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.gemini_api_key,
        }

        response = httpx.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()

        data = response.json()
        embeddings = []

        for item in data.get("embeddings", []):
            values = item.get("values", [])
            if len(values) == self.embedding_dimension:
                embeddings.append(values)
            else:
                logger.warning(
                    "Embedding dimension mismatch: expected %d, got %d",
                    self.embedding_dimension,
                    len(values),
                )
                embeddings.append(values + [0.0] * (self.embedding_dimension - len(values)))

        return embeddings

    def chunk_text(self, text: str) -> list[str]:
        config = self.chunking_config
        chunks = []

        for separator in config.separators:
            if not text.strip():
                break

            parts = text.split(separator)
            current_chunk = ""

            for part in parts:
                if len(current_chunk) + len(part) <= config.chunk_size:
                    current_chunk += (separator if current_chunk else "") + part
                else:
                    if current_chunk.strip():
                        chunks.append(current_chunk.strip())

                    if len(part) > config.chunk_size:
                        sub_chunks = self._split_large_segment(part, config)
                        if sub_chunks:
                            current_chunk = sub_chunks[-1]
                            chunks.extend(sub_chunks[:-1])
                    else:
                        current_chunk = part

            if current_chunk.strip():
                chunks.append(current_chunk.strip())
                text = ""
                break

            text = separator.join(parts)

        if not chunks and text.strip():
            chunks.append(text.strip())

        if config.chunk_overlap > 0 and len(chunks) > 1:
            chunks = self._apply_overlap(chunks, config)

        return [c for c in chunks if len(c) >= config.min_chunk_size]

    def _split_large_segment(
        self, segment: str, config: ChunkingConfig
    ) -> list[str]:
        chunks = []
        for i in range(0, len(segment), config.chunk_size - config.chunk_overlap):
            chunk = segment[i : i + config.chunk_size]
            if chunk.strip():
                chunks.append(chunk.strip())
        return chunks

    def _apply_overlap(
        self, chunks: list[str], config: ChunkingConfig
    ) -> list[str]:
        if config.chunk_overlap <= 0 or len(chunks) <= 1:
            return chunks

        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_chunk = chunks[i - 1]
            overlap_text = prev_chunk[-config.chunk_overlap:]
            new_chunk = overlap_text + chunks[i]
            overlapped.append(new_chunk)

        return overlapped

    def delete_client_data(self, client_id: str) -> int:
        collection_name = f"{self.collection_prefix}_{client_id}"
        try:
            self.chroma_store.delete(
                where={"client_id": client_id},
                collection_name=collection_name,
            )
            stats = self.chroma_store.get_collection_stats(collection_name)
            return stats.get("count", 0)
        except Exception as exc:
            logger.error("Failed to delete client data: %s", exc)
            return 0

    def get_knowledge_base_stats(self, client_id: str) -> dict:
        collection_name = f"{self.collection_prefix}_{client_id}"
        try:
            return self.chroma_store.get_collection_stats(collection_name)
        except Exception:
            return {"name": collection_name, "count": 0, "metadata": {}}

    def list_collections(self) -> list[str]:
        return self.chroma_store.list_collections()

    @staticmethod
    def _generate_chunk_id(filename: str, index: int) -> str:
        raw = f"{filename}:{index}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


rag_pipeline = RAGPipeline(
    gemini_api_key="",
)
