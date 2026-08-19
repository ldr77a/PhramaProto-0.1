"""Stable, safe error values for local HTTP responses."""

from dataclasses import dataclass

APP_START_ERROR = "APP-START-001"
DB_INTEGRITY_ERROR = "DB-INTEGRITY-001"
DB_VERSION_ERROR = "DB-VERSION-001"
REQUEST_ERROR = "REQUEST-001"
LLM_KEY_ERROR = "LLM-KEY-001"
LLM_AUTH_ERROR = "LLM-AUTH-001"
LLM_RATE_ERROR = "LLM-RATE-001"
LLM_TIMEOUT_ERROR = "LLM-TIMEOUT-001"
LLM_UPSTREAM_ERROR = "LLM-UPSTREAM-001"
LLM_RESPONSE_ERROR = "LLM-RESPONSE-001"
RELEASE_BUILD_ERROR = "RELEASE-BUILD-001"
APP_ALREADY_RUNNING_ERROR = "APP-ALREADY-RUNNING-001"


@dataclass(frozen=True)
class AppError(Exception):
    """An error whose public representation never includes private detail."""

    code: str
    status_code: int = 500

    def __str__(self) -> str:
        return self.code
