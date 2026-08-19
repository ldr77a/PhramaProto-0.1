"""성분 canonical_base 정규화 (게이트1 데이터 품질) — 규칙 3분류. 삭제 금지, 속성만(I5/I7).

문제: hypromellose 한 물질이 점도·상표명·등급 표기로 222개 노드로 쪼개져 게이트1(허용범위)
집계가 무의미. 표기 변이는 base 하나로 묶되, 화학적으로 다른 것(phthalate=HPMCP,
acetate succinate=HPMCAS)·치환코드(2208 vs 2910, 용도 다름 I7)는 분리 유지한다.

각 Ingredient 에 속성 추가(canonical_name 은 그대로 보존):
  canonical_base   : 집계 기준 이름(예 "hypromellose"). 게이트1은 이걸로 집계.
  norm_method      : rule_suffix_strip | kept_separate | noise | review_queue | unmapped
  norm_confidence  : high | review
  grade            : 치환코드 등급(있을 때, 예 "2208")

분류(위에서부터 먼저 매칭 우선):
  C 노이즈    : 문장형("composition")·캡슐규격 → non_ingredient + method='noise'
  (mixture)  : 서로 다른 base 2개+ → method='review_queue'(자동분해 금지 I7)
  B 분리유지  : phthalate/acetate succinate(다른 물질) 또는 치환코드 → base 분리
  A 통합     : base 키워드 1개 + 표기변이 → 접미사 제거로 base 추출(method='rule_suffix_strip')
  unmapped   : 알려진 base 없음(롱테일, 이번 범위 밖 — 임베딩 통합은 다음 단계)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# base(통합기준명) → 이 물질을 가리키는 트리거(동의어·브랜드 포함, 소문자 부분문자열).
BASE_TRIGGERS: dict[str, tuple[str, ...]] = {
    "hypromellose": ("hypromellose", "hpmc", "hydroxypropylmethyl",
                     "hydroxypropyl methylcellulose", "hydroxypropyl methyl cellulose",
                     "hydroxy propyl methylcellulose", "hydroxy propyl methyl cellulose",
                     "methocel", "benecel", "pharmacoat", "metholose"),
    "hydroxypropyl cellulose": ("hydroxypropyl cellulose", "hydroxy propyl cellulose",
                                "hydroxypropylcellulose", "klucel"),
    "hydroxyethyl cellulose": ("hydroxyethyl cellulose", "hydroxy ethyl cellulose", "natrosol"),
    "ethyl cellulose": ("ethyl cellulose", "ethylcellulose", "ethocel", "aquacoat", "surelease"),
    "microcrystalline cellulose": ("microcrystalline cellulose", "microcrystalline", "avicel",
                                   "emcocel", "vivapur", "ceolus"),
    "croscarmellose sodium": ("croscarmellose", "ac-di-sol", "primellose"),
    "carboxymethylcellulose sodium": ("carboxymethylcellulose", "carboxymethyl cellulose",
                                      "sodium carboxymethyl", "carmellose"),
    "crospovidone": ("crospovidone", "cross-linked povidone", "crosslinked povidone",
                     "polyplasdone", "kollidon cl"),
    "copovidone": ("copovidone", "copolyvidone", "kollidon va"),
    "povidone": ("povidone", "polyvinylpyrrolidone", "plasdone", "kollidon"),
    "magnesium stearate": ("magnesium stearate", "hyqual"),
    "calcium stearate": ("calcium stearate",),
    "stearic acid": ("stearic acid",),
    "lactose": ("lactose",),
    "mannitol": ("mannitol", "pearlitol"),
    "sorbitol": ("sorbitol", "neosorb"),
    "sodium starch glycolate": ("sodium starch glycolate", "explotab", "primojel"),
    "starch": ("starch", "amylum"),
    "titanium dioxide": ("titanium dioxide",),
    "talc": ("talc",),
    "colloidal silicon dioxide": ("colloidal silicon dioxide", "colloidal silica",
                                  "fumed silica", "silicon dioxide", "aerosil", "cab-o-sil",
                                  "syloid"),
    "polyethylene glycol": ("polyethylene glycol", "macrogol", "carbowax"),
    "sucrose": ("sucrose", "sugar sphere"),
}

# 더 구체적인 base 가 잡히면 일반 base 는 버린다(부분문자열 충돌 해소).
_OVERRIDES: dict[str, tuple[str, ...]] = {
    "crospovidone": ("povidone",),
    "copovidone": ("povidone",),
    "sodium starch glycolate": ("starch",),
    "croscarmellose sodium": ("carboxymethylcellulose sodium",),
    "hydroxypropyl cellulose": ("cellulose",),  # 방어(현재 'cellulose' 단독 base 없음)
}

# 화학적으로 다른 물질로 갈라지는 수식어(현재 셀룰로스에테르 대상). 있으면 분리 유지.
_FORK_MODIFIERS = ("acetate succinate", "acetate phthalate", "phthalate")
# USP 치환 유형 코드(용도 다름, I7 분리). 문자+숫자 상표등급(e5,k100m)과 구분되는 4자리.
_SUBSTITUTION_CODES = ("2208", "2910", "2906", "2900", "2907", "1828")


@dataclass(frozen=True)
class BaseVerdict:
    canonical_base: str
    norm_method: str          # rule_suffix_strip|kept_separate|noise|review_queue|unmapped
    norm_confidence: str      # high|review
    grade: str | None = None
    detected_bases: tuple[str, ...] = ()


def _is_noise(nl: str) -> bool:
    if "composition" in nl:               # "seal coat composition: ..." 문장형
        return True
    if "capsule" in nl and any(w in nl for w in ("shell", "empty", "hard capsule",
                                                 "capsule no", "hard gelatin")):
        return True
    return False


# 트리거는 '단어 시작 경계(왼쪽만)'로 매칭한다. 이유:
#  - 오른쪽 경계까지 걸면 "methoceltm"(™ 글자로 붙은 것)이 \bmethocel\b 에 안 걸린다.
#  - 왼쪽 경계만 걸면 "ethocel"(ethyl cellulose 트리거)이 "m|ethocel" 안에서 안 걸린다
#    (앞 글자 m 이 단어문자 → 경계 아님). → methocel 이 ethyl cellulose 로 오검출되지 않음.
_BASE_PATTERNS: dict[str, "re.Pattern[str]"] = {
    b: re.compile(r"\b(?:" + "|".join(re.escape(t) for t in trigs) + r")")
    for b, trigs in BASE_TRIGGERS.items()
}


def _detect_bases(nl: str) -> list[str]:
    hit = {b for b, pat in _BASE_PATTERNS.items() if pat.search(nl)}
    for specific, generals in _OVERRIDES.items():
        if specific in hit:
            hit.difference_update(generals)
    return sorted(hit)


def _normalize_surface(name: str) -> str:
    value = name.strip().lower()
    value = re.sub(r"[®™℠]", " ", value)
    value = value.replace("짰", " ")
    return " ".join(value.split())


def classify_aerosil_family(name: str) -> BaseVerdict | None:
    """Keep legacy AEROSIL aggregation from erasing material identity."""
    nl = _normalize_surface(name)
    if re.search(r"\baerosil\b", nl) is None:
        return None
    nl = re.sub(r"[-\u2010-\u2015\u2212]", " ", nl)
    nl = " ".join(nl.split())

    if re.fullmatch(r"aerosil r\s*972", nl):
        return BaseVerdict(
            "hydrophobic colloidal silica",
            "kept_separate",
            "high",
            grade="R972",
        )

    recognized_grades = {
        "aerosil 200": "200",
        "aerosil 200 pharma": "200 Pharma",
        "aerosil 200 vv": "200 VV",
    }
    grade = recognized_grades.get(nl)
    if grade is not None:
        return BaseVerdict(nl, "kept_separate", "high", grade=grade)

    # Bare brands, amounts, composites and contextual phrases are unsafe to
    # aggregate. Reviewers may resolve them through the HPE6 overlay instead.
    return BaseVerdict(
        nl,
        "review_queue",
        "review",
        detected_bases=("colloidal silicon dioxide",),
    )


def classify_base(name: str) -> BaseVerdict:
    """성분명 → canonical_base 판정(순수 함수). 위에서부터 우선."""
    nl = _normalize_surface(name)

    if _is_noise(nl):
        return BaseVerdict(name, "noise", "review")

    aerosil = classify_aerosil_family(nl)
    if aerosil is not None:
        return aerosil

    bases = _detect_bases(nl)
    if len(bases) == 0:
        return BaseVerdict(name, "unmapped", "review")           # 롱테일 — 다음 단계
    if len(bases) >= 2:
        return BaseVerdict(name, "review_queue", "review", detected_bases=tuple(bases))

    base = bases[0]

    # B: 화학적으로 다른 물질(수식어) — 긴 것 먼저.
    for mod in _FORK_MODIFIERS:
        if mod in nl:
            return BaseVerdict(f"{base} {mod}", "kept_separate", "high")

    # B: 치환코드(hypromellose 등) — 용도 다름, base+grade 로 분리.
    for code in _SUBSTITUTION_CODES:
        if re.search(rf"\b{code}\b", nl):
            return BaseVerdict(f"{base} {code}", "kept_separate", "high", grade=code)

    # A: 표기 변이 → base 통합.
    return BaseVerdict(base, "rule_suffix_strip", "high")


# --- Neo4j 적용 (속성만, 멱등) -----------------------------------------------
def apply(client, *, dry_run: bool = False) -> dict:
    with client.read_session() as s:
        rows = s.run(
            "MATCH (i:Ingredient) OPTIONAL MATCH (i)<-[r:CONTAINS|HAS_API]-() "
            "RETURN i.canonical_name AS n, count(r) AS deg, "
            "       coalesce(i.non_ingredient,false) AS ni"
        ).data()

    updates, review = [], []
    for r in rows:
        # 이전 정제서 이미 non_ingredient 인 건 그대로(중복 노이즈 판정 안 함).
        if r["ni"]:
            v = BaseVerdict(r["n"], "noise", "review")
        else:
            v = classify_base(r["n"])
        updates.append({"name": r["n"], "deg": r["deg"], "base": v.canonical_base,
                        "method": v.norm_method, "conf": v.norm_confidence, "grade": v.grade})
        if v.norm_method in ("review_queue", "unmapped"):
            review.append({"name": r["n"], "deg": r["deg"], "guess_base": v.canonical_base,
                           "reason": v.norm_method, "detected": list(v.detected_bases)})

    if not dry_run:
        with client.write_session() as s:
            s.run(
                "UNWIND $rows AS row MATCH (i:Ingredient {canonical_name: row.name}) "
                "SET i.canonical_base = row.base, i.norm_method = row.method, "
                "    i.norm_confidence = row.conf, i.grade = row.grade, "
                "    i.non_ingredient = CASE WHEN row.method='noise' THEN true "
                "                            ELSE coalesce(i.non_ingredient,false) END",
                rows=updates,
            )

    from collections import Counter
    methods = Counter(u["method"] for u in updates)
    # 통합 효과: base 별 노드 수(1보다 크면 통합됨).
    base_groups = Counter(u["base"] for u in updates
                          if u["method"] in ("rule_suffix_strip", "kept_separate"))
    return {
        "total": len(rows),
        "methods": dict(methods),
        "review_list": review,
        "top_consolidated": base_groups.most_common(15),
        "distinct_bases": len(base_groups),
        "dry_run": dry_run,
    }
