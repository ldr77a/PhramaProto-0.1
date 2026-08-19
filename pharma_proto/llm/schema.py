"""One provider-neutral structured schema for formulation requests."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from generation.input_parser import FormulationSpec, build_spec
from generation.oral_solid_profiles import canonical_role

IngredientName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ParsedAPI(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: IngredientName
    dose_mg: float | None = Field(default=None, gt=0, le=1_000_000)


class ParsedRoleChoice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: IngredientName
    ingredients: list[IngredientName] = Field(default_factory=list, max_length=20)


class ParsedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    apis: list[ParsedAPI] = Field(min_length=1, max_length=10)
    dosage_form: IngredientName = "tablet"
    binder: list[IngredientName] = Field(default_factory=list, max_length=20)
    disintegrant: list[IngredientName] = Field(default_factory=list, max_length=20)
    diluent: list[IngredientName] = Field(default_factory=list, max_length=20)
    lubricant: list[IngredientName] = Field(default_factory=list, max_length=20)
    additional_roles: list[ParsedRoleChoice] = Field(default_factory=list, max_length=40)
    process: str = Field(default="", max_length=500)
    release_profile: str = Field(default="", max_length=200)
    n_candidates: int = Field(default=3, ge=1, le=5)
    target_total_mg: float | None = Field(default=None, gt=0, le=10_000_000)

    def to_domain(self) -> FormulationSpec:
        excipients: dict[str, list[str]] = {
            "binder": list(self.binder),
            "disintegrant": list(self.disintegrant),
            "diluent": list(self.diluent),
            "lubricant": list(self.lubricant),
        }
        for item in self.additional_roles:
            role = canonical_role(item.role)
            if role and item.ingredients:
                excipients.setdefault(role, []).extend(item.ingredients)
        return build_spec(
            [(item.name, item.dose_mg) for item in self.apis],
            {role: values for role, values in excipients.items() if values},
            dosage_form=self.dosage_form,
            process=self.process,
            release_profile=self.release_profile,
            n_candidates=self.n_candidates,
            target_total_mg=self.target_total_mg,
        )


__all__ = ["ParsedAPI", "ParsedRequest", "ParsedRoleChoice"]
