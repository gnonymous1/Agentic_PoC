import json
import uuid
import os
from datetime import datetime
from typing import List, Dict, Optional

try:
    import chromadb
    from chromadb.utils import embedding_functions
    HAS_CHROMA = True
except Exception as e:
    print(f"[WARNING] ChromaDB import failed (Python 3.14 Incompatibility): {e}")
    print("[WARNING] Falling back to SimpleJSONMemory")
    HAS_CHROMA = False

class RealVectorMemory:
    """
    Long-term memory using ChromaDB.
    """

    def __init__(self, config: dict):
        self.config = config
        
        # Determine persistence path
        persist_path = config.get("memory", {}).get("path", "./data/chromadb")

        # Initialize Chroma Client
        self.client = chromadb.PersistentClient(path=persist_path)

        # Embedding function
        self.embed_fn = embedding_functions.DefaultEmbeddingFunction()

        # Initialize Collections
        self.collections = {
            "general": self._get_or_create("omnios_general"),
            "executions": self._get_or_create("omnios_executions"),
            "learnings": self._get_or_create("omnios_learnings"),
            "patterns": self._get_or_create("omnios_patterns"),
            "facts": self._get_or_create("omnios_facts"),
        }

    def _get_or_create(self, name: str):
        return self.client.get_or_create_collection(
            name=name,
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine"}
        )

    async def store(self, data: dict, collection: str = "general"):
        """Store data in vector memory."""
        doc_id = str(uuid.uuid4())
        data_type = data.get("type", "general")

        collection_map = {
            "execution": "executions",
            "learning": "learnings",
            "behavioral_pattern": "patterns",
            "fact": "facts",
        }
        col_name = collection_map.get(data_type, collection)
        col = self.collections.get(col_name, self.collections["general"])

        doc_text = self._data_to_text(data)

        col.add(
            documents=[doc_text],
            metadatas=[{
                "type": data_type,
                "timestamp": data.get("timestamp", datetime.now().isoformat()),
                "full_data": json.dumps(data, default=str)[:5000],
            }],
            ids=[doc_id]
        )
        return doc_id

    async def search(self, query: str, limit: int = 10, collection: str = "general") -> List[dict]:
        """Semantic search across memory."""
        col = self.collections.get(collection, self.collections["general"])
        try:
            results = col.query(
                query_texts=[query],
                n_results=min(limit, col.count() or 1),
            )
        except Exception:
            return []

        items = []
        if not results.get("documents"):
            return []
            
        for i, doc in enumerate(results["documents"][0]):
            metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
            try:
                full_data = json.loads(metadata.get("full_data", "{}"))
            except json.JSONDecodeError:
                full_data = {"text": doc}

            distance = results["distances"][0][i] if results.get("distances") else 1.0
            relevance = 1 - distance

            items.append({
                "text": doc,
                "type": metadata.get("type"),
                "timestamp": metadata.get("timestamp"),
                "data": full_data,
                "relevance": relevance,
            })
        return items

    def _data_to_text(self, data: dict) -> str:
        parts = []
        for key, value in data.items():
            if key in ["timestamp", "full_data"]:
                continue
            if isinstance(value, str):
                parts.append(f"{key}: {value}")
            elif isinstance(value, (list, dict)):
                parts.append(f"{key}: {json.dumps(value, default=str)[:500]}")
        return " | ".join(parts)


class SimpleJSONMemory:
    """
    Fallback memory system using timestamp-based JSON files.
    Not semantic, but persistent.
    """
    def __init__(self, config: dict):
        self.config = config
        self.path = config.get("memory", {}).get("vector_store_path", "./data/simple_memory.json")
        self.data = []
        print(f"[MEM] Initialized SimpleJSONMemory at {self.path}")

    async def store(self, data: dict, collection: str = "general"):
        doc_id = str(uuid.uuid4())
        data["id"] = doc_id
        data["timestamp"] = data.get("timestamp", datetime.now().isoformat())
        
        # Ensure collection directory exists
        col_dir = os.path.join(os.path.dirname(self.path), collection)
        os.makedirs(col_dir, exist_ok=True)
        
        file_path = os.path.join(col_dir, f"{doc_id}.json")
        with open(file_path, "w") as f:
            json.dump(data, f, default=str, indent=2)
            
        return doc_id

    async def search(self, query: str, limit: int = 10, collection: str = "general") -> List[dict]:
        # Dumb keyword search used as fallback
        results = []
        try:
            col_dir = os.path.join(os.path.dirname(self.path), collection)
            if not os.path.exists(col_dir):
                return []
                
            files = [f for f in os.listdir(col_dir) if f.endswith(".json")]
            for fname in files:
                with open(os.path.join(col_dir, fname)) as f:
                    data = json.load(f)
                    text_dump = json.dumps(data)
                    # Case-insensitive term matching
                    if any(term.lower() in text_dump.lower() for term in query.split()):
                        results.append({
                            "text": str(data),
                            "data": data,
                            "relevance": 0.8 # Constant relevance for simple search
                        })
                if len(results) >= limit:
                    break
        except Exception:
            pass
        return results

# Export the appropriate class
if HAS_CHROMA:
    VectorMemory = RealVectorMemory
else:
    VectorMemory = SimpleJSONMemory
