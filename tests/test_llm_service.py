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


class _RecordingClaudeMessages:
    def __init__(self) -> None:
        self.tool_choice = None
        self.tools = None

    def create(self, *, tool_choice, tools, **kwargs):
        self.tool_choice = tool_choice
        self.tools = tools
        return SimpleNamespace(
            content=[
                SimpleNamespace(type="text", text="요청을 구조화했습니다."),
                SimpleNamespace(
                    type="tool_use",
                    name="parse_formulation_request",
                    input={
                        "apis": [{"name": "Acetaminophen", "dose_mg": 500}],
                        "dosage_form": "tablet",
                        "disintegrant": ["Croscarmellose sodium"],
                        "release_profile": "immediate release",
                        "n_candidates": 3,
                    },
                ),
            ],
            stop_reason="tool_use",
        )


class _RecordingClaudeClient:
    def __init__(self) -> None:
        self.messages = _RecordingClaudeMessages()

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


def test_claude_parses_a_forced_tool_result_without_output_format() -> None:
    client = _RecordingClaudeClient()
    service = LLMService(
        client_factories={"claude": lambda *args, **kwargs: client},
        policy=RetryPolicy(max_attempts=1),
    )

    formulation = service.parse(
        "claude",
        "cheap",
        "test-key",
        "아세트아미노펜 500 mg 속방정을 크로스카멜로오스나트륨으로 제조",
    )

    assert formulation.apis[0].name == "Acetaminophen"
    assert formulation.apis[0].dose_mg == 500
    assert formulation.excipient_choices["disintegrant"] == ["croscarmellose sodium"]
    assert formulation.release_profile == "immediate release"
    assert client.messages.tool_choice == {
        "type": "tool",
        "name": "parse_formulation_request",
    }
