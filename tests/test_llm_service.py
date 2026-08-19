from __future__ import annotations

import json
from types import SimpleNamespace

from pharma_proto.llm.resilience import RetryPolicy
from pharma_proto.llm.schema import ParsedRequest
from pharma_proto.llm.service import LLMService


class _RecordingGeminiModels:
    def __init__(self) -> None:
        self.config = None

    def generate_content(self, *, model, contents, config):
        self.config = config
        return SimpleNamespace(
            text=json.dumps(
                {
                    "apis": [{"name": "Acetaminophen", "dose_mg": 500}],
                    "dosage_form": "tablet",
                    "process": "direct compression",
                    "n_candidates": 3,
                }
            )
        )


class _RecordingGeminiClient:
    def __init__(self) -> None:
        self.models = _RecordingGeminiModels()

    def close(self) -> None:
        pass


def test_gemini_uses_supported_pydantic_response_schema() -> None:
    client = _RecordingGeminiClient()
    service = LLMService(
        client_factories={"gemini": lambda *args, **kwargs: client},
        policy=RetryPolicy(max_attempts=1),
    )

    formulation = service.parse(
        "gemini",
        "cheap",
        "test-key",
        "아세트아미노펜 500 mg 속방정제",
    )

    assert formulation.apis[0].name == "Acetaminophen"
    assert formulation.apis[0].dose_mg == 500
    assert formulation.process == "direct compression"
    assert formulation.n_candidates == 3
    assert client.models.config.response_schema is ParsedRequest
    assert client.models.config.response_json_schema is None
