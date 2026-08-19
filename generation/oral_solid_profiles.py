"""Deterministic role profiles for oral-solid formulation generation."""

from __future__ import annotations

from dataclasses import dataclass

from pharma_proto.knowledge.function_taxonomy import ROLE_ALIASES


class UnsupportedDosageForm(ValueError):
    """Raised when a request is outside the oral-solid product scope."""


@dataclass(frozen=True)
class OralSolidProfile:
    profile_id: str
    dosage_form_bases: tuple[str, ...]
    auto_roles: tuple[str, ...]
    required_functions: tuple[str, ...]


CURATED_DEFAULTS: dict[str, tuple[str, ...]] = {
    "diluent": ("microcrystalline cellulose", "lactose", "mannitol"),
    "binder": ("povidone", "hydroxypropyl cellulose", "hypromellose"),
    "disintegrant": ("croscarmellose sodium", "sodium starch glycolate", "crospovidone"),
    "lubricant": ("magnesium stearate", "sodium stearyl fumarate", "stearic acid"),
    "glidant": ("colloidal silicon dioxide", "talc", "calcium silicate"),
    "coating": ("hypromellose", "ethylcellulose", "polyvinyl alcohol"),
    "film_forming_agent": ("hypromellose", "ethylcellulose", "polyvinyl alcohol"),
    "plasticizer": ("triethyl citrate", "polyethylene glycol", "propylene glycol"),
    "opacifier": ("titanium dioxide",),
    "colorant": ("iron oxides", "titanium dioxide"),
    "sweetener": ("sucralose", "saccharin sodium", "aspartame"),
    "flavoring_agent": ("peppermint oil", "menthol"),
    "taste_masking_agent": ("cyclodextrin", "ethylcellulose"),
    "wetting_agent": ("sodium lauryl sulfate", "polysorbate 80", "poloxamer"),
    "solubilizer": ("polysorbate 80", "povidone", "cyclodextrin"),
    "dissolution_enhancer": ("sodium lauryl sulfate", "poloxamer", "povidone"),
    "adsorbent": ("colloidal silicon dioxide", "magnesium carbonate", "calcium silicate"),
    "anticaking_agent": ("colloidal silicon dioxide", "calcium silicate", "talc"),
    "stabilizer": ("citric acid", "sodium citrate", "povidone"),
    "antioxidant": ("ascorbic acid", "ascorbyl palmitate", "butylated hydroxytoluene"),
    "preservative": ("methylparaben", "propylparaben", "potassium sorbate"),
    "buffer": ("sodium citrate", "citric acid", "sodium phosphate"),
    "acidifying_agent": ("citric acid", "tartaric acid", "fumaric acid"),
    "alkalizing_agent": ("sodium bicarbonate", "sodium carbonate", "magnesium oxide"),
    "chelating_agent": ("edetate disodium", "citric acid"),
    "sustained_release_agent": ("hypromellose", "ethylcellulose", "carbomer"),
    "granulation_aid": ("povidone", "hydroxypropyl cellulose", "pregelatinized starch"),
    "moisture_control_agent": ("colloidal silicon dioxide", "calcium silicate"),
}


_TABLET_BASES = ("tablet", "granule", "pellet", "bead", "powder")
_CAPSULE_BASES = ("capsule", "pellet", "bead", "granule", "powder")

PROFILES: dict[str, OralSolidProfile] = {
    "immediate_release_tablet": OralSolidProfile(
        "immediate_release_tablet",
        _TABLET_BASES,
        ("diluent", "binder", "disintegrant", "lubricant", "glidant"),
        ("api", "diluent", "disintegrant", "lubricant"),
    ),
    "film_coated_tablet": OralSolidProfile(
        "film_coated_tablet",
        _TABLET_BASES,
        ("diluent", "binder", "disintegrant", "lubricant", "glidant", "coating", "plasticizer"),
        ("api", "diluent", "disintegrant", "lubricant", "coating"),
    ),
    "enteric_tablet": OralSolidProfile(
        "enteric_tablet",
        _TABLET_BASES,
        ("diluent", "binder", "disintegrant", "lubricant", "glidant", "coating", "film_forming_agent", "plasticizer"),
        ("api", "diluent", "disintegrant", "lubricant", "coating"),
    ),
    "modified_release_tablet": OralSolidProfile(
        "modified_release_tablet",
        _TABLET_BASES,
        ("diluent", "binder", "lubricant", "glidant", "sustained_release_agent"),
        ("api", "diluent", "binder", "lubricant", "sustained_release_agent"),
    ),
    "orally_disintegrating_tablet": OralSolidProfile(
        "orally_disintegrating_tablet",
        _TABLET_BASES,
        ("diluent", "binder", "disintegrant", "lubricant", "glidant", "sweetener", "taste_masking_agent"),
        ("api", "diluent", "disintegrant", "lubricant"),
    ),
    "chewable_tablet": OralSolidProfile(
        "chewable_tablet",
        _TABLET_BASES,
        ("diluent", "binder", "disintegrant", "lubricant", "glidant", "sweetener", "flavoring_agent"),
        ("api", "diluent", "lubricant", "sweetener"),
    ),
    "hard_capsule": OralSolidProfile(
        "hard_capsule",
        _CAPSULE_BASES,
        ("diluent", "disintegrant", "lubricant", "glidant"),
        ("api", "diluent", "disintegrant"),
    ),
    "oral_granule": OralSolidProfile(
        "oral_granule",
        ("granule", "pellet", "bead", "powder"),
        ("diluent", "binder", "glidant", "granulation_aid"),
        ("api", "diluent", "binder"),
    ),
    "oral_pellet": OralSolidProfile(
        "oral_pellet",
        ("pellet", "bead", "granule"),
        ("diluent", "binder", "glidant", "coating"),
        ("api", "diluent", "binder"),
    ),
    "oral_powder": OralSolidProfile(
        "oral_powder",
        ("powder", "granule"),
        ("diluent", "glidant", "anticaking_agent"),
        ("api", "diluent"),
    ),
}


