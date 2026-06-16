import hashlib
import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


class VersionRecord:
    def __init__(self, hash_value: str, text: str, timestamp: datetime, metadata: dict):
        self.hash_value = hash_value
        self.text = text
        self.timestamp = timestamp
        self.metadata = metadata


class PromptRegistry:
    def __init__(self):
        self._store: dict[str, list[VersionRecord]] = {}

    def register(self, slug: str, text: str, metadata: dict | None = None) -> str:
        hash_value = hashlib.sha256(text.encode("utf-8")).hexdigest()
        record = VersionRecord(
            hash_value=hash_value,
            text=text,
            timestamp=datetime.now(UTC),
            metadata=metadata or {},
        )
        if slug not in self._store:
            self._store[slug] = []
        self._store[slug].append(record)
        logger.info("Registered prompt '%s' — hash=%s", slug, hash_value[:12])
        return hash_value

    def get_active(self, slug: str) -> str:
        versions = self._store.get(slug)
        if not versions:
            raise KeyError(f"No prompt registered for slug '{slug}'")
        return versions[-1].text

    def rollback(self, slug: str, target_hash: str) -> str:
        versions = self._store.get(slug)
        if not versions:
            raise KeyError(f"No prompt registered for slug '{slug}'")
        for i, record in enumerate(versions):
            if record.hash_value == target_hash:
                self._store[slug] = versions[: i + 1]
                logger.info("Rolled back prompt '%s' to hash=%s", slug, target_hash[:12])
                return record.text
        raise KeyError(f"Hash '{target_hash[:12]}' not found for slug '{slug}'")

    def get_active_hash(self, slug: str) -> str:
        versions = self._store.get(slug)
        if not versions:
            raise KeyError(f"No prompt registered for slug '{slug}'")
        return versions[-1].hash_value

    def register_from_module(self, slug: str, module_path: str, prompt_text: str) -> str:
        return self.register(
            slug,
            prompt_text,
            metadata={"source": module_path, "type": "system_prompt"},
        )


prompt_registry = PromptRegistry()
