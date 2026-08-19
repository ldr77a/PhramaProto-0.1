from __future__ import annotations

from gates.formulation import Component, FormulationInput
from gates.pipeline import run_pipeline
from pharma_proto.knowledge import NullKnowledgeRepository


def test_pipeline_runs_only_the_five_renumbered_gates() -> None:
    formulation = FormulationInput(
        components=[
            Component("Metformin", role="api", mg=500, pct=60, function="api"),
            Component("Povidone", mg=30, pct=3.6, function="binder"),
            Component(
                "Croscarmellose sodium",
                mg=25,
                pct=3,
                function="disintegrant",
            ),
            Component(
                "Magnesium stearate",
                mg=8,
                pct=1,
                function="lubricant",
            ),
            Component("Lactose", mg=270, pct=32.4, function="diluent"),
        ],
        target_total_mg=833,
    )

    output = run_pipeline(
        formulation,
        repository=NullKnowledgeRepository(),
        offline=True,
    )

    assert [result.gate for result in output["results"]] == [
        "게이트1 사용량 범위",
        "게이트2 제조성 대리지표",
        "게이트3 총량 제약",
        "게이트4 조성 합계",
        "게이트5 필수 기능 구성",
    ]
