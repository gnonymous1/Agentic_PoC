import asyncio
import time
import random
from core.resilience import CircuitBreaker, RateLimiter, RetryWithBackoff, CircuitBreakerOpenException

async def test_resilience_stack():
    # 1. Test Circuit Breaker
    print("Testing Circuit Breaker...")
    cb = CircuitBreaker(name="test_cb", failure_threshold=2, recovery_timeout=2)
    
    async def failing_func():
        raise Exception("Service Down")
    
    # Trip the circuit
    try: await cb.call(failing_func)
    except: pass
    try: await cb.call(failing_func)
    except: pass
    
    print(f"Circuit State after 2 failures: {cb.state.value}")
    if cb.state.value == "open":
        print("PASS: Circuit tripped")
    else:
        print("FAIL: Circuit did not trip")
    
    try:
        await cb.call(failing_func)
    except CircuitBreakerOpenException:
        print("PASS: Fast-fail verified")
    except:
        print("FAIL: Did not raise CircuitBreakerOpenException")

    print("Waiting for recovery timeout...")
    await asyncio.sleep(2.1)
    
    async def success_func():
        return "OK"
    
    res = await cb.call(success_func)
    print(f"Circuit State after 1 success (Half-Open): {cb.state.value}")
    # Current implementation requires 2 successes to close
    res = await cb.call(success_func)
    print(f"Circuit State after 2 successes: {cb.state.value}")
    if cb.state.value == "closed":
        print("PASS: Circuit recovered")
    else:
        print("FAIL: Circuit did not recover")

    # 2. Test Rate Limiter
    print("\nTesting Rate Limiter...")
    rl = RateLimiter(rate=5, period=1) # 5 req/sec
    start = time.time()
    for i in range(5):
        await rl.acquire()
    print(f"5 requests took {time.time() - start:.2f}s (should be near 0)")
    
    start = time.time()
    await rl.acquire() # 6th request
    elapsed = time.time() - start
    print(f"6th request took {elapsed:.2f}s (should be ~0.2s)")
    if 0.15 <= elapsed <= 0.35:
        print("PASS: Rate limiting verified")
    else:
        print("FAIL: Rate limiting timing off")

    # 3. Test Retry with Backoff
    print("\nTesting Retry with Backoff...")
    retry = RetryWithBackoff(max_retries=2, base_delay=0.1, jitter=False)
    
    call_count = 0
    async def flaky_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Flaky Error")
        return "Success"
    
    start = time.time()
    res = await retry.execute(flaky_func)
    elapsed = time.time() - start
    print(f"Flaky func took {elapsed:.2f}s and {call_count} attempts")
    if res == "Success" and call_count == 3:
        print("PASS: Retry logic verified")
    else:
        print("FAIL: Retry failed")

if __name__ == "__main__":
    asyncio.run(test_resilience_stack())
