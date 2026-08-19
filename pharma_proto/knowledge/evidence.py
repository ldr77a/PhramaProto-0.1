"""Backend-neutral immutable evidence returned by knowledge repositories."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FunctionDescriptor:
    name: str
    canonical_role: str | None
    scope: str
    support_status: str


@dataclass(frozen=True)
class MonographEvidence:
    monograph_id: str
    source_id: str
    name: str
    pdf_start_page: int | None = None
    pdf_end_page: int | None = None


@dataclass(frozen=True)
class UseRangeEvidence:
    evidence_id: str
    function_name: str
    min_pct: float | None
    max_pct: float | None
    unit: str
    dosage_form: str | None = None
    application: str | None = None
    source_id: str = ""
    pdf_page: int | None = None
    review_status: str | None = None


@dataclass(frozen=True)
class PropertyEvidence:
    evidence_id: str
    property_name: str
    label: str | None
    value_text: str
    section: int | None = None
    source_id: str = ""
    pdf_page: int | None = None
    review_status: str | None = None


@dataclass(frozen=True)
class StabilityEvidence:
    evidence_id: str
    statement: str
    section: int | None = None
    source_id: str = ""
    pdf_page: int | None = None
    review_status: str | None = None


@dataclass(frozen=True)
class IncompatibilityEvidence:
    evidence_id: str
    target_name: str
    normalized_target_name: str
    target_kind: str | None = None
    section: int | None = None
    source_id: str = ""
    pdf_page: int | None = None
    review_status: str | None = None


@dataclass(frozen=True)
class IngredientEvidence:
    ingredient: str
    monographs: tuple[MonographEvidence, ...] = ()
    use_ranges: tuple[UseRangeEvidence, ...] = ()
    properties: tuple[PropertyEvidence, ...] = ()
    stability: tuple[StabilityEvidence, ...] = ()
    incompatibilities: tuple[IncompatibilityEvidence, ...] = ()

    @classmethod
    def empty(cls, ingredient: str) -> IngredientEvidence:
        return cls(ingredient=ingredient)


__all__ = [
    "FunctionDescriptor",
    "IncompatibilityEvidence",
    "IngredientEvidence",
    "MonographEvidence",
    "PropertyEvidence",
    "StabilityEvidence",
    "UseRangeEvidence",
]
