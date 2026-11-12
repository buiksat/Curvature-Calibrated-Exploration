from __future__ import annotations

from experiments.make_linear_bound_artifact import derive


def _stats(mean: float) -> dict[str, float]:
    return {"mean": mean}


def test_linear_bound_artifact_computes_horizon_normalizations_and_vacuity() -> None:
    aggregate = {
        "groups": [
            {
                "comparison": "fixed_reference",
                "method": "dense_full",
                "horizons": [
                    {
                        "horizon": 10,
                        "metrics": {
                            "cumulative_pseudo_regret": _stats(2.0),
                            "theorem_rhs": _stats(20.0),
                        },
                    }
                ],
            }
        ]
    }
    certification = {
        "event": "linear_policy_certification_audit",
        "policies": [
            {
                "comparison": "fixed_reference",
                "method": "dense_full",
                "certification_category": "ex_ante_theorem_certified",
            }
        ],
    }
    artifact = derive(aggregate, certification)
    row = artifact["rows"][0]
    assert row["R_T_over_T"] == 0.2
    assert row["theorem_rhs_over_T"] == 2.0
    assert row["theorem_rhs_over_R_T"] == 10.0
    assert row["certification_category"] == "ex_ante_theorem_certified"
    assert row["rhs_certification_status"] == (
        "conditional_theorem_bound_on_ex_ante_schedules"
    )
    assert artifact["reward_support"]["context_count"] == 256
    assert isinstance(row["rhs_exceeds_maximum_possible_pseudo_regret"], bool)


def test_posthoc_policy_rhs_is_not_labelled_as_a_certified_bound() -> None:
    aggregate = {
        "groups": [
            {
                "comparison": "fixed_reference",
                "method": "cg_full",
                "horizons": [
                    {
                        "horizon": 10,
                        "metrics": {
                            "cumulative_pseudo_regret": _stats(2.0),
                            "theorem_rhs": _stats(20.0),
                        },
                    }
                ],
            }
        ]
    }
    certification = {
        "event": "linear_policy_certification_audit",
        "policies": [
            {
                "comparison": "fixed_reference",
                "method": "cg_full",
                "certification_category": "posthoc_theorem_event_verified",
            }
        ],
    }
    row = derive(aggregate, certification)["rows"][0]
    assert row["rhs_certification_status"] == "posthoc_decomposition_rhs"
