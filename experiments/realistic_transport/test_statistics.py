from __future__ import annotations

import math

import pytest
from experiments.realistic_transport.statistics import (
    clopper_pearson_interval,
    clopper_pearson_upper_bound,
    DEFAULT_BOOTSTRAP_RESAMPLES,
    describe,
    four_corner_rank_tolerance_contrasts,
    paired_seed_bootstrap,
    StatisticsError,
    zero_denominator_ratio_summary,
)


def test_describe_reports_preregistered_statistics() -> None:
    summary = describe([1.0, 2.0, 3.0, 4.0])

    assert summary["n"] == 4
    assert summary["mean"] == 2.5
    assert summary["standard_deviation"] == pytest.approx(math.sqrt(5.0 / 3.0))
    assert summary["standard_error"] == pytest.approx(math.sqrt(5.0 / 12.0))
    assert summary["median"] == 2.5
    assert summary["q10"] == pytest.approx(1.3)
    assert summary["q25"] == pytest.approx(1.75)
    assert summary["q75"] == pytest.approx(3.25)
    assert summary["q90"] == pytest.approx(3.7)
    assert summary["iqr"] == 1.5
    assert summary["minimum"] == 1.0
    assert summary["maximum"] == 4.0


@pytest.mark.parametrize("values", [[], [1.0, math.nan], [1.0, math.inf]])
def test_describe_rejects_empty_or_nonfinite_values(values: list[float]) -> None:
    with pytest.raises(StatisticsError):
        describe(values)


def test_exact_clopper_pearson_boundaries() -> None:
    interval = clopper_pearson_interval(0, 10)
    upper = clopper_pearson_upper_bound(0, 10)

    assert interval["ci_low"] == 0.0
    assert interval["ci_high"] == pytest.approx(1.0 - 0.025 ** (1.0 / 10.0))
    assert upper["upper_bound"] == pytest.approx(1.0 - 0.05 ** (1.0 / 10.0))
    assert clopper_pearson_interval(10, 10)["ci_high"] == 1.0
    assert clopper_pearson_upper_bound(10, 10)["upper_bound"] == 1.0


@pytest.mark.parametrize(
    ("successes", "total", "level"),
    [(-1, 10, 0.95), (11, 10, 0.95), (1, 0, 0.95), (1, 10, 1.0)],
)
def test_clopper_pearson_rejects_invalid_inputs(
    successes: int, total: int, level: float
) -> None:
    with pytest.raises(StatisticsError):
        clopper_pearson_interval(successes, total, level=level)
    with pytest.raises(StatisticsError):
        clopper_pearson_upper_bound(successes, total, level=level)


def test_paired_bootstrap_is_deterministic_and_preserves_pairing() -> None:
    first = [(102, 4.0), (100, 2.0), (101, 3.0)]
    second = [(101, 1.0), (102, 2.0), (100, 0.0)]

    first_result = paired_seed_bootstrap(
        first, second, bootstrap_seed=271828, resamples=250
    )
    second_result = paired_seed_bootstrap(
        first, second, bootstrap_seed=271828, resamples=250
    )

    assert first_result == second_result
    assert first_result["seed_keys"] == [100, 101, 102]
    assert first_result["difference_definition"] == "first_minus_second"
    difference = first_result["paired_difference"]
    assert difference["mean"] == 2.0
    assert difference["bootstrap_mean_interval"]["ci"] == [2.0, 2.0]
    assert DEFAULT_BOOTSTRAP_RESAMPLES == 10_000


def test_paired_bootstrap_rejects_duplicate_and_misaligned_seeds() -> None:
    with pytest.raises(StatisticsError, match="duplicate seed 1"):
        paired_seed_bootstrap(
            [(1, 1.0), (1, 2.0)],
            [(1, 1.0)],
            bootstrap_seed=1,
            resamples=10,
        )
    with pytest.raises(StatisticsError, match="misaligned"):
        paired_seed_bootstrap(
            [(1, 1.0), (2, 2.0)],
            [(1, 1.0), (3, 3.0)],
            bootstrap_seed=1,
            resamples=10,
        )


def test_paired_bootstrap_rejects_nonfinite_values() -> None:
    with pytest.raises(StatisticsError, match="finite"):
        paired_seed_bootstrap(
            [(1, math.nan)], [(1, 0.0)], bootstrap_seed=1, resamples=10
        )


