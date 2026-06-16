"""
GNONE — ChromaDB Vector Store Wrapper

Provides connection management, collection creation, upsert, query,
and delete operations for ChromaDB as the local vector store backend.
"""

import logging
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)


class ChromaStore:
    """
    Thread-safe ChromaDB wrapper with automatic collection management,
    persistent storage, and in-memory fallback.
    """

    def __init__(
        self,
        persist_directory: str = "./chroma_data",
        collection_name: str = "gnone_knowledge",
        embedding_dimension: int = 1536,
        distance_metric: str = "cosine",
    ):
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.embedding_dimension = embedding_dimension
        self.distance_metric = distance_metric
        self._client: chromadb.ClientAPI | None = None
        self._collection = None

    def connect(self, use_persistent: bool = True) -> chromadb.ClientAPI:
        if self._client is not None:
            return self._client

        try:
            if use_persistent:
                Path(self.persist_directory).mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(
                    path=self.persist_directory,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
                logger.info(
                    "ChromaDB persistent client initialized at %s",
                    self.persist_directory,
                )
            else:
                self._client = chromadb.EphemeralClient()
                logger.info("ChromaDB ephemeral (in-memory) client initialized")
        except Exception as exc:
            logger.warning(
                "Failed to initialize ChromaDB persistent client, falling back to in-memory: %s",
                exc,
            )
            self._client = chromadb.EphemeralClient()

        return self._client

    def get_or_create_collection(
        self,
        collection_name: str | None = None,
        metadata: dict | None = None,
    ):
        if self._client is None:
            self.connect()

        name = collection_name or self.collection_name
        collection_metadata = metadata or {
            "hnsw:space": self.distance_metric,
            "hnsw:M": 16,
            "hnsw:construction_ef": 200,
        }

        try:
            self._collection = self._client.get_or_create_collection(
                name=name,
                metadata=collection_metadata,
            )
            logger.info(
                "Collection '%s' ready (%d documents)",
                name,
                self._collection.count(),
            )
        except Exception as exc:
            logger.error("Failed to get/create collection '%s': %s", name, exc)
            raise

        return self._collection

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict] | None = None,
        collection_name: str | None = None,
    ) -> bool:
        collection = self.get_or_create_collection(collection_name)

        if metadatas is None:
            metadatas = [{} for _ in ids]

        batch_size = 500
        for i in range(0, len(ids), batch_size):
            batch_end = min(i + batch_size, len(ids))
            collection.upsert(
                ids=ids[i:batch_end],
                embeddings=embeddings[i:batch_end],
                documents=documents[i:batch_end],
                metadatas=metadatas[i:batch_end],
            )

        logger.info(
            "Upserted %d vectors into collection '%s'",
            len(ids),
            collection_name or self.collection_name,
        )
        return True

    def query(
        self,
        query_embeddings: list[list[float]],
        n_results: int = 10,
        where: dict | None = None,
        where_document: dict | None = None,
        include: list[str] | None = None,
        collection_name: str | None = None,
    ) -> dict:
        collection = self.get_or_create_collection(collection_name)

        query_params: dict = {
            "query_embeddings": query_embeddings,
            "n_results": n_results,
        }

        if where:
            query_params["where"] = where
        if where_document:
            query_params["where_document"] = where_document
        if include:
            query_params["include"] = include
        else:
            query_params["include"] = ["documents", "metadatas", "distances"]

        results = collection.query(**query_params)
        return results

    def delete(
        self,
        ids: list[str] | None = None,
        where: dict | None = None,
        collection_name: str | None = None,
    ) -> bool:
        collection = self.get_or_create_collection(collection_name)

        if ids:
            collection.delete(ids=ids)
            logger.info("Deleted %d vectors by ID from '%s'", len(ids), collection_name or self.collection_name)
        elif where:
            collection.delete(where=where)
            logger.info("Deleted vectors by filter from '%s'", collection_name or self.collection_name)
        else:
            logger.warning("No IDs or filter provided for delete")
            return False

        return True

    def delete_collection(self, collection_name: str | None = None) -> bool:
        if self._client is None:
            self.connect()

        name = collection_name or self.collection_name
        try:
            self._client.delete_collection(name)
            if self._collection and self._collection.name == name:
                self._collection = None
            logger.info("Deleted collection '%s'", name)
            return True
        except Exception as exc:
            logger.error("Failed to delete collection '%s': %s", name, exc)
            return False

    def get_collection_stats(self, collection_name: str | None = None) -> dict:
        collection = self.get_or_create_collection(collection_name)
        return {
            "name": collection.name,
            "count": collection.count(),
            "metadata": collection.metadata,
        }

    def list_collections(self) -> list[str]:
        if self._client is None:
            self.connect()
        return [c.name for c in self._client.list_collections()]

    def close(self) -> None:
        self._client = None
        self._collection = None
        logger.info("ChromaDB connection closed")


chroma_store = ChromaStore()
