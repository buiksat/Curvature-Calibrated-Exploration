"""Deterministic statistical summaries for the realistic transport benchmark.

The seed is the inferential unit.  Functions that compare methods therefore
accept explicitly keyed values and reject duplicate or mismatched seed sets.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from numbers import Integral
from typing import Any, TypeAlias

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.stats import beta as beta_distribution


FloatArray = NDArray[np.float64]
SeededValues: TypeAlias = Mapping[int, float] | Iterable[tuple[int, float]]
CornerObservation: TypeAlias = tuple[int, int, float, float]

DEFAULT_BOOTSTRAP_RESAMPLES = 10_000
DEFAULT_CONFIDENCE_LEVEL = 0.95


class StatisticsError(ValueError):
    """Raised when statistical inputs violate the preregistered contract."""


def _finite_float(value: Any, *, name: str) -> float:
    if isinstance(value, (bool, np.bool_)):
        raise StatisticsError(f"{name} must be numeric, not boolean")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise StatisticsError(f"{name} must be a finite real number") from error
    if not math.isfinite(result):
        raise StatisticsError(f"{name} must be finite")
    return result


def _positive_integer(value: Any, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise StatisticsError(f"{name} must be an integer")
    result = int(value)
    if result <= 0:
        raise StatisticsError(f"{name} must be positive")
    return result


def _seed(value: Any, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise StatisticsError(f"{name} must be an integer")
    result = int(value)
    if result < 0:
        raise StatisticsError(f"{name} must be nonnegative")
    return result


def _level(value: Any) -> float:
    result = _finite_float(value, name="confidence level")
    if not 0.0 < result < 1.0:
        raise StatisticsError("confidence level must lie strictly between zero and one")
    return result


def _vector(values: ArrayLike | Iterable[float], *, name: str) -> FloatArray:
    if isinstance(values, np.ndarray):
        array = np.asarray(values, dtype=np.float64)
    else:
        try:
            array = np.asarray(tuple(values), dtype=np.float64)
        except (TypeError, ValueError, OverflowError) as error:
            raise StatisticsError(
                f"{name} must be a one-dimensional numeric sequence"
            ) from error
    if array.ndim != 1 or array.size == 0:
        raise StatisticsError(f"{name} must be a nonempty one-dimensional sequence")
    if not np.all(np.isfinite(array)):
        raise StatisticsError(f"{name} contains a nonfinite value")
    return np.ascontiguousarray(array, dtype=np.float64)


def _seeded_values(values: SeededValues, *, name: str) -> dict[int, float]:
    rows = values.items() if isinstance(values, Mapping) else values
    result: dict[int, float] = {}
    try:
        iterator = iter(rows)
    except TypeError as error:
        raise StatisticsError(f"{name} must contain (seed, value) pairs") from error
    for index, row in enumerate(iterator):
        try:
            raw_seed, raw_value = row
        except (TypeError, ValueError) as error:
            raise StatisticsError(
                f"{name} row {index} must contain exactly (seed, value)"
            ) from error
        seed = _seed(raw_seed, name=f"{name} seed")
        if seed in result:
            raise StatisticsError(f"{name} contains duplicate seed {seed}")
        result[seed] = _finite_float(raw_value, name=f"{name}[{seed}]")
    if not result:
        raise StatisticsError(f"{name} must contain at least one seed")
    return result


def _aligned_seed_arrays(
    first: SeededValues,
    second: SeededValues,
    *,
    first_name: str,
    second_name: str,
) -> tuple[list[int], FloatArray, FloatArray]:
    first_by_seed = _seeded_values(first, name=first_name)
    second_by_seed = _seeded_values(second, name=second_name)
    first_seeds = set(first_by_seed)
    second_seeds = set(second_by_seed)
    if first_seeds != second_seeds:
        missing_from_first = sorted(second_seeds - first_seeds)
        missing_from_second = sorted(first_seeds - second_seeds)
        raise StatisticsError(
            "seed keys are misaligned: "
            f"missing from {first_name}={missing_from_first}, "
            f"missing from {second_name}={missing_from_second}"
        )
    seeds = sorted(first_seeds)
    first_array = np.asarray([first_by_seed[seed] for seed in seeds], dtype=np.float64)
    second_array = np.asarray(
        [second_by_seed[seed] for seed in seeds], dtype=np.float64
    )
    return seeds, first_array, second_array


def _description(array: FloatArray) -> dict[str, float | int]:
    standard_deviation = float(np.std(array, ddof=1)) if array.size > 1 else 0.0
    q10, q25, median, q75, q90 = np.quantile(
        array, (0.10, 0.25, 0.50, 0.75, 0.90), method="linear"
    )
    return {
        "n": int(array.size),
        "mean": float(np.mean(array)),
        "standard_deviation": standard_deviation,
        "standard_error": standard_deviation / math.sqrt(array.size),
        "median": float(median),
        "q10": float(q10),
        "q25": float(q25),
        "q75": float(q75),
        "q90": float(q90),
        "iqr": float(q75 - q25),
        "minimum": float(np.min(array)),
        "maximum": float(np.max(array)),
    }


def describe(values: ArrayLike | Iterable[float]) -> dict[str, float | int]:
    """Return the preregistered deterministic descriptive statistics."""

    return _description(_vector(values, name="descriptive values"))


def clopper_pearson_interval(
    successes: int,
    total: int,
    *,
    level: float = DEFAULT_CONFIDENCE_LEVEL,
) -> dict[str, Any]:
    """Return the exact equal-tailed two-sided binomial confidence interval."""

    total = _positive_integer(total, name="total")
    if isinstance(successes, (bool, np.bool_)) or not isinstance(successes, Integral):
        raise StatisticsError("successes must be an integer")
    successes = int(successes)
    if not 0 <= successes <= total:
        raise StatisticsError("successes must lie between zero and total")
    level = _level(level)
    alpha = 1.0 - level
    low = 0.0
    if successes > 0:
        low = float(
            beta_distribution.ppf(alpha / 2.0, successes, total - successes + 1)
        )
    high = 1.0
    if successes < total:
        high = float(
            beta_distribution.ppf(1.0 - alpha / 2.0, successes + 1, total - successes)
        )
    if not math.isfinite(low) or not math.isfinite(high):
        raise StatisticsError("SciPy returned a nonfinite Clopper-Pearson endpoint")
    return {
        "successes": successes,
        "n": total,
        "estimate": successes / total,
        "level": level,
        "method": "exact_clopper_pearson_two_sided",
        "ci_low": low,
        "ci_high": high,
        "ci": [low, high],
    }


def clopper_pearson_upper_bound(
    successes: int,
    total: int,
    *,
    level: float = DEFAULT_CONFIDENCE_LEVEL,
) -> dict[str, Any]:
    """Return the exact one-sided Clopper-Pearson upper confidence bound."""

    total = _positive_integer(total, name="total")
    if isinstance(successes, (bool, np.bool_)) or not isinstance(successes, Integral):
        raise StatisticsError("successes must be an integer")
    successes = int(successes)
    if not 0 <= successes <= total:
        raise StatisticsError("successes must lie between zero and total")
    level = _level(level)
    upper = 1.0
    if successes < total:
        upper = float(beta_distribution.ppf(level, successes + 1, total - successes))
    if not math.isfinite(upper):
        raise StatisticsError("SciPy returned a nonfinite Clopper-Pearson endpoint")
    return {
        "successes": successes,
        "n": total,
        "estimate": successes / total,
        "level": level,
        "method": "exact_clopper_pearson_one_sided_upper",
        "upper_bound": upper,
    }


def _bootstrap_indices(
    count: int,
    *,
    seed: int,
    resamples: int,
) -> NDArray[np.int64]:
    count = _positive_integer(count, name="seed count")
    seed = _seed(seed, name="bootstrap seed")
    resamples = _positive_integer(resamples, name="bootstrap resamples")
    generator = np.random.default_rng(seed)
    return generator.integers(
        0,
        count,
        size=(resamples, count),
        dtype=np.int64,
    )


def _bootstrap_mean_interval(
    values: FloatArray,
    indices: NDArray[np.int64],
    *,
    level: float,
) -> dict[str, Any]:
    draws = np.mean(values[indices], axis=1)
    alpha = 1.0 - level
    low, high = np.quantile(draws, (alpha / 2.0, 1.0 - alpha / 2.0), method="linear")
    return {
        "resamples": int(indices.shape[0]),
        "level": level,
        "method": "deterministic_seed_clustered_percentile_bootstrap",
        "estimate": float(np.mean(values)),
        "ci_low": float(low),
        "ci_high": float(high),
        "ci": [float(low), float(high)],
    }


def paired_seed_bootstrap(
    first: SeededValues,
    second: SeededValues,
    *,
    bootstrap_seed: int,
    resamples: int = DEFAULT_BOOTSTRAP_RESAMPLES,
    level: float = DEFAULT_CONFIDENCE_LEVEL,
) -> dict[str, Any]:
    """Summarize paired values and bootstrap the first-minus-second mean.

    A single resampled seed-index matrix is reused for both methods and their
    difference.  This preserves every within-seed dependency.
    """

    seeds, first_array, second_array = _aligned_seed_arrays(
        first,
        second,
        first_name="first",
        second_name="second",
    )
    level = _level(level)
    indices = _bootstrap_indices(len(seeds), seed=bootstrap_seed, resamples=resamples)
    difference = first_array - second_array

    def summarize(array: FloatArray) -> dict[str, Any]:
        return {
            **_description(array),
            "bootstrap_mean_interval": _bootstrap_mean_interval(
                array, indices, level=level
            ),
        }

    return {
        "method": "deterministic_paired_seed_bootstrap",
        "difference_definition": "first_minus_second",
        "seed_keys": seeds,
        "bootstrap_seed": _seed(bootstrap_seed, name="bootstrap seed"),
        "resamples": int(indices.shape[0]),
        "level": level,
        "first": summarize(first_array),
        "second": summarize(second_array),
        "paired_difference": summarize(difference),
    }


def zero_denominator_ratio_summary(
    numerators: Sequence[float] | ArrayLike,
    denominators: Sequence[float] | ArrayLike,
    *,
    zero_tolerance: float = 0.0,
) -> dict[str, Any]:
    """Describe ratios after omitting and counting zero denominators.

    No epsilon is added to a denominator.  A positive ``zero_tolerance`` is an
    explicit analysis threshold and is returned with the result.
    """

    numerator = _vector(numerators, name="ratio numerators")
    denominator = _vector(denominators, name="ratio denominators")
    if numerator.shape != denominator.shape:
        raise StatisticsError("ratio numerators and denominators must align")
    zero_tolerance = _finite_float(zero_tolerance, name="zero tolerance")
    if zero_tolerance < 0.0:
        raise StatisticsError("zero tolerance must be nonnegative")
    omitted = np.abs(denominator) <= zero_tolerance
    eligible = ~omitted
    ratios = numerator[eligible] / denominator[eligible]
    if not np.all(np.isfinite(ratios)):
        raise StatisticsError("ratio calculation produced a nonfinite value")
    ratio_description = _description(ratios) if ratios.size else None
    return {
        "n": int(numerator.size),
        "eligible_ratio_count": int(np.count_nonzero(eligible)),
        "zero_denominator_count": int(np.count_nonzero(omitted)),
        "zero_denominator_indices": np.flatnonzero(omitted).astype(int).tolist(),
        "zero_tolerance": zero_tolerance,
        "ratio": ratio_description,
    }


def four_corner_rank_tolerance_contrasts(
    observations: Iterable[CornerObservation],
    *,
    low_rank: int,
    high_rank: int,
    loose_tolerance: float,
    tight_tolerance: float,
    bootstrap_seed: int,
    resamples: int = DEFAULT_BOOTSTRAP_RESAMPLES,
    level: float = DEFAULT_CONFIDENCE_LEVEL,
) -> dict[str, Any]:
    """Estimate rank, tolerance, and interaction contrasts over four cells.

    Each observation is ``(seed, rank, tolerance, value)``.  Every seed must
    occur exactly once in every corner.  The bootstrap resamples whole seeds,
    preserving all four values in a cluster.
    """

    low_rank = _positive_integer(low_rank, name="low rank")
    high_rank = _positive_integer(high_rank, name="high rank")
    if low_rank >= high_rank:
        raise StatisticsError("low rank must be smaller than high rank")
    loose_tolerance = _finite_float(loose_tolerance, name="loose tolerance")
    tight_tolerance = _finite_float(tight_tolerance, name="tight tolerance")
    if loose_tolerance <= 0.0 or tight_tolerance <= 0.0:
        raise StatisticsError("CG tolerances must be positive")
    if tight_tolerance >= loose_tolerance:
        raise StatisticsError("tight tolerance must be smaller than loose tolerance")
    level = _level(level)

    corners = (
        (low_rank, loose_tolerance),
        (low_rank, tight_tolerance),
        (high_rank, loose_tolerance),
        (high_rank, tight_tolerance),
    )
    values_by_corner: dict[tuple[int, float], dict[int, float]] = {
        corner: {} for corner in corners
    }
    observation_count = 0
    for index, observation in enumerate(observations):
        try:
            raw_seed, raw_rank, raw_tolerance, raw_value = observation
        except (TypeError, ValueError) as error:
            raise StatisticsError(
                "four-corner observation "
                f"{index} must contain (seed, rank, tolerance, value)"
            ) from error
        seed = _seed(raw_seed, name=f"observation {index} seed")
        rank = _positive_integer(raw_rank, name=f"observation {index} rank")
        tolerance = _finite_float(raw_tolerance, name=f"observation {index} tolerance")
        value = _finite_float(raw_value, name=f"observation {index} value")
        corner = (rank, tolerance)
        if corner not in values_by_corner:
            raise StatisticsError(f"unexpected rank/tolerance corner {corner}")
        if seed in values_by_corner[corner]:
            raise StatisticsError(
                f"duplicate seed {seed} in rank/tolerance corner {corner}"
            )
        values_by_corner[corner][seed] = value
        observation_count += 1
    if observation_count == 0:
        raise StatisticsError("four-corner observations must be nonempty")

    reference_seeds = set(values_by_corner[corners[0]])
    if not reference_seeds:
        raise StatisticsError("every rank/tolerance corner must contain seeds")
    for corner in corners[1:]:
        corner_seeds = set(values_by_corner[corner])
        if corner_seeds != reference_seeds:
            raise StatisticsError(
                "rank/tolerance corner seed keys are misaligned: "
                f"corner={corner}, missing={sorted(reference_seeds - corner_seeds)}, "
                f"extra={sorted(corner_seeds - reference_seeds)}"
            )

    seeds = sorted(reference_seeds)

    def cell(rank: int, tolerance: float) -> FloatArray:
        by_seed = values_by_corner[(rank, tolerance)]
        return np.asarray([by_seed[seed] for seed in seeds], dtype=np.float64)

    low_loose = cell(low_rank, loose_tolerance)
    low_tight = cell(low_rank, tight_tolerance)
    high_loose = cell(high_rank, loose_tolerance)
    high_tight = cell(high_rank, tight_tolerance)

    rank_contrast = 0.5 * ((high_loose - low_loose) + (high_tight - low_tight))
    tolerance_contrast = 0.5 * ((low_tight - low_loose) + (high_tight - high_loose))
    interaction = (high_tight - high_loose) - (low_tight - low_loose)
    indices = _bootstrap_indices(len(seeds), seed=bootstrap_seed, resamples=resamples)

    def summarize(array: FloatArray, definition: str) -> dict[str, Any]:
        return {
            "definition": definition,
            **_description(array),
            "bootstrap_mean_interval": _bootstrap_mean_interval(
                array, indices, level=level
            ),
        }

    return {
        "method": "four_corner_seed_clustered_percentile_bootstrap",
        "seed_keys": seeds,
        "bootstrap_seed": _seed(bootstrap_seed, name="bootstrap seed"),
        "resamples": int(indices.shape[0]),
        "level": level,
        "corners": [
            {
                "rank": rank,
                "tolerance": tolerance,
                "summary": _description(cell(rank, tolerance)),
            }
            for rank, tolerance in corners
        ],
        "rank_high_minus_low": summarize(
            rank_contrast,
            "0.5 * [(high, loose) - (low, loose) + " "(high, tight) - (low, tight)]",
        ),
        "tolerance_tight_minus_loose": summarize(
            tolerance_contrast,
            "0.5 * [(low, tight) - (low, loose) + " "(high, tight) - (high, loose)]",
        ),
        "rank_tolerance_interaction": summarize(
            interaction,
            "[(high, tight) - (high, loose)] - " "[(low, tight) - (low, loose)]",
        ),
    }


__all__ = [
    "DEFAULT_BOOTSTRAP_RESAMPLES",
    "DEFAULT_CONFIDENCE_LEVEL",
    "StatisticsError",
    "clopper_pearson_interval",
    "clopper_pearson_upper_bound",
    "describe",
    "four_corner_rank_tolerance_contrasts",
    "paired_seed_bootstrap",
    "zero_denominator_ratio_summary",
]
