"""Provider adapters that send only a question and fixed structured schema."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any

from pharma_proto.llm.catalog import model_for
from pharma_proto.llm.resilience import RetryPolicy, run_with_retry
from pharma_proto.llm.schema import ParsedRequest

SYSTEM_INSTRUCTION = (
    "Extract the pharmaceutical formulation request into the supplied schema. "
    "Translate ingredient names to English generic names. Do not add fields outside the schema "
    "and do not invent excipients the user did not provide."
)

ClientFactory = Callable[..., Any]


def _openai_factory(api_key: str, *, timeout: float, max_retries: int):
    from openai import OpenAI

    return OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)


def _claude_factory(api_key: str, *, timeout: float, max_retries: int):
    from anthropic import Anthropic

    return Anthropic(api_key=api_key, timeout=timeout, max_retries=max_retries)


def _gemini_factory(api_key: str, *, timeout: float, max_retries: int):
    from google import genai
    from google.genai import types

    attempts = 1 if max_retries == 0 else max_retries + 1
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=int(timeout * 1000),
            retry_options=types.HttpRetryOptions(attempts=attempts),
        ),
    )


_DEFAULT_FACTORIES: dict[str, ClientFactory] = {
    "openai": _openai_factory,
    "gemini": _gemini_factory,
    "claude": _claude_factory,
}


def _coerce_parsed(value: object) -> ParsedRequest:
    if isinstance(value, ParsedRequest):
        return value
    return ParsedRequest.model_validate(value)


def _gemini_response_schema() -> dict[str, Any]:
    return {
        "type": "OBJECT",
        "properties": {
            "apis": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "name": {"type": "STRING"},
                        "dose_mg": {"type": "NUMBER"},
                    },
                    "required": ["name"],
                },
            },
            "dosage_form": {"type": "STRING"},
            "binder": {"type": "ARRAY", "items": {"type": "STRING"}},
            "disintegrant": {"type": "ARRAY", "items": {"type": "STRING"}},
            "diluent": {"type": "ARRAY", "items": {"type": "STRING"}},
            "lubricant": {"type": "ARRAY", "items": {"type": "STRING"}},
            "additional_roles": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "role": {"type": "STRING"},
                        "ingredients": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                        },
                    },
                    "required": ["role"],
                },
            },
            "process": {"type": "STRING"},
            "release_profile": {"type": "STRING"},
            "n_candidates": {"type": "INTEGER"},
            "target_total_mg": {"type": "NUMBER"},
        },
        "required": ["apis"],
    }


class LLMService:
    def __init__(
        self,
        *,
        client_factories: Mapping[str, ClientFactory] | None = None,
        policy: RetryPolicy | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._factories = dict(_DEFAULT_FACTORIES)
        if client_factories is not None:
            self._factories.update(client_factories)
        self._policy = policy or RetryPolicy()
        self._sleeper = sleeper

    def _parse_once(
        self,
        provider: str,
        model: str,
        api_key: str,
        question: str,
    ) -> ParsedRequest:
        client = self._factories[provider](
            api_key,
            timeout=self._policy.timeout_seconds,
            max_retries=0,
        )
        try:
            if provider == "openai":
                response = client.responses.parse(
                    model=model,
                    input=[
                        {"role": "system", "content": SYSTEM_INSTRUCTION},
                        {"role": "user", "content": question},
                    ],
                    text_format=ParsedRequest,
                )
                return _coerce_parsed(response.output_parsed)
            if provider == "claude":
                response = client.messages.parse(
                    model=model,
                    max_tokens=2048,
                    system=SYSTEM_INSTRUCTION,
                    messages=[{"role": "user", "content": question}],
                    output_format=ParsedRequest,
                )
                return _coerce_parsed(response.parsed_output)
            if provider == "gemini":
                from google.genai import types

                response = client.models.generate_content(
                    model=model,
                    contents=question,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        response_mime_type="application/json",
                        response_schema=_gemini_response_schema(),
                    ),
                )
                return ParsedRequest.model_validate_json(response.text)
            raise ValueError("unsupported provider")
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()

    def parse(
        self,
        provider: str,
        tier: str,
        api_key: str,
        question: str,
    ):
        model = model_for(provider, tier)
        key = api_key.strip()
        text = question.strip()
        if not key or not text or len(text) > 4000:
            raise ValueError("invalid LLM request")
        parsed = run_with_retry(
            lambda: self._parse_once(provider, model, key, text),
            policy=self._policy,
            sleeper=self._sleeper,
        )
        return parsed.to_domain()


__all__ = ["LLMService", "SYSTEM_INSTRUCTION"]
