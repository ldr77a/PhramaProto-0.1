"""게이트 파이프라인 — 6개 게이트를 순서대로 실행하고 종합 판정.

실행 순서(비용·의존성): 4(총량제약) → 5(총량100%) → 6(기능) → 1(허용범위) → 3(제조성) → 2(호환성).
[싸고 빠른 것 먼저 → KG 집계 → 무거운 RDKit 마지막]

hard fail(차단) vs soft warning(조건부):
  hard: 총량초과(4), 총합≠100(5), 필수기능 누락(6), 명확한 범위이탈(1).
  soft: 제조성 근사(3), 호환성 caution(2).
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
from gates.formulation import (  # type: ignore[import-not-found]
    FormulationInput,
    GateResult,
)
from pharma_proto.knowledge import KnowledgeRepository


def _gate2_result(
    fi: FormulationInput,
    *,
    repository: KnowledgeRepository,
    offline: bool,
) -> GateResult:
    from gates.compatibility import CompatibilityGate  # type: ignore[import-not-found]
    gate = CompatibilityGate(repository=repository, offline=offline)
    api_names = [a.name for a in fi.apis()]
    excipient_names = [e.name for e in fi.excipients()]
    missing_apis = gate.unresolved_structures(api_names)
    missing_excipients = gate.unresolved_structures(excipient_names)
    verdicts = gate.eval_formulation(api_names, excipient_names)
    high_risk = [verdict for verdict in verdicts if verdict.risk == "high"]
    if high_risk:
        lead = high_risk[0]
        reaction = (
            lead.hits[0].reaction
            if lead.hits
            else f"HPE6:{lead.hpe_hits[0].target_name}"
        )
        return GateResult(
            "게이트2 호환성",
            "fail",
            f"고위험 호환성 {len(high_risk)}건(예: {lead.drug}+{lead.excipient} {reaction})",
            provenance="PharmDE 17규칙 + RDKit + HPE6 Section 12 + KG 교차검증",
            hard=True,
            details=[verdict.combined for verdict in high_risk],
        )
    if missing_apis:
        return GateResult(
            "게이트2 호환성",
            "fail",
            f"API 구조정보 없음 — 화학 호환성 판정 불가: {', '.join(missing_apis)}",
            provenance="RDKit 구조 확인 + PharmDE 17규칙",
            hard=True,
            details=[f"unresolved API: {name}" for name in missing_apis],
        )
    if not verdicts:
        if missing_excipients:
            return GateResult(
                "게이트2 호환성",
                "warning",
                f"부형제 구조정보 부족 {len(missing_excipients)}건 — 부분 판정만 수행",
                provenance="RDKit 구조 확인 + PharmDE 17규칙 + HPE6 Section 12",
                hard=False,
                details=[f"unresolved excipient: {name}" for name in missing_excipients],
            )
        return GateResult("게이트2 호환성", "pass", "위험 반응 조합 없음",
                          provenance="PharmDE 17규칙 + RDKit", hard=False)
    lead = verdicts[0]
    rxn = (
        lead.hits[0].reaction
        if lead.hits
        else f"HPE6:{lead.hpe_hits[0].target_name}"
    )
    reason = (f"{len(verdicts)}개 위험 조합(예: {lead.drug}+{lead.excipient} {rxn}, "
              f"KG실사용 {lead.kg_used_in}건)")
    details = [
        f"{v.drug}+{v.excipient}: rules={[h.reaction for h in v.hits]}, "
        f"hpe6={[h.target_name for h in v.hpe_hits]} ({v.risk})"
        for v in verdicts
    ]
    details.extend(f"unresolved excipient: {name}" for name in missing_excipients)
    if missing_excipients:
        reason += f"; 구조정보 부족 부형제 {len(missing_excipients)}건"
    return GateResult("게이트2 호환성", "warning", reason,
                      provenance="PharmDE 17규칙 + RDKit + HPE6 Section 12 + KG 교차검증", hard=False,
                      details=details)


def run_pipeline(
    fi: FormulationInput,
    *,
    repository: KnowledgeRepository,
    offline: bool = False,
) -> dict:
    """6게이트 실행 → {results: [GateResult], verdict, warnings, hard_fails}."""
    results: list[GateResult] = []
    results.append(total_constraint.check(fi))                         # 4
    results.append(total_sum.check(fi))                                # 5
    results.append(function_coverage.check(fi, repository=repository)) # 6
    results.append(allowable_range.check(fi, repository=repository))   # 1
    results.append(manufacturability.check(fi, repository=repository)) # 3
    results.append(                                                   # 2
        _gate2_result(fi, repository=repository, offline=offline)
    )

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
