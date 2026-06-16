"""
GNONE — Vector Memory Layer.
ChromaDB for local RAG with pgvector fallback for production.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ChromaVectorStore:
    """Local ChromaDB vector store for document embeddings and RAG retrieval."""

    def __init__(self, persist_dir: str = "data/vector_store"):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = None
        self._collection = None

    def _get_client(self):
        if self._client is None:
            try:
                import chromadb
                self._client = chromadb.PersistentClient(path=str(self.persist_dir))
                self._collection = self._client.get_or_create_collection(
                    name="gnone_knowledge",
                    metadata={"hnsw:space": "cosine"},
                )
                logger.info("ChromaDB initialized at %s", self.persist_dir)
            except ImportError:
                logger.warning("ChromaDB not installed. Using in-memory fallback.")
                self._client = "fallback"
                self._collection = {"documents": [], "metadatas": [], "ids": [], "embeddings": []}
        return self._client

    def add_document(self, doc_id: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Add a document to the vector store."""
        client = self._get_client()
        if client == "fallback":
            self._collection["documents"].append(content)
            self._collection["metadatas"].append(metadata or {})
            self._collection["ids"].append(doc_id)
            logger.info("Document %s added (in-memory fallback)", doc_id)
            return True

        try:
            self._collection.add(
                documents=[content],
                ids=[doc_id],
                metadatas=[metadata or {}],
            )
            logger.info("Document %s indexed in ChromaDB", doc_id)
            return True
        except Exception as exc:
            logger.error("ChromaDB add failed: %s", exc)
            return False

    def query(self, query_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant documents via semantic search."""
        client = self._get_client()
        if client == "fallback":
            # Simple keyword fallback
            results = []
            for i, doc in enumerate(self._collection["documents"]):
                if any(word.lower() in doc.lower() for word in query_text.split()):
                    results.append({
                        "id": self._collection["ids"][i],
                        "content": doc,
                        "metadata": self._collection["metadatas"][i],
                    })
            return results[:n_results]

        try:
            results = self._collection.query(query_texts=[query_text], n_results=n_results)
            return [
                {"id": results["ids"][0][i], "content": results["documents"][0][i], "metadata": results["metadatas"][0][i]}
                for i in range(len(results["ids"][0]))
            ]
        except Exception as exc:
            logger.error("ChromaDB query failed: %s", exc)
            return []

    def delete_document(self, doc_id: str) -> bool:
        """Remove a document from the vector store."""
        client = self._get_client()
        if client == "fallback":
            for i, did in enumerate(self._collection["ids"]):
                if did == doc_id:
                    for key in self._collection:
                        if isinstance(self._collection[key], list) and i < len(self._collection[key]):
                            self._collection[key].pop(i)
                    return True
            return False

        try:
            self._collection.delete(ids=[doc_id])
            return True
        except Exception as exc:
            logger.error("ChromaDB delete failed: %s", exc)
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Return vector store statistics."""
        client = self._get_client()
        if client == "fallback":
            return {"count": len(self._collection["ids"]), "backend": "in-memory"}
        try:
            return {"count": self._collection.count(), "backend": "chromadb"}
        except Exception:
            return {"count": 0, "backend": "error"}


# Singleton instance
vector_store = ChromaVectorStore()
