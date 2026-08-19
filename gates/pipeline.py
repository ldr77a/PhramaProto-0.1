"""게이트 파이프라인 — 5개 게이트를 순서대로 실행하고 종합 판정.

hard fail(차단) vs soft warning(조건부):
  hard: 명확한 범위이탈(1), 총량초과(3), 총합≠100(4), 필수기능 누락(5).
  soft: 제조성 근사(2).
종합: hard fail 있으면 "부적합", 없으면 "배합 가능(주의 N건)".
"""

from __future__ import annotations

from gates import (  # type: ignore[import-not-found]
    allowable_range,
    function_coverage,
    manufacturability,
    total_constraint,
    total_sum,
)
from gates.formulation import FormulationInput  # type: ignore[import-not-found]
from pharma_proto.knowledge import KnowledgeRepository


def run_pipeline(
    fi: FormulationInput,
    *,
    repository: KnowledgeRepository,
    offline: bool = False,
) -> dict:
    """5게이트 실행 → {results: [GateResult], verdict, warnings, hard_fails}."""
    results = [
        allowable_range.check(fi, repository=repository),
        manufacturability.check(fi, repository=repository),
        total_constraint.check(fi),
        total_sum.check(fi),
        function_coverage.check(fi, repository=repository),
    ]

    hard_fails = [r for r in results if r.hard and r.status == "fail"]
    warnings = [r for r in results if r.status == "warning"]
    verdict = "부적합" if hard_fails else "배합 가능"
    return {"results": results, "verdict": verdict,
            "hard_fails": hard_fails, "warnings": warnings}


def format_report(fi: FormulationInput, out: dict) -> str:
    lines = ["=== 배합 게이트 종합 ==="]
    apis = ", ".join(a.name for a in fi.apis())
    lines.append(f"배합: API[{apis}] + 부형제 {len(fi.excipients())}개, 제형={fi.dosage_form}")
    lines.append("")
    for r in out["results"]:
        lines.append(f"  {r.gate:16s}: {r.symbol}  {r.reason}")
    n_warn = len(out["warnings"])
    if out["hard_fails"]:
        lines.append(f"\n── 종합: ❌ 부적합 (hard fail {len(out['hard_fails'])}건) ──")
    else:
        lines.append(f"\n── 종합: ✅ {out['verdict']} (주의 {n_warn}건) ──")
    lines.append("provenance: 각 판정 근거는 게이트별 provenance 참조")
    return "\n".join(lines)
