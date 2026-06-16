"""
Dependency injection container for the GNONE platform.
Provides lazy-initialized singletons for all external services.
"""

from dataclasses import dataclass


@dataclass
class Container:
    _initialized: bool = False

    async def init(self):
        if self._initialized:
            return
        self._initialized = True

    async def shutdown(self):
        self._initialized = False


container = Container()
