import os
import json
import logging
import datetime
from typing import Dict, List, Any, Optional
from cortex.state import AgentState
from hippocampus.vector_store import LightweightVectorStore
from hippocampus.hybrid_search import HybridSearcher, SimpleBM25
from cortex.llm import get_llm
from utils.logger import setup_logging

logger = setup_logging()

class SemanticLayer:
    """Represents a semantic layer in the hierarchical memory system."""
    
    def __init__(self, name: str, description: str, priority: int = 1):
        self.name = name
        self.description = description
        self.priority = priority
        self.memory_entries = []
        self.metadata = {}
    
    def add_entry(self, content: str, metadata: Dict[str, Any] = None):
        """Add a memory entry to this semantic layer."""
        entry = {
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.datetime.now().isoformat(),
            "layer": self.name
        }
        self.memory_entries.append(entry)
    
    def get_entries(self) -> List[Dict[str, Any]]:
        """Get all memory entries in this layer."""
        return self.memory_entries

class HierarchicalMemory:
    """Advanced hierarchical memory system with semantic layers and hybrid search."""
    
    def __init__(self):
        self.layers = {}
        self.vector_store = LightweightVectorStore()
        self.hybrid_searcher = HybridSearcher(self.vector_store)
        self.bm25_simple = SimpleBM25()  # Fallback BM25
        self.consolidation_queue = []
        self._initialize_layers()
    
    def _initialize_layers(self):
        """Initialize semantic layers with different priorities."""
        self.layers = {
            "critical": SemanticLayer("critical", "High-priority operational data", priority=1),
            "operational": SemanticLayer("operational", "Day-to-day operational memories", priority=2),
            "learning": SemanticLayer("learning", "Learning and skill acquisition", priority=3),
            "experience": SemanticLayer("experience", "Long-term experiential memories", priority=4),
            "knowledge": SemanticLayer("knowledge", "Structured knowledge and facts", priority=5)
        }
    
    def remember(self, text: str, metadata: Dict[str, Any] = None, layer: str = "operational"):
        """
        Store memory with semantic layer classification and hybrid indexing.
        
        Args:
            text: Memory content
            metadata: Additional metadata
            layer: Semantic layer to store in
        """
        if layer not in self.layers:
            layer = "operational"
        
        # Add to semantic layer
        self.layers[layer].add_entry(text, metadata)
        
        # Add to vector store for semantic search
        self.vector_store.add(text, metadata)
        
        # Add to hybrid searcher (BM25 index)
        memory_id = f"mem_{len(self.consolidation_queue)}"
        self.hybrid_searcher.add_document(memory_id, text, metadata, layer)
        self.bm25_simple.add_document(memory_id, text)
        
        # Add to consolidation queue
        self.consolidation_queue.append({
            "content": text,
            "metadata": metadata,
            "layer": layer,
            "timestamp": datetime.datetime.now().isoformat(),
            "memory_id": memory_id
        })
        
        print(f"[HierarchicalMemory] Stored in {layer} layer: {text[:50]}...")
    
    def recall(self, query: str, n_results: int = 5, layer: Optional[str] = None, use_hybrid: bool = True) -> List[Dict[str, Any]]:
        """
        Retrieve relevant memories with hybrid search (BM25 + Vector).
        
        Args:
            query: Search query
            n_results: Number of results to return
            layer: Specific layer to search (None for all layers)
            use_hybrid: Whether to use hybrid search (True) or vector only (False)
        
        Returns:
            List of memory entries with scores
        """
        if layer:
            if layer not in self.layers:
                return []
            # Search within specific layer
            results = []
            for entry in self.layers[layer].get_entries():
                if query.lower() in entry["content"].lower():
                    results.append(entry)
            return results[:n_results]
        else:
            # Use hybrid search (OpenClaw-style: 70% vector + 30% BM25)
            if use_hybrid:
                try:
                    results = self.hybrid_searcher.search(query, n_results)
                    logger.info(f"[HybridSearch] Found {len(results)} results for query: {query[:50]}...")
                    return results
                except Exception as e:
                    logger.error(f"[HybridSearch] Error: {e}, falling back to vector search")
                    return self.vector_store.query(query, n_results)
            else:
                # Vector only search
                return self.vector_store.query(query, n_results)
    
    def consolidate_memory(self, state: AgentState = None) -> Dict[str, Any]:
        """
        Perform long-term memory consolidation.
        
        Args:
            state: Optional agent state for context
        
        Returns:
            Consolidation summary
        """
        llm = get_llm(role="memory")
        
        # Process consolidation queue
        if not self.consolidation_queue:
            return {"status": "no_new_memories", "summary": "No memories to consolidate"}
        
        # Get recent memories for consolidation
        recent_memories = self.consolidation_queue[-10:]  # Last 10 memories
        
        # Generate consolidation prompt
        memories_text = "\n".join([f"- {m['content']}" for m in recent_memories])
        
        consolidation_prompt = f"""You are performing memory consolidation for an AI system.

RECENT MEMORIES:
{memories_text}

TASK: Analyze these recent memories and:
1. Identify key patterns and insights
2. Extract important learnings
3. Create a consolidated summary
4. Suggest actions or improvements
5. Store the consolidated knowledge in appropriate semantic layers

Respond with a structured JSON containing:
- patterns: Key patterns identified
- insights: Important insights extracted
- summary: Consolidated summary
- actions: Suggested actions
- knowledge: Structured knowledge to store
- layer: Target semantic layer for storage

Be thorough and analytical."""
        
        messages = [
            {"role": "system", "content": "You are a memory consolidation specialist for an AI system."},
            {"role": "user", "content": consolidation_prompt}
        ]
        
        try:
            response = llm.invoke(messages)
            content = response.content
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            
            consolidation_result = json.loads(content.strip())
            
            # Store consolidated knowledge
            if "knowledge" in consolidation_result and "layer" in consolidation_result:
                self.remember(
                    consolidation_result["knowledge"],
                    metadata=consolidation_result,
                    layer=consolidation_result["layer"]
                )
            
            return {
                "status": "success",
                "result": consolidation_result,
                "memories_processed": len(recent_memories)
            }
            
        except Exception as e:
            logger.error(f"Memory consolidation failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "memories_processed": len(recent_memories)
            }
    
    def get_layer_summary(self, layer: str) -> Dict[str, Any]:
        """Get summary statistics for a specific semantic layer."""
        if layer not in self.layers:
            return {"error": "Layer not found"}
        
        layer_obj = self.layers[layer]
        entries = layer_obj.get_entries()
        
        return {
            "layer": layer,
            "description": layer_obj.description,
            "priority": layer_obj.priority,
            "memory_count": len(entries),
            "recent_entries": entries[-5:]  # Last 5 entries
        }
    
    def get_system_summary(self) -> Dict[str, Any]:
        """Get overall memory system summary."""
        total_memories = sum(len(layer.get_entries()) for layer in self.layers.values())
        
        return {
            "total_layers": len(self.layers),
            "total_memories": total_memories,
            "layer_breakdown": {
                name: {
                    "count": len(layer.get_entries()),
                    "priority": layer.priority
                }
                for name, layer in self.layers.items()
            },
            "consolidation_queue_size": len(self.consolidation_queue),
            "vector_store_size": len(self.vector_store.documents)
        }

