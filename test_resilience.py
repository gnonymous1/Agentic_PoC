import asyncio
import time
from core.llm_router import LLMRouter, Provider, ModelProfile
from core.resilience import CircuitBreakerOpenException

# Mock config
MOCK_CONFIG = {
    "providers": {
        "openai": {"api_key": "dummy"},
        "ollama": {"base_url": "http://localhost:11434"}
    }
}

async def mock_fail(*args, **kwargs):
    raise Exception("Simulated API Retryable Error")

async def test_circuit_breaker():
    print("\n[TEST] Testing Circuit Breaker...")
    
    router = LLMRouter(MOCK_CONFIG)
    
    # Override provider client with a mock that always fails
    router._call_openai_compatible = mock_fail
    
    # We expect 3 failures to open the circuit (default threshold is 3)
    model_id = "gpt-4o"
    curr_provider = "openai"
    
    print(f"  Circuit State: {router.circuit_breakers[curr_provider].state}")
    
    # 1. Trigger failures
    for i in range(3):
        try:
            print(f"  Sending request {i+1}...")
            await router.complete([{"role": "user", "content": "test"}], task_type="general", priority="balanced")
        except Exception as e:
            print(f"  Caught expected error: {e}")

    # 2. Verify Circuit is OPEN
    state = router.circuit_breakers[curr_provider].state
    print(f"  Circuit State after 3 failures: {state}")
    
    if state.value != "open":
        print("  [FAIL] Circuit did not open!")
        return

    # 3. Verify Fail Fast
    print("  Sending request 4 (should fail fast)...")
    try:
        await router.complete([{"role": "user", "content": "test"}], task_type="general")
        print("  [FAIL] Request succeeded unexpectedly!")
    except CircuitBreakerOpenException:
        print("  [PASS] Caught CircuitBreakerOpenException (Fail Fast works)")
    except Exception as e:
        print(f"  [FAIL] Caught wrong exception: {type(e)}")

async def test_rate_limiter():
    print("\n[TEST] Testing Rate Limiter...")
    router = LLMRouter(MOCK_CONFIG)
    curr_provider = "openai"
    
    # Manually set low limit: 2 requests per 2 seconds
    limiter = router.rate_limiters[curr_provider]
    limiter.rate = 2
    limiter.period = 2
    limiter.tokens = 2
    
    start = time.time()
    
    # Req 1 (Instant)
    await limiter.acquire()
    print(f"  Req 1 acquired at {time.time() - start:.2f}s")
    
    # Req 2 (Instant)
    await limiter.acquire()
    print(f"  Req 2 acquired at {time.time() - start:.2f}s")
    
    # Req 3 (Should wait ~1s)
    print("  Req 3 requesting (should wait)...")
    await limiter.acquire()
    print(f"  Req 3 acquired at {time.time() - start:.2f}s")
    
    if (time.time() - start) < 0.8:
         print("  [FAIL] Rate limiter didn't wait long enough!")
    else:
         print("  [PASS] Rate limiter waited correctly")

async def test_retry_logic():
    print("\n[TEST] Testing Retry Logic...")
    router = LLMRouter(MOCK_CONFIG)
    
    # Mock that fails 2 times then succeeds
    call_count = 0
    async def mock_flaky(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            print(f"  [Mock] Flaky call {call_count} failing...")
            raise Exception("Simulated Flaky Error")
        print(f"  [Mock] Flaky call {call_count} succeeding!")
        return {"usage": {}, "choices": [{"message": {"content": "Success"}}]}

    # We need to monkeypatch the underlying implementation that is wrapped
    # But wait, we decorated `_call_openai_compatible_impl`. 
    # If we replace `_call_openai_compatible`, we bypass the decorator?
    # No, `_call_openai_compatible` calls `_call_openai_compatible_impl`.
    # `_call_openai_compatible_impl` IS the decorated function.
    # So we need to patch `router._call_openai_compatible_impl`.
    # BUT `_call_openai_compatible_impl` is an instance method.
    # The decorator returns a wrapper.
    # So `router._call_openai_compatible_impl` IS the wrapper.
    # To test the retry, we need the *inner* logic to fail. 
    # We can't easily replace the inner logic of a decorated method on an instance without messing up the binding?
    # Actually, we can just replace `router._call_openai_compatible` with a new decorated function?
    
    # Or better: `LLMRouter` calls `_call_openai_compatible_impl`.
    # Let's replace `router._call_openai_compatible_impl` with our flaky mock, BUT we need to RE-APPLY the decorator.
    
    from core.resilience import retry_with_backoff
    
    @retry_with_backoff(retries=3, backoff_in_seconds=0.1)
    async def flaky_wrapper(*args, **kwargs):
        return await mock_flaky(*args, **kwargs)
        
    router._call_openai_compatible_impl = flaky_wrapper
    
    # Override the public caller to just call our patched impl (to match the real code structure)
    # router._call_openai_compatible is: return await self._call_openai_compatible_impl(...)
    # So patching `_call_openai_compatible_impl` should be enough IF `_call_openai_compatible` calls it by name.
    # Yes it does.
    
    try:
        response = await router.complete([{"role": "user", "content": "test"}], task_type="general")
        print("  [PASS] Request succeeded after retries")
        if call_count == 3:
             print(f"  [PASS] Retried exactly {call_count} times")
        else:
             print(f"  [FAIL] Unexpected call count: {call_count}")
             
    except Exception as e:
        print(f"  [FAIL] Request failed: {e}")

async def main():
    await test_circuit_breaker()
    await test_rate_limiter()
    await test_retry_logic()

if __name__ == "__main__":
    asyncio.run(main())
