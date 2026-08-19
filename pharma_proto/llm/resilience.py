"""Provider-neutral timeout, retry, and safe error classification."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from pydantic import ValidationError

from pharma_proto.errors import (
    LLM_AUTH_ERROR,
    LLM_RATE_ERROR,
    LLM_RESPONSE_ERROR,
    LLM_TIMEOUT_ERROR,
    LLM_UPSTREAM_ERROR,
)

T = TypeVar("T")


@dataclass(frozen=True)
class LLMFailure(Exception):
    code: str
    retryable: bool
    request_id: str | None = None
    retry_after: float | None = None
    status_code: int = 502
    provider_code: int | None = None
    provider_status: str | None = None
    provider_reason: str | None = None

    def __str__(self) -> str:
        return self.code


@dataclass(frozen=True)
class RetryPolicy:
    timeout_seconds: float = 30.0
    max_attempts: int = 2
    max_retry_after_seconds: float = 5.0

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0 or self.max_attempts < 1:
            raise ValueError("invalid retry policy")


def _status_code(error: Exception) -> int | None:
    for name in ("status_code", "status", "code"):
        value = getattr(error, name, None)
        if isinstance(value, int):
            return value
    response = getattr(error, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None


def _request_id(error: Exception) -> str | None:
    for name in ("request_id", "_request_id"):
        value = getattr(error, name, None)
        if value:
            return str(value)[:200]
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", {}) or {}
    for name in ("x-request-id", "request-id"):
        value = headers.get(name)
        if value:
            return str(value)[:200]
    return None


def _retry_after(error: Exception) -> float | None:
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", {}) or {}
    value = headers.get("retry-after") or headers.get("Retry-After")
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _provider_status(error: Exception) -> str | None:
    for name in ("status", "type"):
        value = getattr(error, name, None)
        if isinstance(value, str) and value:
            return str(value)[:80]
    return None


def _provider_reason(error: Exception) -> str | None:
    details = getattr(error, "details", None)
    if isinstance(details, dict):
        payload = details.get("error", details)
        if isinstance(payload, dict):
            items = payload.get("details", [])
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and isinstance(item.get("reason"), str):
                        return str(item["reason"])[:80]

    body = getattr(error, "body", None)
    if isinstance(body, dict):
        payload = body.get("error", body)
        if isinstance(payload, dict):
            message = str(payload.get("message", "")).casefold()
            if "output_config" in message or "schema" in message:
                return "STRUCTURED_OUTPUT_INVALID"
            if "tool" in message:
                return "TOOL_CONFIGURATION_INVALID"
            if "model" in message:
                return "MODEL_INVALID"
            if "max_tokens" in message:
                return "MAX_TOKENS_INVALID"
            if message:
                return "INVALID_REQUEST"
    return None


def classify_provider_error(error: Exception) -> LLMFailure:
    if isinstance(error, LLMFailure):
        return error
    status = _status_code(error)
    request_id = _request_id(error)
    retry_after = _retry_after(error)
    provider_status = _provider_status(error)
    provider_reason = _provider_reason(error)
    class_name = error.__class__.__name__.casefold()

    if status in {401, 403} or "authentication" in class_name or "permission" in class_name:
        return LLMFailure(
            LLM_AUTH_ERROR,
            False,
            request_id,
            status_code=401,
            provider_code=status,
            provider_status=provider_status,
            provider_reason=provider_reason,
        )
    if status == 429 or "ratelimit" in class_name or "rate_limit" in class_name:
        return LLMFailure(
            LLM_RATE_ERROR,
            True,
            request_id,
            retry_after,
            status_code=429,
            provider_code=status,
            provider_status=provider_status,
            provider_reason=provider_reason,
        )
    if status == 408 or isinstance(error, TimeoutError) or "timeout" in class_name:
        return LLMFailure(
            LLM_TIMEOUT_ERROR,
            True,
            request_id,
            status_code=504,
            provider_code=status,
            provider_status=provider_status,
            provider_reason=provider_reason,
        )
    if status is not None and status >= 500:
        return LLMFailure(
            LLM_UPSTREAM_ERROR,
            True,
            request_id,
            status_code=502,
            provider_code=status,
            provider_status=provider_status,
            provider_reason=provider_reason,
        )
    if isinstance(error, (ConnectionError, OSError)) or "connection" in class_name:
        return LLMFailure(
            LLM_UPSTREAM_ERROR,
            True,
            request_id,
            status_code=502,
            provider_code=status,
            provider_status=provider_status,
            provider_reason=provider_reason,
        )
    if isinstance(error, (ValidationError, ValueError, TypeError, json_error_type())):
        return LLMFailure(
            LLM_RESPONSE_ERROR,
            False,
            request_id,
            status_code=502,
            provider_code=status,
            provider_status=provider_status,
            provider_reason=provider_reason,
        )
    return LLMFailure(
        LLM_UPSTREAM_ERROR,
        False,
        request_id,
        status_code=502,
        provider_code=status,
        provider_status=provider_status,
        provider_reason=provider_reason,
    )


def json_error_type() -> type[Exception]:
    from json import JSONDecodeError

    return JSONDecodeError


def run_with_retry(
    operation: Callable[[], T],
    *,
    policy: RetryPolicy,
    sleeper: Callable[[float], None] = time.sleep,
) -> T:
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return operation()
        except Exception as error:
            failure = classify_provider_error(error)
            if not failure.retryable or attempt >= policy.max_attempts:
                raise failure from None
            delay = failure.retry_after if failure.retry_after is not None else float(2 ** (attempt - 1))
            if delay > policy.max_retry_after_seconds:
                raise failure from None
            sleeper(delay)
    raise AssertionError("retry loop did not return or raise")


__all__ = [
    "LLMFailure",
    "RetryPolicy",
    "classify_provider_error",
    "run_with_retry",
]