def test_zero_denominator_ratio_summary_omits_without_replacement() -> None:
    summary = zero_denominator_ratio_summary(
        [0.0, 2.0, 6.0, 4.0],
        [0.0, 1.0, 3.0, 1e-13],
        zero_tolerance=1e-12,
    )

    assert summary["n"] == 4
    assert summary["eligible_ratio_count"] == 2
    assert summary["zero_denominator_count"] == 2
    assert summary["zero_denominator_indices"] == [0, 3]
    assert summary["ratio"]["mean"] == 2.0
    assert summary["ratio"]["minimum"] == 2.0
    assert summary["ratio"]["maximum"] == 2.0


def test_zero_denominator_ratio_summary_handles_all_zeros() -> None:
    summary = zero_denominator_ratio_summary([1.0, 2.0], [0.0, -0.0])

    assert summary["eligible_ratio_count"] == 0
    assert summary["zero_denominator_count"] == 2
    assert summary["ratio"] is None


def test_zero_denominator_ratio_summary_rejects_invalid_inputs() -> None:
    with pytest.raises(StatisticsError, match="align"):
        zero_denominator_ratio_summary([1.0], [1.0, 2.0])
    with pytest.raises(StatisticsError, match="nonfinite"):
        zero_denominator_ratio_summary([math.inf], [1.0])
    with pytest.raises(StatisticsError, match="nonnegative"):
        zero_denominator_ratio_summary([1.0], [1.0], zero_tolerance=-1.0)


def _four_corner_rows() -> list[tuple[int, int, float, float]]:
    rows: list[tuple[int, int, float, float]] = []
    for seed, baseline in ((100, 1.0), (101, 2.0), (102, 4.0)):
        for rank, rank_indicator in ((16, 0.0), (64, 1.0)):
            for tolerance, tolerance_indicator in ((1e-2, 0.0), (1e-6, 1.0)):
                value = (
                    baseline
                    + 2.0 * rank_indicator
                    + 3.0 * tolerance_indicator
                    + 4.0 * rank_indicator * tolerance_indicator
                )
                rows.append((seed, rank, tolerance, value))
    return rows


def test_four_corner_contrasts_resample_complete_seed_clusters() -> None:
    first = four_corner_rank_tolerance_contrasts(
        reversed(_four_corner_rows()),
        low_rank=16,
        high_rank=64,
        loose_tolerance=1e-2,
        tight_tolerance=1e-6,
        bootstrap_seed=314159,
        resamples=200,
    )
    second = four_corner_rank_tolerance_contrasts(
        _four_corner_rows(),
        low_rank=16,
        high_rank=64,
        loose_tolerance=1e-2,
        tight_tolerance=1e-6,
        bootstrap_seed=314159,
        resamples=200,
    )

    assert first == second
    assert first["seed_keys"] == [100, 101, 102]
    for name, expected in (
        ("rank_high_minus_low", 4.0),
        ("tolerance_tight_minus_loose", 5.0),
        ("rank_tolerance_interaction", 4.0),
    ):
        contrast = first[name]
        assert contrast["mean"] == expected
        assert contrast["bootstrap_mean_interval"]["ci"] == [expected, expected]


def test_four_corner_contrasts_reject_duplicate_cells() -> None:
    rows = _four_corner_rows()
    rows.append(rows[0])
    with pytest.raises(StatisticsError, match="duplicate seed"):
        four_corner_rank_tolerance_contrasts(
            rows,
            low_rank=16,
            high_rank=64,
            loose_tolerance=1e-2,
            tight_tolerance=1e-6,
            bootstrap_seed=1,
            resamples=10,
        )


def test_four_corner_contrasts_reject_misaligned_seed_cells() -> None:
    rows = _four_corner_rows()
    rows.remove((102, 64, 1e-6, 13.0))
    with pytest.raises(StatisticsError, match="misaligned"):
        four_corner_rank_tolerance_contrasts(
            rows,
            low_rank=16,
            high_rank=64,
            loose_tolerance=1e-2,
            tight_tolerance=1e-6,
            bootstrap_seed=1,
            resamples=10,
        )


def test_four_corner_contrasts_reject_unexpected_or_nonfinite_cells() -> None:
    with pytest.raises(StatisticsError, match="unexpected"):
        four_corner_rank_tolerance_contrasts(
            [(100, 32, 1e-4, 1.0)],
            low_rank=16,
            high_rank=64,
            loose_tolerance=1e-2,
            tight_tolerance=1e-6,
            bootstrap_seed=1,
            resamples=10,
        )
    rows = _four_corner_rows()
    rows[0] = (*rows[0][:-1], math.nan)
    with pytest.raises(StatisticsError, match="finite"):
        four_corner_rank_tolerance_contrasts(
            rows,
            low_rank=16,
            high_rank=64,
            loose_tolerance=1e-2,
            tight_tolerance=1e-6,
            bootstrap_seed=1,
            resamples=10,
        )
