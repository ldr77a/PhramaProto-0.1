"""Bounded, allowlisted diagnostics for the local researcher application."""

from __future__ import annotations

import json
import logging
from collections import deque
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Mapping

from pharma_proto import __version__

_ALLOWED_DATABASE_FIELDS = (
    "status",
    "snapshot_id",
    "schema_version",
    "node_count",
    "relationship_count",
)


def _safe_text(value: object | None, *, limit: int = 200) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or any(marker in text.casefold() for marker in ("api_key", "password", "bearer ")):
        return None
    return text[:limit]


class SafeDiagnostics:
    def __init__(self, logger: logging.Logger, handler: RotatingFileHandler) -> None:
        self._logger = logger
        self._handler = handler
        self._recent_codes: deque[str] = deque(maxlen=20)
        self._closed = False

    def record(
        self,
        *,
        event: str,
        code: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        snapshot_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        if self._closed:
            return
        row = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": _safe_text(event, limit=80),
            "app_version": __version__,
        }
        optional = {
            "code": code,
            "provider": provider,
            "model": model,
            "snapshot_id": snapshot_id,
            "request_id": request_id,
        }
        for key, value in optional.items():
            safe = _safe_text(value)
            if safe is not None:
                row[key] = safe
        if code:
            self._recent_codes.append(str(code)[:80])
        self._logger.info(json.dumps(row, sort_keys=True, separators=(",", ":")))

    def summary(
        self,
        *,
        repository_health: Mapping[str, object],
        provider_status: Mapping[str, bool],
    ) -> dict[str, object]:
        database = {
            key: repository_health[key]
            for key in _ALLOWED_DATABASE_FIELDS
            if key in repository_health
        }
        return {
            "app_version": __version__,
            "database": database,
            "providers": dict(provider_status),
            "recent_error_codes": list(self._recent_codes),
        }

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._logger.removeHandler(self._handler)
        self._handler.close()


def configure_safe_logging(
    log_directory: str | Path,
    *,
    max_bytes: int = 524_288,
    backup_count: int = 3,
) -> SafeDiagnostics:
    directory = Path(log_directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "app.log"
    logger = logging.getLogger(f"pharma_proto.safe.{hash(path.resolve())}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for old_handler in tuple(logger.handlers):
        logger.removeHandler(old_handler)
        old_handler.close()
    handler = RotatingFileHandler(
        path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return SafeDiagnostics(logger, handler)


__all__ = ["SafeDiagnostics", "configure_safe_logging"]
