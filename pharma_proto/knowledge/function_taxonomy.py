"""Deterministic classification for every Function connected in the KG."""

from __future__ import annotations

import re

from pharma_proto.knowledge.evidence import FunctionDescriptor


ROLE_ALIASES: dict[str, tuple[str, ...]] = {
    "diluent": (
        "diluent", "tablet_diluent", "filler_in_tablets", "tablet_excipient",
        "directly_compressible_tablet_excipient",
    ),
    "binder": ("binder", "tablet_granulation", "granulation_aid"),
    "disintegrant": ("disintegrant",),
    "lubricant": ("lubricant", "tablet_lubricant"),
    "glidant": ("glidant", "anticaking_agent"),
    "coating": ("coating", "tablet_coating", "aqueous_film_coating"),
    "film_forming_agent": ("film_forming_agent", "aqueous_film_coating"),
    "plasticizer": ("plasticizer", "plasticizer_for_gelatin_and_cellulose"),
    "opacifier": ("opacifier", "pigment"),
    "colorant": ("colorant", "color_adjuvant", "pigment"),
    "sweetener": ("sweetener", "sweetener_in_chewable_tablets"),
    "flavoring_agent": ("flavoring_agent", "flavor_enhancer"),
    "taste_masking_agent": ("taste_masking_agent", "tastemasking_agent"),
    "wetting_agent": ("wetting_agent", "anionic_surfactant", "nonionic_surfactant"),
    "solubilizer": ("solubilizer", "dissolution_enhancer", "complexing_agent"),
    "dissolution_enhancer": ("dissolution_enhancer", "wetting_agent", "solubilizer"),
    "adsorbent": ("adsorbent", "absorbent_of_liquid_in_tableting"),
    "anticaking_agent": ("anticaking_agent", "glidant"),
    "stabilizer": ("stabilizer", "thermal_stabilizer"),
    "antioxidant": ("antioxidant",),
    "preservative": ("preservative",),
    "buffer": ("buffer", "buffer_in_tablets"),
    "acidifying_agent": ("acidifying_agent", "acidulant"),
    "alkalizing_agent": ("alkalizing_agent", "organic_base"),
    "chelating_agent": ("chelating_agent", "sequestering_agent"),
    "sustained_release_agent": (
        "sustained_release_agent", "extended_release_agent",
        "controlled_release_agent", "modified_release_agent",
        "release_modifying_agent", "matrixforming_agent",
        "extended_release_matrix_former", "sustained_release_tablet_matrix",
    ),
    "granulation_aid": ("granulation_aid", "tablet_granulation"),
    "moisture_control_agent": (
        "moisture_control_agent_in_tablets", "water_absorbing_agent",
        "water_activity_reducing_agent",
    ),
}

AUTO_ORAL_SOLID_ROLES = frozenset({
    "anticaking_agent", "binder", "coating", "diluent", "disintegrant",
    "film_forming_agent", "flavoring_agent", "glidant", "granulation_aid",
    "lubricant", "plasticizer", "sustained_release_agent", "sweetener",
    "taste_masking_agent",
})

_OTHER_DOSAGE_KEYWORDS = (
    "aerosol", "cosolvent", "cream", "dry_powder_inhaler", "emollient",
    "emulsifier", "gel_base", "gelling_agent", "inhal", "lyophil",
    "ointment", "oleaginous", "ophthalm", "parenteral", "skin_penetr",
    "solution", "suppository", "suspending", "tonicity", "transdermal",
    "water_miscible_cosolvent",
)
_NON_FORMULATION = frozenset({
    "antacid", "antiseptic", "detergent", "dietary_supplement",
    "disinfectant", "fecal_softener", "therapeutic_agent",
})
_DESCRIPTION_MARKERS = (
    "applications_in_pharmaceutical_formulations", "are_widely_used",
    "is_used_in_pharmaceutical_products", "is_also_claimed",
)


def normalize_function_name(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace("/", "_")
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9_]+", "_", normalized)).strip("_")


def _canonical_role(normalized: str) -> str | None:
    if normalized in ROLE_ALIASES:
        return normalized
    for canonical, aliases in ROLE_ALIASES.items():
        if normalized in aliases:
            return canonical
    return None


def classify_function(name: str) -> FunctionDescriptor:
    normalized = normalize_function_name(name)
    if (
        not normalized
        or len(normalized) > 120
        or any(marker in normalized for marker in _DESCRIPTION_MARKERS)
    ):
        return FunctionDescriptor(name, None, "invalid_or_review", "review_required")

    canonical = _canonical_role(normalized)
    if canonical is not None:
        status = "auto" if canonical in AUTO_ORAL_SOLID_ROLES else "explicit_only"
        return FunctionDescriptor(name, canonical, "oral_solid", status)

    if normalized in _NON_FORMULATION:
        return FunctionDescriptor(name, None, "non_formulation", "excluded_scope")
    if any(keyword in normalized for keyword in _OTHER_DOSAGE_KEYWORDS):
        return FunctionDescriptor(name, None, "other_dosage_form", "excluded_scope")
    return FunctionDescriptor(name, None, "invalid_or_review", "review_required")


__all__ = [
    "AUTO_ORAL_SOLID_ROLES",
    "ROLE_ALIASES",
    "classify_function",
    "normalize_function_name",
]
