"""게이트 4 — 조성 합계. 배합 %의 합이 100 ± 허용오차인가.

hard fail: Σpct 가 100 에서 벗어남.
미완성(fail 아님): pct=null(present만) 성분이 있으면 합산 불가 → "불완전 배합(%미제정 N개)".
공정용매(process_material)는 증발분이라 100% 합산서 제외.
"""

from __future__ import annotations

from gates.formulation import (  # type: ignore[import-not-found]
    FormulationInput,
    GateResult,
)

TOLERANCE = 0.5   # ±%p


def check(fi: FormulationInput, *, tolerance: float = TOLERANCE, **_) -> GateResult:
    counted = [c for c in fi.components if not c.process_material]
    nulls = [c for c in counted if c.pct is None]
    known = [c.pct for c in counted if c.pct is not None]

    if nulls:
        return GateResult("게이트4 조성 합계", "warning",
                          f"불완전 배합: {len(nulls)}개 성분 %미제정 → 합산 불가",
                          provenance="규칙: Σpct=100±오차 (미제정은 미완성)",
                          hard=False, details=[c.name for c in nulls])

    total = sum(known)
    if abs(total - 100.0) <= tolerance:
        return GateResult("게이트4 조성 합계", "pass",
                          f"Σpct={total:.2f}% (100±{tolerance})",
                          provenance="규칙: Σpct=100±오차", hard=True)
    gap = total - 100.0
    return GateResult("게이트4 조성 합계", "fail",
                      f"Σpct={total:.2f}% ({'초과' if gap>0 else '부족'} {abs(gap):.2f}%p)",
                      provenance="규칙: Σpct=100±오차", hard=True)
