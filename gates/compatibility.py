"""게이트2 엔진 — API-부형제 화학적 호환성 판정 (지시서 Task C).

C-1 규칙 기반(PharmDE): 각 (약물,부형제) 쌍에 17규칙을 적용. 약물측·부형제측 작용기가
    동시에 매칭되면 그 반응 위험 hit. SMARTS 불가 항목은 이름사전 보조.
C-2 KG 교차검증(차별점): 위험 쌍이 실제 승인/특허 배합에 쓰였는지 조회 → 위험 완화 표시.
C-3 종합 판정: 규칙 위험도 + KG 실증을 함께 출력, provenance 부착(I5 계승).

위험도(지시서 §C-1 + 유전독성 보정):
    0 rule = low, 1 rule = medium, 2+ rule = high. 단 유전독성 규칙(N-nitrosation)은
    단일 hit 라도 high(니트로사민은 미량도 발암 우려).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cleaning.canonical_base import classify_base
from gates.rule_data import ALL_RULES  # type: ignore[import-not-found]
from gates.smiles_resolver import SmilesResolver  # type: ignore[import-not-found]
from pharma_proto.knowledge import KnowledgeRepository


@dataclass
class RuleHit:
    reaction: str
    drug: str
    excipient: str
    mechanism: str
    source: str
    drug_by: str        # "smarts" | "name"
    exc_by: str         # "smarts" | "name"
    genotoxic: bool
    note: str = ""


@dataclass(frozen=True)
class HPEPairHit:
    source_ingredient: str
    target_name: str
    evidence_id: str
    pdf_page: int | None = None


@dataclass
class PairVerdict:
    drug: str
    excipient: str
    hits: list[RuleHit] = field(default_factory=list)
    hpe_hits: list[HPEPairHit] = field(default_factory=list)
    risk: str = "low"                 # low | medium | high
    kg_used_in: int = 0               # 실제 배합수(KG 교차검증)
    kg_sources: list[str] = field(default_factory=list)
    combined: str = ""                # 종합 코멘트


def _compile_smarts() -> dict[str, object]:
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    out: dict[str, object] = {}
    for r in ALL_RULES:
        for sm in (r.drug_smarts, r.exc_smarts):
            if sm and sm not in out:
                m = Chem.MolFromSmarts(sm)
                if m is None:
                    raise ValueError(f"SMARTS parse failed: {sm!r} (rule {r.name})")
                out[sm] = m
    return out


class CompatibilityGate:
    def __init__(
        self,
        *,
        resolver: SmilesResolver | None = None,
        repository: KnowledgeRepository | None = None,
        offline: bool = False,
    ) -> None:
        self._resolver = resolver or SmilesResolver(offline=offline)
        self._repository = repository
        self._patt = _compile_smarts()

    # --- 분자 로딩 ---------------------------------------------------------
    def _mol(self, name: str):
        from rdkit import Chem
        smiles = self._resolver.resolve(name)
        if not smiles:
            return None
        return Chem.MolFromSmiles(smiles)

    def _smarts_match(self, mol, smarts: str | None) -> bool:
        if mol is None or not smarts:
            return False
        return mol.HasSubstructMatch(self._patt[smarts])

    @staticmethod
    def _name_match(name: str, needles: tuple[str, ...]) -> bool:
        n = name.lower()
        return any(k in n for k in needles)

    @staticmethod
    def _normalized_ingredient(name: str) -> str:
        return classify_base(name).canonical_base.strip().casefold()

    def _hpe_direct_matches(self, drug: str, excipient: str) -> list[HPEPairHit]:
        if self._repository is None:
            return []
        lookup = getattr(self._repository, "ingredient_evidence", None)
        if not callable(lookup):
            return []
        pairs = (
            (drug, lookup(drug), self._normalized_ingredient(excipient)),
            (excipient, lookup(excipient), self._normalized_ingredient(drug)),
        )
        found: dict[tuple[str, str], HPEPairHit] = {}
        for source_name, evidence, counterpart in pairs:
            for item in evidence.incompatibilities:
                target = self._normalized_ingredient(item.normalized_target_name)
                if target != counterpart:
                    continue
                key = (item.evidence_id, target)
                found[key] = HPEPairHit(
                    source_ingredient=source_name,
                    target_name=item.target_name,
                    evidence_id=item.evidence_id,
                    pdf_page=item.pdf_page,
                )
        return [found[key] for key in sorted(found)]

    # --- 한 쌍 판정 --------------------------------------------------------
    def eval_pair(self, drug: str, excipient: str, drug_mol=None, exc_mol=None) -> PairVerdict:
        if drug_mol is None:
            drug_mol = self._mol(drug)
        if exc_mol is None:
            exc_mol = self._mol(excipient)
        v = PairVerdict(drug=drug, excipient=excipient)

        for r in ALL_RULES:
            # 약물측: SMARTS(현재 규칙은 약물측 이름사전 없음)
            drug_by = "smarts" if self._smarts_match(drug_mol, r.drug_smarts) else ""
            # 부형제측: SMARTS 또는 이름사전
            exc_by = ""
            if self._smarts_match(exc_mol, r.exc_smarts):
                exc_by = "smarts"
            elif r.exc_name_any and self._name_match(excipient, r.exc_name_any):
                exc_by = "name"
            if drug_by and exc_by:
                v.hits.append(RuleHit(
                    reaction=r.name, drug=drug, excipient=excipient,
                    mechanism=r.mechanism, source=r.source,
                    drug_by=drug_by, exc_by=exc_by, genotoxic=r.genotoxic, note=r.note))

        v.hpe_hits = self._hpe_direct_matches(drug, excipient)
        v.risk = self._risk(v.hits)
        if v.hpe_hits and v.risk == "low":
            v.risk = "medium"
        if self._repository is not None and (v.hits or v.hpe_hits):
            v.kg_used_in, v.kg_sources = self._kg_crosscheck(drug, excipient)
        v.combined = self._combine(v)
        return v

    def unresolved_structures(self, names: list[str]) -> list[str]:
        """Return unique names whose molecular structure cannot be resolved."""
        return [
            name
            for name in dict.fromkeys(names)
            if self._mol(name) is None
        ]

    @staticmethod
    def _risk(hits: list[RuleHit]) -> str:
        if not hits:
            return "low"
        if any(h.genotoxic for h in hits):
            return "high"
        return "high" if len({h.reaction for h in hits}) >= 2 else "medium"

    def _kg_crosscheck(self, drug: str, excipient: str) -> tuple[int, list[str]]:
        """규칙 위험 쌍이 실제 배합에 함께 쓰였나(어간 CONTAINS 매칭)."""
        if self._repository is None:
            return 0, []
        evidence = self._repository.compatibility_usage(drug, excipient)
        return evidence.count, list(evidence.source_types)

    @staticmethod
    def _combine(v: PairVerdict) -> str:
        if not v.hits and not v.hpe_hits:
            return "LOW RISK — 매칭 규칙 없음"
        tier = {"high": "HIGH", "medium": "CAUTION", "low": "LOW"}[v.risk]
        evidence = []
        if v.hits:
            evidence.append(f"화학규칙 {len(v.hits)}건")
        if v.hpe_hits:
            evidence.append(f"HPE6 직접 부적합 {len(v.hpe_hits)}건")
        prefix = f"{tier} — {', '.join(evidence)}"
        if v.kg_used_in > 0:
            return (f"{prefix}, 실제 배합 {v.kg_used_in}건에 존재"
                    f"({','.join(v.kg_sources)}) → 회피 가능(조건부 관리)")
        return f"{prefix}, KG 실사용 근거 없음(위험 유지)"

    # --- 배합 전체 판정 ----------------------------------------------------
    def eval_formulation(self, apis: list[str], excipients: list[str]) -> list[PairVerdict]:
        """모든 (api, excipient) 쌍 판정. 위험(hit) 있는 쌍만 반환(정렬: high>medium)."""
        # 분자 캐시(같은 성분 반복 로딩 방지)
        mols = {n: self._mol(n) for n in set(apis) | set(excipients)}
        out: list[PairVerdict] = []
        for a in apis:
            for e in excipients:
                v = self.eval_pair(a, e, drug_mol=mols.get(a), exc_mol=mols.get(e))
                if v.hits or v.hpe_hits:
                    out.append(v)
        order = {"high": 0, "medium": 1, "low": 2}
        out.sort(key=lambda v: (order[v.risk], -v.kg_used_in))
        return out
