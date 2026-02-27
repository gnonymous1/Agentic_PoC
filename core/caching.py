import asyncio
import hashlib
import json
import time
import os
from datetime import datetime
from typing import Optional, Any
from enum import Enum

class CacheStrategy(Enum):
    L1_ONLY = "l1"
    L1_L2 = "l1_l2"
    NONE = "none"

class L1Cache:
    """In-memory LRU Cache."""
    def __init__(self, max_size: int = 1000):
        self.cache = {}
        self.access_order = []  # List of keys, most recent last
        self.max_size = max_size

    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            # Move to end (most recently used)
            if key in self.access_order:
                self.access_order.remove(key)
            self.access_order.append(key)
            
            # Check expiry? (Handling expire at Manager level for simplicity or embedding it)
            entry = self.cache[key]
            if entry["expiry"] and time.time() > entry["expiry"]:
                self.delete(key)
                return None
            return entry["value"]
        return None

    def set(self, key: str, value: Any, ttl: int = 3600):
        expiry = time.time() + ttl if ttl else None
        
        if len(self.cache) >= self.max_size and key not in self.cache:
            # Evict LRU
            oldest = self.access_order.pop(0)
            del self.cache[oldest]

        self.cache[key] = {"value": value, "expiry": expiry}
        if key in self.access_order:
            self.access_order.remove(key)
        self.access_order.append(key)

    def delete(self, key: str):
        if key in self.cache:
            del self.cache[key]
        if key in self.access_order:
            self.access_order.remove(key)

class L2Cache:
    """Disk-based Cache."""
    def __init__(self, directory: str = "./data/cache"):
        self.directory = directory
        os.makedirs(directory, exist_ok=True)

    def _get_path(self, key: str) -> str:
        # User safe filename logic
        safe_key = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.directory, f"{safe_key}.json")

    async def get(self, key: str) -> Optional[Any]:
        path = self._get_path(key)
        if os.path.exists(path):
            try:
                # Run in thread to avoid blocking loop
                def load():
                    with open(path, "r") as f:
                        return json.load(f)
                entry = await asyncio.to_thread(load)
                
                if entry["expiry"] and time.time() > entry["expiry"]:
                    await self.delete(key)
                    return None
                return entry["value"]
            except Exception:
                return None
        return None

    async def set(self, key: str, value: Any, ttl: int = 86400):
        expiry = time.time() + ttl if ttl else None
        entry = {"value": value, "expiry": expiry}
        path = self._get_path(key)
        
        def save():
            with open(path, "w") as f:
                json.dump(entry, f, default=str)
        await asyncio.to_thread(save)

    async def delete(self, key: str):
        path = self._get_path(key)
        if os.path.exists(path):
            await asyncio.to_thread(os.remove, path)

class SemanticCache:
    """Vector-based semantic cache for fuzzy matching."""
    def __init__(self, config: dict, memory=None):
        from core.memory import VectorMemory
        self.memory = memory or VectorMemory(config)
        self.threshold = config.get("semantic_cache_threshold", 0.95)

    async def get(self, prompt: str, model_id: str) -> Optional[Any]:
        # Search in a dedicated cache collection if possible, or general
        results = await self.memory.search(prompt, limit=1, collection="omnios_cache")
        if results:
            best = results[0]
            if best["relevance"] >= self.threshold:
                # Ensure model_id matches or is compatible
                data = best.get("data", {})
                if data.get("model_id") == model_id:
                    return data.get("response")
        return None

    async def set(self, prompt: str, model_id: str, response: Any):
        await self.memory.store({
            "type": "cache_entry",
            "prompt": prompt,
            "model_id": model_id,
            "response": response,
            "timestamp": datetime.now().isoformat()
        }, collection="omnios_cache")

class CacheManager:
    """Orchestrates L1, L2, and Semantic caching."""
    def __init__(self, config: dict, memory=None):
        self.config = config
        self.l1 = L1Cache(max_size=config.get("cache_l1_size", 100))
        self.l2 = L2Cache(directory=config.get("cache_l2_dir", "./data/cache"))
        self.semantic = SemanticCache(config, memory=memory)

    def generate_key(self, prompt: str, model_id: str, **kwargs) -> str:
        """Create a stable key from inputs."""
        combined = f"{model_id}:{prompt}:{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.sha256(combined.encode()).hexdigest()

    async def get(self, prompt: str, model_id: str, **kwargs) -> Optional[Any]:
        key = self.generate_key(prompt, model_id, **kwargs)
        
        # 1. Check L1 (In-Memory)
        val = self.l1.get(key)
        if val is not None:
             return val
        
        # 2. Check L2 (Disk/Redis)
        val = await self.l2.get(key)
        if val is not None:
            self.l1.set(key, val) # Promote to L1
            return val
            
        # 3. Check Semantic (Vector) - Only for general text tasks
        if kwargs.get("task_type") in ["general", "creative", "reasoning"]:
            val = await self.semantic.get(prompt, model_id)
            if val is not None:
                # Do NOT promote semantic hits to L1/L2 as keys won't match exactly
                return val
                
        return None

    async def set(self, prompt: str, model_id: str, value: Any, ttl: int = 3600, **kwargs):
        key = self.generate_key(prompt, model_id, **kwargs)
        
        # Write to L1 and L2
        self.l1.set(key, value, ttl=ttl)
        await self.l2.set(key, value, ttl=ttl*24)
        
        # Write to Semantic if appropriate
        if kwargs.get("task_type") in ["general", "creative", "reasoning"]:
            await self.semantic.set(prompt, model_id, value)
