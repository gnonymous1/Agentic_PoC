"""
Unified health check aggregator for all GNONE dependencies.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

HealthCheckFn = Callable[[], Awaitable[bool]]


@dataclass
class HealthStatus:
    service: str
    healthy: bool
    latency_ms: float


class HealthRegistry:
    def __init__(self):
        self._checks: dict[str, HealthCheckFn] = {}

    def register(self, name: str, check_fn: HealthCheckFn):
        self._checks[name] = check_fn

    async def check_all(self) -> list[HealthStatus]:
        results = []

        async def run_check(name: str, fn: HealthCheckFn):
            import time
            start = time.perf_counter()
            try:
                ok = await fn()
            except Exception:
                ok = False
            elapsed = (time.perf_counter() - start) * 1000
            results.append(HealthStatus(name, ok, round(elapsed, 2)))

        tasks = [run_check(n, f) for n, f in self._checks.items()]
        await asyncio.gather(*tasks)
        return results

    @property
    def is_all_healthy(self) -> bool:
        return all(h.healthy for h in asyncio.run(self.check_all()))


health_registry = HealthRegistry()
