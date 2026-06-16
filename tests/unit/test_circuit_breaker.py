import pytest

from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
from app.core.errors import CircuitBreakerOpen


@pytest.mark.asyncio
async def test_circuit_breaker_closed():
    cb = CircuitBreaker("test_service")
    result = await cb.call(lambda: "success")
    assert result == "success"
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_breaker_opens_on_failures():
    cb = CircuitBreaker("test_service", CircuitBreakerConfig(failure_threshold=3, recovery_timeout=1))
    for _ in range(3):
        with pytest.raises(ValueError):
            await cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
    assert cb.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_circuit_breaker_open_raises():
    cb = CircuitBreaker("test_service", CircuitBreakerConfig(failure_threshold=1, recovery_timeout=60))
    with pytest.raises(ValueError):
        await cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
    with pytest.raises(CircuitBreakerOpen):
        await cb.call(lambda: "should not reach")
