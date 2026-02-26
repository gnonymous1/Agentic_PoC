"""
Fallback Chain - OpenClaw-style graceful degradation
Handles failures at multiple layers with automatic recovery
"""

import asyncio
import time
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from utils.logger import setup_logging

logger = setup_logging()


class FallbackLevel(Enum):
    """Levels of fallback severity"""
    RETRY = "retry"                    # Simple retry
    BACKUP_MODEL = "backup_model"      # Switch to backup model
    CACHE = "cache"                    # Use cached result
    DEGRADE = "degrade"                # Reduce functionality
    FAIL = "fail"                      # Graceful failure


@dataclass
class FallbackConfig:
    """Configuration for fallback behavior"""
    max_retries: int = 3
    retry_delay: float = 1.0
    backoff_multiplier: float = 2.0
    backup_models: List[str] = None
    timeout_seconds: float = 30.0
    use_cache: bool = True
    
    def __post_init__(self):
        if self.backup_models is None:
            self.backup_models = [
                "stepfun/step-3.5-flash:free",
                "google/gemini-2.0-flash-001",
                "anthropic/claude-3-haiku"  # Fallback options
            ]


class FallbackChain:
    """
    Implements OpenClaw-style graceful degradation
    Chain: Retry → Backup Model → Cache → Degrade → Fail
    """
    
    def __init__(self, config: FallbackConfig = None):
        self.config = config or FallbackConfig()
        self.cache: Dict[str, Any] = {}
        self.failure_counts: Dict[str, int] = {}
        self.last_failure_time: Dict[str, float] = {}
    
    async def execute_with_fallback(
        self,
        operation: Callable,
        operation_name: str,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute an operation with full fallback chain
        
        Args:
            operation: The function to execute
            operation_name: Name for logging/cache key
            *args, **kwargs: Arguments for operation
        
        Returns:
            Result dict with status and data
        """
        cache_key = f"{operation_name}_{hash(str(args))}_{hash(str(kwargs))}"
        
        # Level 1: Try primary execution with retries
        result = await self._try_with_retry(operation, operation_name, *args, **kwargs)
        if result["status"] == "success":
            if self.config.use_cache:
                self.cache[cache_key] = result
            return result
        
        # Level 2: Try backup models (for LLM operations)
        if self._is_llm_operation(operation_name):
            backup_result = await self._try_backup_models(operation, operation_name, *args, **kwargs)
            if backup_result["status"] == "success":
                logger.info(f"[Fallback] Backup model succeeded for {operation_name}")
                return backup_result
        
        # Level 3: Check cache
        if self.config.use_cache and cache_key in self.cache:
            logger.warning(f"[Fallback] Returning cached result for {operation_name}")
            cached = self.cache[cache_key].copy()
            cached["from_cache"] = True
            return cached
        
        # Level 4: Degrade functionality
        degraded = await self._try_degraded_mode(operation_name, *args, **kwargs)
        if degraded:
            logger.warning(f"[Fallback] Using degraded mode for {operation_name}")
            return degraded
        
        # Level 5: Graceful failure
        logger.error(f"[Fallback] All fallbacks exhausted for {operation_name}")
        return {
            "status": "failed",
            "error": f"All fallback strategies exhausted for {operation_name}",
            "operation": operation_name,
            "fallback_level": FallbackLevel.FAIL.value
        }
    
    async def _try_with_retry(
        self,
        operation: Callable,
        operation_name: str,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """Try operation with exponential backoff retry"""
        delay = self.config.retry_delay
        
        for attempt in range(self.config.max_retries):
            try:
                # Check circuit breaker
                if self._is_circuit_open(operation_name):
                    logger.warning(f"[Fallback] Circuit breaker open for {operation_name}, skipping attempt {attempt + 1}")
                    await asyncio.sleep(delay)
                    delay *= self.config.backoff_multiplier
                    continue
                
                # Execute with timeout
                result = await asyncio.wait_for(
                    operation(*args, **kwargs) if asyncio.iscoroutinefunction(operation) 
                    else asyncio.to_thread(operation, *args, **kwargs),
                    timeout=self.config.timeout_seconds
                )
                
                # Success - reset failure count
                self.failure_counts[operation_name] = 0
                return {
                    "status": "success",
                    "data": result,
                    "attempt": attempt + 1,
                    "fallback_level": None
                }
                
            except asyncio.TimeoutError:
                logger.warning(f"[Fallback] Timeout on attempt {attempt + 1} for {operation_name}")
                self._record_failure(operation_name)
                
            except Exception as e:
                logger.warning(f"[Fallback] Error on attempt {attempt + 1} for {operation_name}: {e}")
                self._record_failure(operation_name)
                
                # Check if error is retryable
                if not self._is_retryable_error(e):
                    logger.error(f"[Fallback] Non-retryable error for {operation_name}: {e}")
                    break
            
            # Wait before retry
            if attempt < self.config.max_retries - 1:
                await asyncio.sleep(delay)
                delay *= self.config.backoff_multiplier
        
        return {
            "status": "failed",
            "error": f"Max retries ({self.config.max_retries}) exceeded",
            "operation": operation_name,
            "fallback_level": FallbackLevel.RETRY.value
        }
    
    async def _try_backup_models(
        self,
        operation: Callable,
        operation_name: str,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """Try with backup LLM models"""
        for model in self.config.backup_models:
            try:
                logger.info(f"[Fallback] Trying backup model {model} for {operation_name}")
                
                # Modify kwargs to use backup model
                modified_kwargs = kwargs.copy()
                modified_kwargs["model_override"] = model
                
                result = await asyncio.wait_for(
                    operation(*args, **modified_kwargs) if asyncio.iscoroutinefunction(operation)
                    else asyncio.to_thread(operation, *args, **modified_kwargs),
                    timeout=self.config.timeout_seconds
                )
                
                return {
                    "status": "success",
                    "data": result,
                    "model_used": model,
                    "fallback_level": FallbackLevel.BACKUP_MODEL.value
                }
                
            except Exception as e:
                logger.warning(f"[Fallback] Backup model {model} failed: {e}")
                continue
        
        return {
            "status": "failed",
            "error": "All backup models exhausted",
            "fallback_level": FallbackLevel.BACKUP_MODEL.value
        }
    
    async def _try_degraded_mode(
        self,
        operation_name: str,
        *args,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Try degraded/simplified version of operation"""
        # Degradation strategies by operation type
        degradation_map = {
            "vector_search": self._degrade_vector_search,
            "code_execution": self._degrade_code_execution,
            "web_search": self._degrade_web_search,
        }
        
        if operation_name in degradation_map:
            try:
                return await degradation_map[operation_name](*args, **kwargs)
            except Exception as e:
                logger.error(f"[Fallback] Degraded mode failed: {e}")
        
        return None
    
    async def _degrade_vector_search(self, *args, **kwargs) -> Dict[str, Any]:
        """Degrade to simple keyword search"""
        query = args[0] if args else kwargs.get("query", "")
        logger.info(f"[Fallback] Degrading vector search to keyword search for: {query}")
        
        # Return a simplified response
        return {
            "status": "success",
            "data": [],
            "message": "Vector search unavailable, returning empty results",
            "fallback_level": FallbackLevel.DEGRADE.value
        }
    
    async def _degrade_code_execution(self, *args, **kwargs) -> Dict[str, Any]:
        """Degrade code execution to syntax check only"""
        code = args[0] if args else kwargs.get("code", "")
        logger.info(f"[Fallback] Degrading code execution to syntax check")
        
        try:
            compile(code, '<string>', 'exec')
            return {
                "status": "success",
                "data": "Code syntax is valid (execution skipped in degraded mode)",
                "fallback_level": FallbackLevel.DEGRADE.value
            }
        except SyntaxError as e:
            return {
                "status": "success",
                "data": f"Syntax error: {e}",
                "fallback_level": FallbackLevel.DEGRADE.value
            }
    
    async def _degrade_web_search(self, *args, **kwargs) -> Dict[str, Any]:
        """Degrade web search to offline mode"""
        logger.info(f"[Fallback] Web search unavailable in offline mode")
        return {
            "status": "success",
            "data": "Web search unavailable (offline mode)",
            "fallback_level": FallbackLevel.DEGRADE.value
        }
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if an error should trigger a retry"""
        retryable_errors = (
            TimeoutError,
            ConnectionError,
            ConnectionResetError,
            ConnectionRefusedError,
        )
        return isinstance(error, retryable_errors) or "rate limit" in str(error).lower()
    
    def _is_llm_operation(self, operation_name: str) -> bool:
        """Check if operation is an LLM call"""
        llm_operations = ["llm_invoke", "chat", "generate", "complete"]
        return any(op in operation_name.lower() for op in llm_operations)
    
    def _record_failure(self, operation_name: str):
        """Record a failure for circuit breaker logic"""
        self.failure_counts[operation_name] = self.failure_counts.get(operation_name, 0) + 1
        self.last_failure_time[operation_name] = time.time()
    
    def _is_circuit_open(self, operation_name: str) -> bool:
        """Check if circuit breaker should prevent execution"""
        failure_count = self.failure_counts.get(operation_name, 0)
        last_failure = self.last_failure_time.get(operation_name, 0)
        
        # Open circuit after 5 failures in 60 seconds
        if failure_count >= 5 and (time.time() - last_failure) < 60:
            return True
        
        # Reset after cooldown period (5 minutes)
        if failure_count >= 5 and (time.time() - last_failure) > 300:
            self.failure_counts[operation_name] = 0
            return False
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get fallback statistics"""
        return {
            "cache_size": len(self.cache),
            "failure_counts": self.failure_counts.copy(),
            "circuit_breakers": [
                op for op, count in self.failure_counts.items() 
                if count >= 5
            ]
        }


# Global instance
_fallback_chain: Optional[FallbackChain] = None


def get_fallback_chain() -> FallbackChain:
    """Get global fallback chain instance"""
    global _fallback_chain
    if _fallback_chain is None:
        _fallback_chain = FallbackChain()
    return _fallback_chain


async def execute_with_fallback(operation: Callable, name: str, *args, **kwargs) -> Dict[str, Any]:
    """Convenience function for fallback execution"""
    chain = get_fallback_chain()
    return await chain.execute_with_fallback(operation, name, *args, **kwargs)
