"""게이트 5 — 필수 기능 구성. 정제에 필수 기능 성분이 다 있는가.

필수 기능: API + ديluent(희석제) + disintegrant(붕해제) + lubricant(활택제).
결합제(binder)는 제법 따라 선택 → 필수에서 제외(경고로만).
성분 기능은 KG HAS_FUNCTION(canonical_base) 우선, 없으면 function_seed 이름사전.
매핑 안 된 성분은 "기능 미상"으로 표시(커버리지 낮으면 한계 명시).
"""

from __future__ import annotations

from gates.formulation import (  # type: ignore[import-not-found]
    FormulationInput,
    GateResult,
)
from gates.kg_util import (  # type: ignore[import-not-found]
    function_for_component,
    load_function_seed,
)
from pharma_proto.knowledge import KnowledgeRepository

REQUIRED = ("api", "diluent", "disintegrant", "lubricant")


def check(
    fi: FormulationInput,
    *,
    repository: KnowledgeRepository | None = None,
    **_,
) -> GateResult:
    seed = load_function_seed()
    covered: dict[str, list[str]] = {}
    unmapped: list[str] = []
    for c in fi.components:
        fn = function_for_component(repository, c, seed)
        if fn:
            covered.setdefault(fn, []).append(c.name)
        else:
            unmapped.append(c.name)

    required = fi.required_functions or REQUIRED
    missing = [f for f in required if f not in covered]
    prov = f"KG HAS_FUNCTION + function_seed. 매핑성분 {len(fi.components)-len(unmapped)}/{len(fi.components)}"
    details = [f"{f}:{covered.get(f, [])}" for f in required]

    if missing:
        note = " (기능 미상 성분 있음 — 매핑 확대 필요)" if unmapped else ""
        return GateResult("게이트5 필수 기능 구성", "fail",
                          f"필수 기능 누락: {', '.join(missing)}{note}",
                          provenance=prov, hard=True, details=details)
    status = "warning" if unmapped else "pass"
    reason = f"필수 기능 구비: {', '.join(required)}"
    if unmapped:
        reason += f" (단 기능미상 {len(unmapped)}개: {unmapped[:3]})"
    return GateResult("게이트5 필수 기능 구성", status, reason,
                      provenance=prov, hard=True, details=details)