class Hippocampus:
    def __init__(self):
        self.memory_system = HierarchicalMemory()
        self.is_active = True
        logger.info("[Hippocampus] Initialized Advanced Hierarchical Memory System")

    def remember(self, text: str, metadata: dict = None, layer: str = "operational"):
        """
        Store memory in the hierarchical system.
        
        Args:
            text: Memory content
            metadata: Additional metadata
            layer: Semantic layer to use
        """
        if self.is_active:
            try:
                self.memory_system.remember(text, metadata, layer)
                logger.info(f"[Hippocampus] Stored memory in {layer} layer")
            except Exception as e:
                logger.error(f"[Hippocampus] Error storing memory: {e}")
        else:
            logger.warning("[Hippocampus] Memory system inactive")

    def recall(self, query: str, n_results: int = 5, layer: Optional[str] = None, use_hybrid: bool = True) -> list:
        """
        Retrieve memories with hybrid search support.
        
        Args:
            query: Search query
            n_results: Number of results
            layer: Specific layer to search
            use_hybrid: Whether to use hybrid search (BM25 + Vector)
        
        Returns:
            List of memory entries
        """
        if self.is_active:
            try:
                return self.memory_system.recall(query, n_results, layer, use_hybrid)
            except Exception as e:
                logger.error(f"[Hippocampus] Error recalling memory: {e}")
                return []
        return []

    def consolidate(self, state: AgentState = None) -> Dict[str, Any]:
        """
        Perform memory consolidation.
        
        Args:
            state: Agent state for context
        
        Returns:
            Consolidation result
        """
        if self.is_active:
            try:
                return self.memory_system.consolidate_memory(state)
            except Exception as e:
                logger.error(f"[Hippocampus] Error during consolidation: {e}")
                return {"status": "error", "error": str(e)}
        return {"status": "inactive"}

    def get_summary(self, layer: Optional[str] = None) -> Dict[str, Any]:
        """Get memory system summary."""
        if self.is_active:
            try:
                if layer:
                    return self.memory_system.get_layer_summary(layer)
                else:
                    return self.memory_system.get_system_summary()
            except Exception as e:
                logger.error(f"[Hippocampus] Error getting summary: {e}")
                return {"error": str(e)}
        return {"status": "inactive"}

    def wipe(self):
        """Clear all memories."""
        if self.is_active:
            try:
                self.memory_system = HierarchicalMemory()
                logger.info("[Hippocampus] Memory system wiped")
            except Exception as e:
                logger.error(f"[Hippocampus] Error wiping memory: {e}")

