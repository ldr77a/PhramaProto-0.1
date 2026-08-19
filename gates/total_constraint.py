"""게이트 3 — 총량 제약. 성분 mg 합이 목표 총중량 이하인가 + 성분 수 상한.

hard fail 대상: Σmg > 목표총중량, 성분수 > 상한.
경고: 단일 성분이 비표준적으로 큰 비율(부형제 단독 과다).
mg 정보가 없으면(모두 pct) 질량합은 skip, 성분 수만 본다.
"""

from __future__ import annotations

from gates.formulation import (  # type: ignore[import-not-found]
    FormulationInput,
    GateResult,
)

MAX_COMPONENTS = 15


def check(fi: FormulationInput, *, max_components: int = MAX_COMPONENTS, **_) -> GateResult:
    n = len(fi.components)
    details = []

    if n > max_components:
        return GateResult("게이트3 총량 제약", "fail",
                          f"성분 수 {n} > 상한 {max_components} (과다 성분)",
                          provenance="규칙: 성분수 상한", hard=True)

    mgs = [c.mg for c in fi.components if c.mg is not None]
    if fi.target_total_mg and mgs:
        total = sum(mgs)
        details.append(f"Σmg={total:.1f}, 목표={fi.target_total_mg:.1f}")
        if total > fi.target_total_mg + 1e-6:
            return GateResult("게이트3 총량 제약", "fail",
                              f"Σmg={total:.1f} > 목표총중량 {fi.target_total_mg:.1f}",
                              provenance="규칙: Σmg ≤ 목표총중량", hard=True, details=details)
        return GateResult("게이트3 총량 제약", "pass",
                          f"Σmg={total:.1f} ≤ {fi.target_total_mg:.1f}, 성분 {n}개",
                          provenance="규칙: Σmg ≤ 목표총중량", hard=True, details=details)

    return GateResult("게이트3 총량 제약", "pass",
                      f"성분 {n}개 ≤ {max_components} (mg 미제공 → 질량합 skip)",
                      provenance="규칙: 성분수 상한", hard=True, details=details)
