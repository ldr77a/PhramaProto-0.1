"""Structured external-LLM parsing with memory-only credentials."""

from pharma_proto.llm.catalog import MODEL_CATALOG, Provider, Tier, model_for
from pharma_proto.llm.memory_keys import MemoryKeyStore
from pharma_proto.llm.schema import ParsedRequest
from pharma_proto.llm.service import LLMService

__all__ = [
    "LLMService",
    "MODEL_CATALOG",
    "MemoryKeyStore",
    "ParsedRequest",
    "Provider",
    "Tier",
    "model_for",
]
