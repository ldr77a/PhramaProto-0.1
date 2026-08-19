"""Task B — API 용량(mg) 폴백 체인. 사용자 > KG 분포 > 표준사전 > 미상.

각 용량에 dose_source 를 기록(I5/I8 — LLM이 숫자 창작 금지, 근거를 남긴다).
KG 용량: HAS_API.mg(원문 문자열)를 unit_converter.mg_value 로 수치화해 중앙값.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path

from pharma_proto.knowledge import KnowledgeRepository

_STD_PATH = Path(__file__).resolve().parent / "standard_doses.json"


@dataclass
class DoseResult:
    name: str
    mg: float | None
    source: str            # user | kg | standard | unknown
    note: str
    n: int = 0


def _load_standard() -> dict:
    return json.loads(_STD_PATH.read_text(encoding="utf-8"))


def _kg_dose(
    repository: KnowledgeRepository,
    name: str,
) -> tuple[float | None, int]:
    vals = [float(value) for value in repository.api_doses(name) if value > 0]
    if not vals:
        return None, 0
    return round(statistics.median(vals), 2), len(vals)


def resolve_dose(
    api,
    *,
    repository: KnowledgeRepository | None = None,
    standard: dict | None = None,
) -> DoseResult:
    standard = _load_standard() if standard is None else standard
    if api.dose_mg:
        return DoseResult(api.name, float(api.dose_mg), "user", "사용자 지정")
    if repository is not None:
        mg, n = _kg_dose(repository, api.name)
        if mg is not None:
            return DoseResult(api.name, mg, "kg", f"KG 실사용 중앙값(n={n})", n=n)
    key = api.name.strip().lower()
    if key in standard:
        s = standard[key]
        return DoseResult(api.name, float(s["mg"]), "standard",
                          f"표준용량 사전({s.get('ref','')})")
    return DoseResult(api.name, None, "unknown", "용량 미상 — 지정 필요")
