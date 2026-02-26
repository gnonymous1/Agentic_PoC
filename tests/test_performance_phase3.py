import asyncio
import time
from core.llm_router import LLMRouter
from core.monitoring import ObservabilityEngine

async def test_performance_optimization():
    config = {
        "providers": {
            "openai": {"api_key": "test_key"}
        },
        "semantic_cache_threshold": 0.90
    }
    obs = ObservabilityEngine(config)
    router = LLMRouter(config, observability=obs)

    # Mock the LLM call to avoid actual API hits
    async def mock_call(model, messages, **kwargs):
        return {
            "content": "Madrid is the capital of Spain.",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}
        }
    
    router._call_openai_compatible = mock_call

    print("--- Testing L1/L2 Cache ---")
    prompt = [{"role": "user", "content": "What is the capital of Spain?"}]
    
    start = time.time()
    res1 = await router.complete(prompt, task_type="general")
    print(f"First call (Miss): {time.time() - start:.4f}s")

    start = time.time()
    res2 = await router.complete(prompt, task_type="general")
    print(f"Second call (L1 Hit): {time.time() - start:.4f}s")
    if res1["content"] == res2["content"]:
        print("PASS: Exact match cache works")

    print("\n--- Testing Semantic Cache ---")
    # Slightly different prompt
    prompt_sem = [{"role": "user", "content": "Tell me the capital city of Spain?"}]
    
    start = time.time()
    res3 = await router.complete(prompt_sem, task_type="general")
    print(f"Semantic call (Should be Hit): {time.time() - start:.4f}s")
    
    if res3["content"] == res1["content"]:
        print("PASS: Semantic cache match found")
    else:
        print(f"FAIL: Semantic match failed. Got: {res3['content']}")

    print("\n--- Testing Task Type Exclusion ---")
    # Task type coding should NOT use semantic cache (usually needs exactness)
    prompt_code = [{"role": "user", "content": "Tell me the capital city of Spain?"}]
    call_count = 0
    async def mock_call_v2(model, messages, **kwargs):
        nonlocal call_count
        call_count += 1
        return {"content": "New Response", "usage": {}}
    
    router._call_openai_compatible = mock_call_v2
    await router.complete(prompt_code, task_type="coding")
    if call_count == 1:
        print("PASS: Semantic cache bypassed for 'coding' task type")
    else:
        print("FAIL: Semantic cache used for 'coding' task type")

if __name__ == "__main__":
    asyncio.run(test_performance_optimization())
