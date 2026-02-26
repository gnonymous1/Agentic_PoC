import json
import os
import numpy as np
import re
from collections import Counter
import math
import datetime
from typing import Dict, List, Any, Optional
import hashlib
from utils.logger import setup_logging

logger = setup_logging()

class LightweightVectorStore:
    def __init__(self, storage_path="memory.json"):
        self.storage_path = storage_path
        self.documents = [] # List of {"content": str, "meta": dict, "type": str, "timestamp": str}
        self.load()
        self._initialize_embeddings()
    
    def _initialize_embeddings(self):
        """Initialize embedding support if available."""
        try:
            from openai import OpenAI
            import numpy as np
            
            api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM__API_KEY")
            base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("LLM__BASE_URL")
            
            if not api_key:
                raise ValueError("No API key found in environment (OPENAI_API_KEY or LLM__API_KEY)")
                
            self.client = OpenAI(api_key=api_key, base_url=base_url)
            self.embedding_model = "openai"
            self.embedding_dim = 1536
            logger.info(f"[VectorStore] Initialized OpenAI embeddings (Base URL: {base_url or 'Default'})")
        except Exception as e:
            logger.warning(f"[VectorStore] Failed to initialize OpenAI: {e}")
            try:
                from sentence_transformers import SentenceTransformer
                self.embedding_model = "sentence_transformers"
                self.model = SentenceTransformer('all-MiniLM-L6-v2')
                self.embedding_dim = 384
                logger.info("[VectorStore] Initialized SentenceTransformers embeddings")
            except Exception as e:
                logger.warning(f"[VectorStore] Failed to initialize SentenceTransformers: {e}")
                self.embedding_model = None
                logger.warning("[VectorStore] No embedding models available, using basic search")
    
    def load(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    self.documents = json.load(f)
            except:
                self.documents = []
    
    def save(self):
        with open(self.storage_path, 'w', encoding='utf-8') as f:
            json.dump(self.documents, f, indent=2)
    
    def _tokenize(self, text):
        """Simple regex tokenizer."""
        text = text.lower()
        return re.findall(r'\b\w+\b', text)
    
    def _compute_tf(self, tokens):
        """Compute term frequency."""
        tf = Counter(tokens)
        total = len(tokens)
        return {k: v / total for k, v in tf.items()}
    
    def _cosine_similarity(self, vec1, vec2):
        """Compute cosine similarity between two vectors."""
        intersection = set(vec1.keys()) & set(vec2.keys())
        numerator = sum([vec1[x] * vec2[x] for x in intersection])

        sum1 = sum([vec1[x]**2 for x in vec1.keys()])
        sum2 = sum([vec2[x]**2 for x in vec2.keys()])
        denominator = math.sqrt(sum1) * math.sqrt(sum2)

        if not denominator:
            return 0.0
        return numerator / denominator
    
    def _generate_embedding(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding for text using available model."""
        if not self.embedding_model:
            return None
        
        try:
            if self.embedding_model == "openai":
                embedding = self.client.embeddings.create(
                    model="text-embedding-ada-002",
                    input=[text]
                )
                return np.array(embedding.data[0].embedding)
            elif self.embedding_model == "sentence_transformers":
                return self.model.encode(text, convert_to_numpy=True)
        except Exception as e:
            logger.error(f"[VectorStore] Embedding generation failed: {e}")
            return None
    
    def _compute_embedding_similarity(self, embedding1, embedding2) -> float:
        """Compute cosine similarity between two embeddings."""
        if embedding1 is None or embedding2 is None:
            return 0.0
            
        # Ensure numpy arrays
        if not isinstance(embedding1, np.ndarray):
            embedding1 = np.array(embedding1)
        if not isinstance(embedding2, np.ndarray):
            embedding2 = np.array(embedding2)
        
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def add(self, text, metadata=None, content_type: str = "text"):
        """
        Add content to vector store with cross-modal support.
        
        Args:
            text: Content to store
            metadata: Additional metadata
            content_type: Type of content (text, image, audio, video, code)
        """
        doc = {
            "content": text,
            "meta": metadata or {},
            "type": content_type,
            "timestamp": datetime.datetime.now().isoformat(),
            "embedding": None
        }
        
        if content_type == "text":
            emb = self._generate_embedding(text)
            if isinstance(emb, np.ndarray):
                emb = emb.tolist()
            doc["embedding"] = emb
        self.documents.append(doc)
        self.save()
        return True
    
    def query(self, query_text, n_results=5, content_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query the vector store with semantic search and cross-modal support.
        
        Args:
            query_text: Search query
            n_results: Number of results to return
            content_type: Filter by content type (None for all types)
        
        Returns:
            List of matching documents
        """
        if not self.documents:
            return []
        
        # Generate query embedding
        query_embedding = self._generate_embedding(query_text)
        
        # Score documents using multiple methods
        scores = []
        for doc in self.documents:
            # Filter by content type if specified
            if content_type and doc.get("type") != content_type:
                continue
            
            # Compute similarity score
            if query_embedding is not None and doc.get("embedding") is not None:
                # Use embedding similarity for text
                score = self._compute_embedding_similarity(query_embedding, doc["embedding"])
            else:
                # Fall back to TF-IDF for text or basic matching
                query_tokens = self._tokenize(query_text)
                query_vec = self._compute_tf(query_tokens)
                doc_tokens = self._tokenize(doc["content"])
                doc_vec = self._compute_tf(doc_tokens)
                score = self._cosine_similarity(query_vec, doc_vec)
            
            scores.append((score, doc))
        
        # Sort by score descending
        scores.sort(key=lambda x: x[0], reverse=True)
        
        # Return top N results
        return [item[1] for item in scores[:n_results]]
    
    def query_by_metadata(self, metadata_filter: Dict[str, Any], n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Query documents by metadata filters.
        
        Args:
            metadata_filter: Dictionary of metadata filters
            n_results: Maximum number of results
        
        Returns:
            List of matching documents
        """
        results = []
        for doc in self.documents:
            match = True
            for key, value in metadata_filter.items():
                if key not in doc.get("meta", {}) or doc["meta"].get(key) != value:
                    match = False
                    break
            if match:
                results.append(doc)
        
        return results[:n_results]
    
    def query_semantic_similarity(self, reference_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Find documents semantically similar to a reference text.
        
        Args:
            reference_text: Reference text for similarity comparison
            n_results: Number of results to return
        
        Returns:
            List of similar documents
        """
        if not self.documents:
            return []
        
        reference_embedding = self._generate_embedding(reference_text)
        if reference_embedding is None:
            return []
        
        scores = []
        for doc in self.documents:
            if doc.get("embedding") is not None:
                score = self._compute_embedding_similarity(reference_embedding, doc["embedding"])
                scores.append((score, doc))
        
        scores.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scores[:n_results]]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the vector store."""
        content_type_counts = Counter(doc.get("type", "text") for doc in self.documents)
        
        return {
            "total_documents": len(self.documents),
            "content_type_breakdown": dict(content_type_counts),
            "embedding_availability": self.embedding_model is not None,
            "last_updated": max((doc.get("timestamp") for doc in self.documents), default=None)
        }
    
    def clear(self):
        self.documents = []
        self.save()
