from __future__ import annotations

import json
from copy import deepcopy
from types import SimpleNamespace

from pharma_proto.llm.resilience import RetryPolicy
from pharma_proto.llm.service import LLMService


class _RecordingGeminiModels:
    def __init__(self) -> None:
        self.config = None
        self.submitted_schema = None

    def generate_content(self, *, model, contents, config):
        from google.genai import _transformers

        self.config = config
        self.submitted_schema = deepcopy(config.response_schema)
        _transformers.t_schema(None, config.response_schema)
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


def test_gemini_uses_a_schema_accepted_by_the_installed_sdk() -> None:
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
    assert client.models.config.response_json_schema is None


def test_gemini_schema_only_uses_portable_structured_output_fields() -> None:
    client = _RecordingGeminiClient()
    service = LLMService(
        client_factories={"gemini": lambda *args, **kwargs: client},
        policy=RetryPolicy(max_attempts=1),
    )

    service.parse("gemini", "normal", "test-key", "아세트아미노펜 500 mg 정제")

    allowed = {"type", "properties", "required", "items"}
    pending = [client.models.submitted_schema]
    while pending:
        node = pending.pop()
        assert isinstance(node, dict)
        assert set(node) <= allowed
        properties = node.get("properties", {})
        assert isinstance(properties, dict)
        pending.extend(properties.values())
        if "items" in node:
            pending.append(node["items"])
