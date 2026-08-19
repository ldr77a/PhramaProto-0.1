"""Process-local API key storage with no persistence hooks."""

from __future__ import annotations

import threading

from pharma_proto.llm.catalog import MODEL_CATALOG


class MemoryKeyStore:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _validate_provider(provider: str) -> None:
        if provider not in MODEL_CATALOG:
            raise ValueError("unsupported provider")

    def set(self, provider: str, key: str) -> None:
        self._validate_provider(provider)
        value = key.strip()
        if not value:
            raise ValueError("API key cannot be blank")
        with self._lock:
            self._values[provider] = value

    def get(self, provider: str) -> str | None:
        self._validate_provider(provider)
        with self._lock:
            return self._values.get(provider)

    def configured(self, provider: str) -> bool:
        return self.get(provider) is not None

    def clear(self) -> None:
        with self._lock:
            self._values.clear()

    def __repr__(self) -> str:
        with self._lock:
            providers = tuple(sorted(self._values))
        return f"MemoryKeyStore(configured={providers!r})"

    __str__ = __repr__


__all__ = ["MemoryKeyStore"]
