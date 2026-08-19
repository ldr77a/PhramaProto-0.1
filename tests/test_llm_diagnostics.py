from __future__ import annotations

import json
from pathlib import Path

from google.genai.errors import ClientError

from pharma_proto.diagnostics import configure_safe_logging
from pharma_proto.llm.resilience import classify_provider_error


def test_google_client_error_keeps_safe_provider_diagnostics() -> None:
    error = ClientError(
        400,
        {
            "error": {
                "code": 400,
                "message": "API key not valid. Please pass a valid API key.",
                "status": "INVALID_ARGUMENT",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                        "reason": "API_KEY_INVALID",
                        "domain": "googleapis.com",
                    }
                ],
            }
        },
    )

    failure = classify_provider_error(error)

    assert getattr(failure, "provider_code", None) == 400
    assert getattr(failure, "provider_status", None) == "INVALID_ARGUMENT"
    assert getattr(failure, "provider_reason", None) == "API_KEY_INVALID"


def test_safe_log_records_provider_codes_without_error_message(tmp_path: Path) -> None:
    diagnostics = configure_safe_logging(tmp_path)

    diagnostics.record(
        event="llm_error",
        code="LLM-UPSTREAM-001",
        provider_code=400,
        provider_status="INVALID_ARGUMENT",
        provider_reason="API_KEY_INVALID",
    )
    diagnostics.close()

    row = json.loads((tmp_path / "app.log").read_text(encoding="utf-8"))
    assert row["provider_code"] == "400"
    assert row["provider_status"] == "INVALID_ARGUMENT"
    assert row["provider_reason"] == "API_KEY_INVALID"
    assert "message" not in row
