"""
Hybrid Search - OpenClaw-style BM25 + Vector search
Combines semantic vector search with BM25 keyword ranking
"""

import sqlite3
import re
from typing import List, Dict, Any, Tuple
from collections import defaultdict
import math
from utils.logger import setup_logging

logger = setup_logging()


class BM25Searcher:
    """BM25 keyword search implementation using SQLite FTS5"""
    
    def __init__(self, db_path: str = "./data/memory_bm25.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite with FTS5"""
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create FTS5 virtual table for full-text search
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                content,
                metadata,
                layer,
                timestamp,
                memory_id UNINDEXED
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("[BM25] Initialized FTS5 database")
    
    def add_document(self, memory_id: str, content: str, metadata: str = "", layer: str = "operational", timestamp: str = ""):
        """Add a document to the BM25 index"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO memory_fts (content, metadata, layer, timestamp, memory_id) VALUES (?, ?, ?, ?, ?)",
                (content, metadata, layer, timestamp, memory_id)
            )
            conn.commit()
        except Exception as e:
            logger.error(f"[BM25] Error adding document: {e}")
        finally:
            conn.close()
    
    def search(self, query: str, n_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search using BM25 ranking
        Returns: List of results with scores
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Use FTS5 rank for BM25 scoring
            cursor.execute("""
                SELECT memory_id, content, metadata, layer, timestamp, rank
                FROM memory_fts
                WHERE memory_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, n_results))
            
            results = []
            for row in cursor.fetchall():
                memory_id, content, metadata, layer, timestamp, rank = row
                # Convert FTS5 rank (lower is better) to score (higher is better)
                # FTS5 rank is negative log of probability, so we invert it
                score = 1.0 / (1.0 + abs(rank)) if rank else 0.0
                
                results.append({
                    "memory_id": memory_id,
                    "content": content,
                    "metadata": metadata,
                    "layer": layer,
                    "timestamp": timestamp,
                    "score": score,
                    "source": "bm25"
                })
            
            return results
        except Exception as e:
            logger.error(f"[BM25] Search error: {e}")
            return []
        finally:
            conn.close()
    
    def clear(self):
        """Clear all indexed documents"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM memory_fts")
        conn.commit()
        conn.close()
        logger.info("[BM25] Cleared all documents")


class HybridSearcher:
    """
    Hybrid search combining Vector and BM25
    Weight: 70% Vector + 30% BM25 (OpenClaw-style)
    """
    
    def __init__(self, vector_store, bm25_searcher: BM25Searcher = None):
        self.vector_store = vector_store
        self.bm25 = bm25_searcher or BM25Searcher()
        self.vector_weight = 0.7
        self.bm25_weight = 0.3
    
    def add_document(self, memory_id: str, content: str, metadata: Dict[str, Any] = None, layer: str = "operational"):
        """Add document to both indexes"""
        import json
        import datetime
        
        timestamp = datetime.datetime.now().isoformat()
        metadata_str = json.dumps(metadata) if metadata else ""
        
        # Add to BM25 index
        self.bm25.add_document(memory_id, content, metadata_str, layer, timestamp)
    
    def search(self, query: str, n_results: int = 6) -> List[Dict[str, Any]]:
        """
        Perform hybrid search
        1. Get 4x candidates from each source
        2. Merge and weight scores
        3. Return top N
        """
        candidate_multiplier = 4
        n_candidates = n_results * candidate_multiplier
        
        # Get vector results
        vector_results = self._get_vector_results(query, n_candidates)
        
        # Get BM25 results
        bm25_results = self.bm25.search(query, n_candidates)
        
        # Merge results
        merged = self._merge_results(vector_results, bm25_results, n_results)
        
        return merged
    
    def _get_vector_results(self, query: str, n_results: int) -> List[Dict[str, Any]]:
        """Get results from vector store"""
        try:
            results = self.vector_store.query(query, n_results)
            # Normalize and tag
            for r in results:
                r["source"] = "vector"
                r["score"] = r.get("score", 0.5)  # Default score if not provided
            return results
        except Exception as e:
            logger.error(f"[Hybrid] Vector search error: {e}")
            return []
    
    def _merge_results(self, vector_results: List[Dict], bm25_results: List[Dict], n_final: int) -> List[Dict]:
        """
        Merge and weight results from both sources
        Final score = (vector_score * 0.7) + (bm25_score * 0.3)
        """
        # Create score lookup by content
        scores = defaultdict(lambda: {"vector": 0.0, "bm25": 0.0})
        contents = {}
        metadata = {}
        
        # Process vector results
        for r in vector_results:
            content = r.get("content", "")
            scores[content]["vector"] = r.get("score", 0.0)
            contents[content] = r
        
        # Process BM25 results
        for r in bm25_results:
            content = r.get("content", "")
            scores[content]["bm25"] = r.get("score", 0.0)
            if content not in contents:
                contents[content] = r
        
        # Calculate weighted scores
        final_results = []
        for content, content_scores in scores.items():
            weighted_score = (
                content_scores["vector"] * self.vector_weight +
                content_scores["bm25"] * self.bm25_weight
            )
            
            result = contents[content].copy()
            result["score"] = weighted_score
            result["vector_score"] = content_scores["vector"]
            result["bm25_score"] = content_scores["bm25"]
            final_results.append(result)
        
        # Sort by weighted score and return top N
        final_results.sort(key=lambda x: x["score"], reverse=True)
        return final_results[:n_final]


# Simple in-memory BM25 for systems without FTS5 support
class SimpleBM25:
    """Simple BM25 implementation without external dependencies"""
    
    def __init__(self):
        self.documents = []
        self.doc_freqs = defaultdict(int)
        self.avg_doc_len = 0
    
    def add_document(self, doc_id: str, content: str):
        """Add document to index"""
        tokens = self._tokenize(content)
        doc = {
            "id": doc_id,
            "content": content,
            "tokens": tokens,
            "length": len(tokens)
        }
        self.documents.append(doc)
        
        # Update document frequencies
        unique_tokens = set(tokens)
        for token in unique_tokens:
            self.doc_freqs[token] += 1
        
        # Update average document length
        total_len = sum(d["length"] for d in self.documents)
        self.avg_doc_len = total_len / len(self.documents) if self.documents else 0
    
    def search(self, query: str, n_results: int = 10) -> List[Dict]:
        """Search documents using BM25"""
        query_tokens = self._tokenize(query)
        scores = []
        
        k1 = 1.5  # BM25 parameter
        b = 0.75  # BM25 parameter
        N = len(self.documents)
        
        for doc in self.documents:
            score = 0.0
            doc_len = doc["length"]
            
            for term in query_tokens:
                # Term frequency in document
                tf = doc["tokens"].count(term)
                
                # Document frequency
                df = self.doc_freqs.get(term, 0)
                
                # IDF calculation
                if df > 0:
                    idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
                else:
                    idf = 0
                
                # BM25 score for this term
                numerator = tf * (k1 + 1)
                denominator = tf + k1 * (1 - b + b * (doc_len / self.avg_doc_len)) if self.avg_doc_len > 0 else tf + k1
                score += idf * (numerator / denominator) if denominator > 0 else 0
            
            scores.append((doc, score))
        
        # Sort by score
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # Return top N
        results = []
        for doc, score in scores[:n_results]:
            results.append({
                "memory_id": doc["id"],
                "content": doc["content"],
                "score": score,
                "source": "bm25"
            })
        
        return results
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization"""
        # Lowercase and extract words
        text = text.lower()
        tokens = re.findall(r'\b\w+\b', text)
        return tokens