_NON_ORAL_SOLID = (
    "injection", "injectable", "solution", "suspension", "syrup", "cream",
    "ointment", "gel", "suppository", "inhalation", "aerosol", "ophthalmic",
    "parenteral", "transdermal", "soft gelatin", "softgel",
)


def role_aliases(role: str) -> tuple[str, ...]:
    return ROLE_ALIASES.get(role, (role,))


_ROLE_INPUT_ALIASES = {
    "결합제": "binder",
    "붕해제": "disintegrant",
    "희석제": "diluent",
    "충전제": "diluent",
    "활택제": "lubricant",
    "활택보조제": "glidant",
    "유동화제": "glidant",
    "코팅제": "coating",
    "피막형성제": "film_forming_agent",
    "가소제": "plasticizer",
    "감미제": "sweetener",
    "향미제": "flavoring_agent",
    "맛차폐제": "taste_masking_agent",
    "습윤제": "wetting_agent",
    "가용화제": "solubilizer",
    "용출개선제": "dissolution_enhancer",
    "흡착제": "adsorbent",
    "안정화제": "stabilizer",
    "항산화제": "antioxidant",
    "보존제": "preservative",
    "완충제": "buffer",
    "산성화제": "acidifying_agent",
    "알칼리화제": "alkalizing_agent",
    "킬레이트제": "chelating_agent",
    "서방화제": "sustained_release_agent",
    "방출조절제": "sustained_release_agent",
    "과립화보조제": "granulation_aid",
}


def canonical_role(value: str) -> str:
    normalized = "_".join(value.strip().lower().replace("-", " ").split())
    if value.strip() in _ROLE_INPUT_ALIASES:
        return _ROLE_INPUT_ALIASES[value.strip()]
    if normalized in ROLE_ALIASES:
        return normalized
    for canonical, aliases in ROLE_ALIASES.items():
        if normalized in aliases:
            return canonical
    return normalized


def resolve_profile(
    dosage_form: str,
    process: str = "",
    release_profile: str = "",
) -> OralSolidProfile:
    text = " ".join((dosage_form, process, release_profile)).strip().lower()
    if any(token in text for token in _NON_ORAL_SOLID):
        raise UnsupportedDosageForm(f"경구 고형제 범위 밖의 제형입니다: {dosage_form}")
    if any(token in text for token in ("orally disintegrating", "oral disintegrating", "orodispersible", "odt", "구강붕해")):
        key = "orally_disintegrating_tablet"
    elif any(token in text for token in ("chewable", "츄어블", "저작")):
        key = "chewable_tablet"
    elif any(token in text for token in ("enteric", "delayed release", "장용")):
        key = "enteric_tablet"
    elif any(token in text for token in ("extended release", "sustained release", "controlled release", "modified release", "서방", "방출조절")):
        key = "modified_release_tablet"
    elif any(token in text for token in ("film coated", "film-coated", "coated tablet", "필름코팅", "코팅정")):
        key = "film_coated_tablet"
    elif any(token in text for token in ("hard capsule", "hard gelatin capsule", "capsule", "경질캡슐")):
        key = "hard_capsule"
    elif any(token in text for token in ("pellet", "bead", "펠렛", "비드")):
        key = "oral_pellet"
    elif any(token in text for token in ("granule", "과립")):
        key = "oral_granule"
    elif any(token in text for token in ("powder", "산제", "분말")):
        key = "oral_powder"
    else:
        key = "immediate_release_tablet"
    return PROFILES[key]


__all__ = [
    "CURATED_DEFAULTS",
    "OralSolidProfile",
    "PROFILES",
    "ROLE_ALIASES",
    "UnsupportedDosageForm",
    "canonical_role",
    "resolve_profile",
    "role_aliases",
]
