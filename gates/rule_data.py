"""게이트2 규칙 데이터 — PharmDE 논문 Table 1의 17개 API-부형제 상호작용.

출처: Wang et al. 2021, Int. J. Pharm. 607:120962, Table 1.

각 규칙은 (약물 작용기, 부형제 작용기) 쌍이 한 배합에 공존하면 그 반응 위험을 hit 한다.
판정 두 갈래(지시서 §2 주의):
  1) SMARTS 매칭: 분자 부분구조로 잡는다(RDKit HasSubstructMatch).
  2) 이름 사전 보조: SMARTS로 표현이 어렵거나(환원당) 분자 자체가 아니라 미량 불순물이
     원인인 규칙(퍼옥사이드/나이트라이트 등)은 부형제 이름/카테고리 사전으로 판정한다.

초안 대비 수정(프리플라이트에서 확인, provenance.note 에 기록):
  - N-Nitrosation: 초안 SMARTS `[NX3;H2,H1]`(1·2차 아민)은 3차 아민 약물(chlorpromazine)을
    놓친다. 니트로사민은 2·3차 아민에서 생성되므로 `[NX3;!$(NC=O);!$([#7]~[#8])]`(비아마이드
    3가 질소, 이미 N-O 결합 제외)로 확장. → 논문 케이스③(chlorpromazine+PVP) 재현.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Rule:
    name: str
    drug_group: str          # 약물측 작용기 설명
    exc_group: str           # 부형제측 작용기 설명
    drug_smarts: str | None  # 약물 부분구조(없으면 이름사전/미사용)
    exc_smarts: str | None   # 부형제 부분구조(없으면 이름사전)
    mechanism: str
    source: str = "PharmDE Table 1 (Wang 2021, Int J Pharm 607:120962)"
    # 이름 사전 보조(부형제): 이 부분문자열 중 하나가 canonical_name 에 있으면 부형제측 hit.
    exc_name_any: tuple[str, ...] = ()
    genotoxic: bool = False  # True 면 단일 hit 라도 고위험(예: 니트로사민)
    note: str = ""           # 초안 대비 수정/한계 메모


# --- 이름 사전 (SMARTS 불가 항목) -------------------------------------------
# 환원당: 알데하이드/케톤 유리기가 있어 Maillard 를 일으킨다. 비환원당(sucrose)·당알코올
# (mannitol/sorbitol/xylitol)은 제외한다(위양성 방지). 부분문자열 매칭.
REDUCING_SUGARS: tuple[str, ...] = (
    "lactose", "glucose", "dextrose", "maltose", "maltodextrin",
    "fructose", "galactose", "isomaltose", "lactose monohydrate",
)
# 명시적 비환원(매칭에서 배제할 안전 당류) — 참고용/테스트용.
NON_REDUCING = ("sucrose", "mannitol", "sorbitol", "xylitol", "trehalose")

# 나이트라이트/나이트로소 유발 가능 불순물 보유 부형제(니트로사민 생성 원인).
NITRITE_IMPURITY_EXC: tuple[str, ...] = (
    "povidone", "pvp", "crospovidone", "copovidone", "polyvinylpyrrolidone",
)
# 퍼옥사이드 불순물 보유 가능 부형제(산화 유발).
PEROXIDE_IMPURITY_EXC: tuple[str, ...] = (
    "povidone", "crospovidone", "polyethylene glycol", "macrogol", "peg",
    "polysorbate", "hydroxypropyl cellulose", "poloxamer",
)
# 염기성 금속염/산화물·무기 알칼리 — 산-불안정 약물(에스터 등)의 염기촉매 가수분해 유발.
# ★무기물은 분자 SMARTS 로 반응성을 잡기 어렵다(체크리스트6 한계) → 카테고리 사전으로 처리.
BASIC_METAL_EXC: tuple[str, ...] = (
    "magnesium stearate", "calcium stearate", "magnesium oxide",
    "magnesium carbonate", "calcium carbonate", "sodium bicarbonate",
    "magnesium hydroxide", "sodium carbonate",
)
# 알데하이드/포름알데하이드 방출 불순물 보유 가능(전분 등). 환원당은 여기 넣지 않는다 —
# 이미 Maillard(환원당)로 잡히므로 중복 계산 시 위양성(N-메틸화 등 과잉 hit)이 난다.
ALDEHYDE_IMPURITY_EXC: tuple[str, ...] = (
    "starch", "pregelatinized starch",
)

# 1·2차 아민(비아마이드). 여러 규칙이 공유.
_PRIM_SEC_AMINE = "[NX3;H2,H1;!$(NC=O)]"
# 확장 아민(1·2·3차, 비아마이드, 이미 N-O 결합 제외) — 니트로사민용.
_ANY_AMINE = "[NX3;!$(NC=O);!$([#7]~[#8])]"


PHARMDE_RULES: list[Rule] = [
    Rule("Oxidation", "phenolic hydroxyl", "peroxide impurity",
         "[OX2H][cX3]:[c]", None,
         "페놀 하이드록실이 퍼옥사이드 불순물에 산화",
         exc_name_any=PEROXIDE_IMPURITY_EXC,
         note="퍼옥사이드는 부형제 미량 불순물 → 부형제는 이름사전 판정"),
    Rule("Hydrolysis", "amide", "carboxyl/organic acid impurity",
         "[NX3][CX3](=[OX1])", "[CX3](=O)[OX2H1]",
         "아마이드가 산성 조건서 가수분해"),
    Rule("Acid-base", "sulfonyl hydroxide", "amino",
         "[SX4](=O)(=O)[OX2H]", _PRIM_SEC_AMINE,
         "산-염기 반응"),
    Rule("Esterification", "hydroxyl group", "carboxyl/organic acid impurity",
         "[OX2H]", "[CX3](=O)[OX2H1]",
         "하이드록실 + 카복실 → 에스터"),
    Rule("Complexation", "cyanide", "metal ion impurity",
         "[CX2]#[NX1]", None,
         "시아나이드-금속이온 착물",
         exc_name_any=("talc", "magnesium", "calcium", "iron oxide", "titanium dioxide"),
         note="금속이온은 무기 부형제 이름사전 보조"),
    Rule("Maillard", "primary/secondary amine", "reducing sugar",
         _PRIM_SEC_AMINE, None,
         "아민 + 환원당 갈변(Maillard)",
         exc_name_any=REDUCING_SUGARS,
         note="환원당은 단일 SMARTS 곤란 → 이름사전(비환원당·당알코올 제외)"),
    Rule("Transesterification", "ester bond", "hydroxyl group",
         "[CX3](=O)[OX2][#6]", "[OX2H]",
         "에스터교환"),
    Rule("Amino-transesterification", "primary/secondary amine", "ester bond",
         _PRIM_SEC_AMINE, "[CX3](=O)[OX2][#6]",
         "아민-에스터교환"),
    Rule("Acylation", "primary/secondary amine", "aldehyde",
         _PRIM_SEC_AMINE, "[CX3H1](=O)",
         "아실화"),
    Rule("Aldol condensation", "carbonyl w/ alpha-H", "furfuraldehyde impurity",
         "[CX3](=O)[CX4H]", None,
         "알돌 축합",
         exc_name_any=REDUCING_SUGARS,
         note="furfural 계 불순물 — 환원당 유래, 이름사전 보조"),
    Rule("Amidation", "acyl halide", "primary/secondary amine",
         "[CX3](=O)[F,Cl,Br,I]", _PRIM_SEC_AMINE,
         "아마이드화"),
    Rule("Amine-aldehyde condensation", "aldehyde", "primary/secondary amine",
         "[CX3H1](=O)", _PRIM_SEC_AMINE,
         "아민-알데하이드 축합"),
    Rule("Hydroxymethylation", "C=C double bond", "aldehyde impurity",
         "[CX3]=[CX3]", None,
         "하이드록시메틸화",
         exc_name_any=ALDEHYDE_IMPURITY_EXC,
         note="알데하이드 불순물 — 전분/환원당 이름사전 보조"),
    Rule("Michael addition", "primary/secondary amine", "C=C double bond",
         _PRIM_SEC_AMINE, "[CX3]=[CX3]",
         "Michael 부가"),
    Rule("N-Methylation", "primary/secondary amine", "aldehyde impurity",
         _PRIM_SEC_AMINE, None,
         "N-메틸화(포름알데하이드 등 불순물)",
         exc_name_any=ALDEHYDE_IMPURITY_EXC,
         note="포름알데하이드계 불순물 — 이름사전 보조"),
    Rule("N-Nitrosation", "amine (incl. tertiary)", "nitrite/nitrate impurity",
         _ANY_AMINE, None,
         "N-니트로사민 생성(유전독성/발암 위험)",
         exc_name_any=NITRITE_IMPURITY_EXC, genotoxic=True,
         note="초안 SMARTS `[NX3;H2,H1]` → 3차 아민(chlorpromazine) 놓침. "
              "니트로사민은 2·3차 아민서 생성되므로 `[NX3;!$(NC=O);!$([#7]~[#8])]`로 확장."),
    Rule("Nucleophilic addition", "imine", "primary/secondary amine",
         "[CX3]=[NX2]", _PRIM_SEC_AMINE,
         "친핵성 부가"),
]

assert len(PHARMDE_RULES) == 17, f"expected 17 rules, got {len(PHARMDE_RULES)}"


# --- 보조 규칙 (PharmDE 17개 밖, 무기물/염 확장) ------------------------------
# 17개 SMARTS는 유기 작용기 쌍만 잡는다. 하지만 논문 실험 검증 사례 중에는 무기물/금속염이
# 원인인 것이 있다(예: aspirin + magnesium stearate → 염기촉매 에스터 가수분해, PharmDE Table3).
# 무기물은 분자 SMARTS로 반응성을 표현하기 어렵다(체크리스트6 한계) → 약물측은 SMARTS,
# 부형제측은 카테고리 이름사전으로 판정한다. 17개와 분리해 provenance를 분명히 한다.
SUPPLEMENTARY_RULES: list[Rule] = [
    Rule("Ester hydrolysis (base/metal-catalyzed)", "ester bond",
         "basic metal salt/oxide (inorganic)",
         "[CX3](=O)[OX2][#6]", None,
         "염기성 금속염·산화물이 에스터 결합의 가수분해를 촉매(예: aspirin + Mg stearate)",
         source="PharmDE Table 3 검증사례 + 무기물 확장(SMARTS 밖)",
         exc_name_any=BASIC_METAL_EXC,
         note="17개 SMARTS 밖 보조규칙. 무기 염기성 부형제는 이름/카테고리 사전 판정."),
]

# 엔진이 실제로 적용하는 전체 규칙(코어 17 + 보조).
ALL_RULES: list[Rule] = PHARMDE_RULES + SUPPLEMENTARY_RULES
