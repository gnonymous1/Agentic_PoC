"""Tests for the PromptRegistry."""

import hashlib

import pytest


class PromptRegistry:
    """Simple in-memory prompt registry for testing."""

    def __init__(self):
        self._versions: dict[str, list[tuple[str, str]]] = {}

    def register(self, name: str, version: str, prompt: str) -> str:
        hash_val = hashlib.sha256(prompt.encode()).hexdigest()[:12]
        if name not in self._versions:
            self._versions[name] = []
        self._versions[name].append((version, hash_val))
        return hash_val

    def get_active(self, name: str) -> tuple[str, str] | None:
        versions = self._versions.get(name)
        if not versions:
            return None
        return versions[-1]

    def rollback(self, name: str, target_version: str | None = None) -> tuple[str, str] | None:
        versions = self._versions.get(name)
        if not versions or len(versions) < 2:
            return None
        if target_version is None:
            self._versions[name] = versions[:-1]
        else:
            idx = next((i for i, (v, _) in enumerate(versions) if v == target_version), -1)
            if idx == -1:
                return None
            self._versions[name] = versions[: idx + 1]
        return self.get_active(name)


@pytest.fixture
def registry():
    return PromptRegistry()


class TestPromptRegistry:
    def test_register_and_get_active(self, registry):
        h = registry.register("system_prompt", "1.0", "You are a helpful assistant.")
        assert h == hashlib.sha256(b"You are a helpful assistant.").hexdigest()[:12]
        active = registry.get_active("system_prompt")
        assert active == ("1.0", h)

    def test_get_active_nonexistent(self, registry):
        assert registry.get_active("nonexistent") is None

    def test_rollback(self, registry):
        registry.register("system_prompt", "1.0", "Prompt v1")
        registry.register("system_prompt", "2.0", "Prompt v2")
        active_before = registry.get_active("system_prompt")
        assert active_before[0] == "2.0"

        result = registry.rollback("system_prompt")
        active_after = registry.get_active("system_prompt")
        assert active_after[0] == "1.0"

    def test_rollback_single_version(self, registry):
        registry.register("test", "1.0", "Only one")
        assert registry.rollback("test") is None

    def test_rollback_to_specific_version(self, registry):
        registry.register("test", "1.0", "v1")
        registry.register("test", "2.0", "v2")
        registry.register("test", "3.0", "v3")
        result = registry.rollback("test", target_version="1.0")
        assert result is not None
        assert result[0] == "1.0"

    def test_hash_uniqueness(self, registry):
        h1 = registry.register("a", "1.0", "Hello world")
        h2 = registry.register("b", "1.0", "Hello world!")
        assert h1 != h2
