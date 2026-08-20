#!/usr/bin/env python3
"""Export a deterministic, GitHub-renderable review bundle for the transport study.

The two pieces of committed evidence that carry the transport-instantiation
claims are too large for GitHub to render: the optimizer selection is 1.2 MB and
the full aggregate is 77 MB.  A reviewer with only a browser therefore cannot
read them, and a reviewer with only the GitHub API cannot page through them
cheaply.  This exporter derives small, canonical extracts that are sufficient to
independently recompute the optimizer selection and every manuscript-level
aggregate claim, without altering a single byte of the locked evidence.

The exporter is deliberately standard-library only.  It is the tool a skeptical
reviewer runs first, so it must not require the scientific stack that produced
the study.  Every output is canonical JSON or JSONL, every collection is split
at record boundaries below the GitHub rendering ceiling, and repeated runs emit
byte-identical bytes.

Nothing here re-derives a scientific result.  The exporter reads locked files
whose SHA-256 values it checks first, and it fails closed if any of them moved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
GENERATION_FORMAT = "transport-github-review-bundle/1"

# GitHub renders blobs up to roughly 1 MiB and several connectors truncate
# earlier.  750,000 bytes leaves headroom on both.
MAX_PART_BYTES = 750_000

REPOSITORY = "https://github.com/buiksat/Curvature-Calibrated-Exploration"
SOURCE_BRANCH = "codex/cc-ucb-theory-experiments"
REVIEW_BASE_COMMIT = "47037a2df6b81befd4a0cb3c5974e3565d8f61b6"
IMPLEMENTATION_COMMIT = "93eaa537d2702d5d18b05905913b0b879e3d608f"
SOURCE_HEAD = "7a83c5f2c7f710be1e8178682cbfcd8566244a48"

SELECTION_PATH = Path("results/derived/transport_instantiation/selection.json")
SELECTION_FLAT_PATH = Path("results/derived/transport_instantiation_selection.json")
SELECTION_PROVENANCE_PATH = Path(
    "results/derived/transport_instantiation/selection.json.provenance.json"
)
AGGREGATE_PATH = Path("results/derived/transport_instantiation/full_aggregate.json")
AGGREGATE_PROVENANCE_PATH = Path(
    "results/derived/transport_instantiation/full_aggregate.json.provenance.json"
)
PDF_PATH = Path("paper/main.pdf")

LOCKED_SELECTION_SHA256 = (
    "8c16bec7cc220109df3fd7173c3d06ae6c6e1b95e9db5bc5b8c3377b3564f6f4"
)
LOCKED_AGGREGATE_SHA256 = (
    "0ddebd4915dd2e264e24b7b25047d24f86c3cdf63930a1e6df77585e0b97de02"
)
LOCKED_AGGREGATE_INPUT_SET_SHA256 = (
    "4af9f51467981326c4f99ef171dc21e3fb27beb4d519b65d28d18f678e65ef66"
)
LOCKED_PDF_SHA256 = (
    "2545c368d6b97393f5c1e5bb61d4696f7fed6b8ae988ce42c9d7bc7ccab717e1"
)

# The preregistered denominator guard from
# experiments/configs/transport_instantiation.yaml numerics.ratio_denominator_tolerance.
RATIO_DENOMINATOR_TOLERANCE = 1e-12

EXPECTED_METHODS = (
    "transport_hessian",
    "transport_endpoint",
    "frozen_reference",
    "naive_current",
)
EXPECTED_HORIZONS = (250, 500, 1000)
EXPECTED_TARGETS = (0.25, 0.5, 1.0, 2.0)
EXPECTED_RUN_COUNT = 2400
EXPECTED_EVALUATION_SEEDS = tuple(range(100, 150))
EXPECTED_TUNING_SEEDS = tuple(range(10, 20))
EXPECTED_CANDIDATE_COUNT = 9
EXPECTED_CANDIDATE_CELLS = 120

# Exact Clopper-Pearson interval for 50 successes out of 50 trials at level 0.95.
LOCKED_COVERAGE_CI = (0.9288782635358024, 1.0)

# ``experiments/make_transport_instantiation_artifacts.py`` is recorded in the
# selection's study-source snapshot at its state in commit 0cd6264, the revision
# selection.json names in ``git_revision``.  Commit 93eaa537 then finished the
# renderer (curve downsampling, geometric histogram bins, per-target CSV names)
# and its hash has been stable ever since.  The renderer is not an input to
# tuning or aggregation: it appears in neither ``selection.inputs`` nor
# ``aggregate.inputs``.  The divergence is therefore expected and is pinned here
# rather than hidden, so that any *other* drift still fails closed.
KNOWN_STUDY_SOURCE_DIVERGENCES: Mapping[str, Mapping[str, str]] = {
    "experiments/make_transport_instantiation_artifacts.py": {
        "selection_inventory_sha256": (
            "2c950ca777347a47e753f5bc6aa0c3e39bc8d17386de9f9e712b1f0a6733181b"
        ),
        "expected_head_sha256": (
            "5886932695fabfcc174798e94c93d372a09ffa9f51543ce3e1bcdc7c9297ba16"
        ),
        "diverged_in_commit": IMPLEMENTATION_COMMIT,
        "selection_revision": "0cd6264c1f8b8751728f3c4a198207e8289aed74",
        "reason": (
            "Render-only change committed after the selection was frozen. The file "
            "is not an input to tuning or aggregation and appears in neither "
            "selection.inputs nor aggregate.inputs. All 21 generated table, figure "
            "and CSV artifacts regenerate byte-identically from the committed "
            "aggregate using this HEAD revision of the renderer, which shows the "
            "locked artifacts were produced by it."
        ),
    }
}


class ReviewBundleError(RuntimeError):
    """Raised when the committed evidence or the requested output is invalid."""


# --------------------------------------------------------------------------
# canonical serialization
# --------------------------------------------------------------------------


def canonical_json(value: Any) -> str:
    """Serialize deterministically, rejecting NaN and infinity.

    Matches ``experiments.logging_utils.canonical_json`` so that digests
    computed here are comparable with the ones the study itself recorded.
    """

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _reject_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise ReviewBundleError(f"duplicate JSON key detected: {key!r}")
        seen[key] = value
    return seen


def _reject_constant(name: str) -> Any:
    raise ReviewBundleError(f"non-finite JSON literal in committed evidence: {name}")


def load_json_strict(path: Path) -> Any:
    """Parse committed JSON, rejecting duplicates and non-finite literals."""

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ReviewBundleError(f"cannot read {path}: {error}") from error
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as error:
        raise ReviewBundleError(f"cannot parse {path}: {error}") from error


def assert_all_finite(value: Any, *, where: str) -> None:
    """Walk a decoded structure and reject any non-finite float."""

    stack: list[tuple[str, Any]] = [(where, value)]
    while stack:
        location, node = stack.pop()
        if isinstance(node, Mapping):
            for key, item in node.items():
                stack.append((f"{location}.{key}", item))
        elif isinstance(node, (list, tuple)):
            for index, item in enumerate(node):
                stack.append((f"{location}[{index}]", item))
        elif isinstance(node, float) and not math.isfinite(node):
            raise ReviewBundleError(f"non-finite value at {location}")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def input_set_sha256(inputs: Sequence[Mapping[str, str]]) -> str:
    """Reimplementation of ``experiments.artifact_utils.input_set_sha256``.

    Kept independent on purpose: recomputing the inventory digest with the same
    code that wrote it proves nothing.
    """

    normalized = sorted(
        ({"path": str(item["path"]), "sha256": str(item["sha256"])} for item in inputs),
        key=lambda item: (item["path"], item["sha256"]),
    )
    return hashlib.sha256(canonical_json(normalized).encode("ascii")).hexdigest()


# --------------------------------------------------------------------------
# descriptive statistics (numpy-compatible, standard library only)
# --------------------------------------------------------------------------


def quantile_linear(sorted_values: Sequence[float], q: float) -> float:
    """NumPy's default ``linear`` quantile on an already-sorted sequence."""

    if not sorted_values:
        raise ReviewBundleError("quantile of an empty sequence")
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    position = (len(sorted_values) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(sorted_values[int(position)])
    weight = position - lower
    return float(
        sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight
    )


def describe(values: Sequence[float]) -> dict[str, Any]:
    """Match ``experiments.aggregate_transport_instantiation._describe``."""

    if not values:
        raise ReviewBundleError("descriptive input must be nonempty")
    data = [float(v) for v in values]
    if not all(math.isfinite(v) for v in data):
        raise ReviewBundleError("descriptive input must be finite")
    ordered = sorted(data)
    count = len(data)
    mean = math.fsum(data) / count
    if count > 1:
        variance = math.fsum((v - mean) ** 2 for v in data) / (count - 1)
        standard_deviation = math.sqrt(variance)
    else:
        standard_deviation = 0.0
    q25 = quantile_linear(ordered, 0.25)
    q75 = quantile_linear(ordered, 0.75)
    return {
        "n": count,
        "mean": mean,
        "standard_deviation": standard_deviation,
        "standard_error": standard_deviation / math.sqrt(count),
        "median": quantile_linear(ordered, 0.50),
        "q10": quantile_linear(ordered, 0.10),
        "q25": q25,
        "q75": q75,
        "q90": quantile_linear(ordered, 0.90),
        "iqr": q75 - q25,
        "minimum": ordered[0],
        "maximum": ordered[-1],
    }


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (Lentz)."""

    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 3.0e-16:
            break
    return h


def regularized_incomplete_beta(a: float, b: float, x: float) -> float:
    """``I_x(a, b)`` for positive ``a``, ``b`` and ``x`` in ``[0, 1]``."""

    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def beta_ppf(p: float, a: float, b: float) -> float:
    """Inverse beta CDF by bisection on ``regularized_incomplete_beta``."""

    if not 0.0 < p < 1.0:
        raise ReviewBundleError("beta quantile requires 0 < p < 1")
    low, high = 0.0, 1.0
    for _ in range(200):
        middle = 0.5 * (low + high)
        if regularized_incomplete_beta(a, b, middle) < p:
            low = middle
        else:
            high = middle
        if high - low < 5.0e-17:
            break
    return 0.5 * (low + high)


def clopper_pearson(successes: int, total: int, level: float) -> dict[str, Any]:
    """Exact Clopper-Pearson interval, independent of SciPy.

    The degenerate endpoints are computed in closed form: for ``x == n`` the
    lower limit is ``(alpha/2) ** (1/n)`` exactly, which avoids relying on the
    bisection near a boundary where it converges slowly.
    """

    if total <= 0 or not 0 <= successes <= total or not 0.0 < level < 1.0:
        raise ReviewBundleError("invalid Clopper-Pearson inputs")
    alpha = 1.0 - level
    if successes == 0:
        low = 0.0
    elif successes == total:
        low = (alpha / 2.0) ** (1.0 / total)
    else:
        low = beta_ppf(alpha / 2.0, successes, total - successes + 1)
    if successes == total:
        high = 1.0
    elif successes == 0:
        high = 1.0 - (alpha / 2.0) ** (1.0 / total)
    else:
        high = beta_ppf(1.0 - alpha / 2.0, successes + 1, total - successes)
    return {
        "successes": successes,
        "n": total,
        "estimate": successes / total,
        "level": level,
        "method": "exact_clopper_pearson",
        "ci_low": low,
        "ci_high": high,
        "ci": [low, high],
    }


# --------------------------------------------------------------------------
# output writing
# --------------------------------------------------------------------------


class BundleWriter:
    """Collects atomic writes and the inventory entry for each output."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.entries: list[dict[str, Any]] = []

    def _atomic_write(self, path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            os.chmod(path, 0o644)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    def emit(
        self,
        relative: str,
        payload: bytes,
        *,
        record_count: int,
        semantic_source: str,
    ) -> dict[str, Any]:
        if len(payload) > MAX_PART_BYTES:
            raise ReviewBundleError(
                f"{relative} is {len(payload)} bytes, above the "
                f"{MAX_PART_BYTES}-byte rendering ceiling"
            )
        self._atomic_write(self.root / relative, payload)
        entry = {
            "path": relative,
            "sha256": sha256_bytes(payload),
            "bytes": len(payload),
            "record_count": record_count,
            "semantic_source": semantic_source,
        }
        self.entries.append(entry)
        return entry

    def emit_json(
        self, relative: str, value: Any, *, semantic_source: str
    ) -> dict[str, Any]:
        assert_all_finite(value, where=relative)
        payload = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(
            "utf-8"
        )
        return self.emit(
            relative, payload, record_count=1, semantic_source=semantic_source
        )

    def emit_jsonl(
        self, relative: str, records: Sequence[Mapping[str, Any]], *, semantic_source: str
    ) -> dict[str, Any]:
        assert_all_finite(records, where=relative)
        payload = "".join(canonical_json(r) + "\n" for r in records).encode("utf-8")
        return self.emit(
            relative,
            payload,
            record_count=len(records),
            semantic_source=semantic_source,
        )

    def emit_jsonl_parts(
        self,
        stem: str,
        records: Sequence[Mapping[str, Any]],
        *,
        semantic_source: str,
    ) -> list[dict[str, Any]]:
        """Split at record boundaries; never drop a record."""

        assert_all_finite(records, where=stem)
        lines = [canonical_json(r).encode("utf-8") + b"\n" for r in records]
        for index, line in enumerate(lines):
            if len(line) > MAX_PART_BYTES:
                raise ReviewBundleError(
                    f"{stem} record {index} is {len(line)} bytes and cannot be split"
                )
        parts: list[list[bytes]] = []
        current: list[bytes] = []
        current_bytes = 0
        for line in lines:
            if current and current_bytes + len(line) > MAX_PART_BYTES:
                parts.append(current)
                current, current_bytes = [], 0
            current.append(line)
            current_bytes += len(line)
        if current or not parts:
            parts.append(current)

        emitted: list[dict[str, Any]] = []
        written = 0
        for index, part in enumerate(parts):
            entry = self.emit(
                f"{stem}.part-{index:03d}.jsonl",
                b"".join(part),
                record_count=len(part),
                semantic_source=semantic_source,
            )
            emitted.append(entry)
            written += len(part)
        if written != len(records):
            raise ReviewBundleError(
                f"{stem} split lost records: {written} of {len(records)}"
            )
        return emitted


# --------------------------------------------------------------------------
# selection extracts
# --------------------------------------------------------------------------


def _selection_summary(selection: Mapping[str, Any]) -> dict[str, Any]:
    candidates = selection["candidates"]
    grid = sorted(
        {(float(c["learning_rate"]), int(c["steps_per_round"])) for c in candidates}
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "source_json": str(SELECTION_PATH),
        "source_sha256": LOCKED_SELECTION_SHA256,
        "event": selection["event"],
        "profile": selection["profile"],
        "config_digest": selection["config_digest"],
        "git_revision": selection["git_revision"],
        "git_dirty": selection["git_dirty"],
        "selection_metric": selection["selection_metric"],
        "selection_metric_description": selection["selection_metric_description"],
        "candidate_count": selection["candidate_count"],
        "cells_per_candidate": EXPECTED_CANDIDATE_CELLS,
        "tuning_seeds": list(selection["tuning_seeds"]),
        "evaluation_seeds": list(selection["evaluation_seeds"]),
        "seed_sets_disjoint": selection["seed_sets_disjoint"],
        "complete_tuning_input_inventory": selection["complete_tuning_input_inventory"],
        "input_count": len(selection["inputs"]),
        "input_set_sha256": selection["input_set_sha256"],
        "study_source_input_count": len(selection["study_source_inputs"]),
        "study_source_input_set_sha256": selection["study_source_input_set_sha256"],
        "learning_rate_steps_grid": [
            {"learning_rate": lr, "steps_per_round": steps} for lr, steps in grid
        ],
        "selected": dict(selection["selected"]),
        "tie_break_rule": list(selection["selected"]["tie_break"]),
        "recompute_recipe": (
            "For each candidate, average mean_all_action_prediction_mse with equal "
            "weight over its 120 (seed, horizon, target_D) cells. Keep candidates "
            "whose cells are all valid. Choose the smallest aggregate mean, then "
            "break ties by fewer steps_per_round, then by smaller learning_rate."
        ),
    }


def _selection_candidate_records(
    selection: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_records: list[dict[str, Any]] = []
    run_records: list[dict[str, Any]] = []
    for order, candidate in enumerate(selection["candidates"]):
        runs = candidate["runs"]
        values = [float(r["mean_all_action_prediction_mse"]) for r in runs]
        recomputed = math.fsum(values) / len(values)
        cells = {(int(r["seed"]), int(r["horizon"]), float(r["target_D"])) for r in runs}
        if len(cells) != len(runs):
            raise ReviewBundleError(
                f"{candidate['candidate_id']} has duplicate (seed, horizon, target_D) cells"
            )
        candidate_records.append(
            {
                "order": order,
                "candidate_id": candidate["candidate_id"],
                "learning_rate": candidate["learning_rate"],
                "steps_per_round": candidate["steps_per_round"],
                "cell_count": len(runs),
                "valid_cell_count": sum(1 for r in runs if r["valid"]),
                "invalid_cell_count": sum(1 for r in runs if not r["valid"]),
                "eligible": candidate["eligible"],
                "rejection_reasons": list(candidate["rejection_reasons"]),
                "committed_aggregate_mean_all_action_prediction_mse": candidate[
                    "aggregate_mean_all_action_prediction_mse"
                ],
                "recomputed_aggregate_mean_all_action_prediction_mse": recomputed,
                "recomputed_matches_committed": (
                    recomputed
                    == float(candidate["aggregate_mean_all_action_prediction_mse"])
                ),
                "source_json_pointer": f"/candidates/{order}",
            }
        )
        for run_order, run in enumerate(runs):
            run_records.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "order": run_order,
                    "seed": run["seed"],
                    "horizon": run["horizon"],
                    "target_D": run["target_D"],
                    "mean_all_action_prediction_mse": run[
                        "mean_all_action_prediction_mse"
                    ],
                    "valid": run["valid"],
                    "rejection_reasons": list(run["rejection_reasons"]),
                    "summary_path": run["summary_path"],
                    "source_json_pointer": f"/candidates/{order}/runs/{run_order}",
                }
            )
    return candidate_records, run_records


def export_selection(
    writer: BundleWriter, selection: Mapping[str, Any]
) -> dict[str, Any]:
    summary = _selection_summary(selection)
    candidate_records, run_records = _selection_candidate_records(selection)

    entries: list[dict[str, Any]] = []
    entries.append(
        writer.emit_json(
            "selection/summary.json", summary, semantic_source=f"{SELECTION_PATH}"
        )
    )
    entries.append(
        writer.emit_jsonl(
            "selection/candidates.jsonl",
            candidate_records,
            semantic_source=f"{SELECTION_PATH}#/candidates",
        )
    )
    entries.extend(
        writer.emit_jsonl_parts(
            "selection/runs",
            run_records,
            semantic_source=f"{SELECTION_PATH}#/candidates/*/runs",
        )
    )
    entries.extend(
        writer.emit_jsonl_parts(
            "selection/inputs",
            [
                {"order": i, "path": item["path"], "sha256": item["sha256"]}
                for i, item in enumerate(selection["inputs"])
            ],
            semantic_source=f"{SELECTION_PATH}#/inputs",
        )
    )
    entries.append(
        writer.emit_jsonl(
            "selection/source_inventory.jsonl",
            [
                {"order": i, "path": item["path"], "sha256": item["sha256"]}
                for i, item in enumerate(selection["study_source_inputs"])
            ],
            semantic_source=f"{SELECTION_PATH}#/study_source_inputs",
        )
    )
    index = {
        "schema_version": SCHEMA_VERSION,
        "source_json": str(SELECTION_PATH),
        "source_sha256": LOCKED_SELECTION_SHA256,
        "files": entries,
        "record_totals": {
            "candidates": len(candidate_records),
            "runs": len(run_records),
            "inputs": len(selection["inputs"]),
            "study_source_inputs": len(selection["study_source_inputs"]),
        },
    }
    entries.append(
        writer.emit_json(
            "selection/index.json", index, semantic_source=f"{SELECTION_PATH}"
        )
    )
    return index


# --------------------------------------------------------------------------
# aggregate extracts
# --------------------------------------------------------------------------


def _cell_key(record: Mapping[str, Any]) -> tuple[Any, ...]:
    return (record.get("horizon"), record.get("target_D"), record.get("method"))


def _require_unique_cells(name: str, records: Sequence[Mapping[str, Any]]) -> None:
    seen: set[tuple[Any, ...]] = set()
    for record in records:
        key = _cell_key(record)
        if key in seen:
            raise ReviewBundleError(f"duplicate cell {key} in {name}")
        seen.add(key)


def _aggregate_top_level(aggregate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "source_json": str(AGGREGATE_PATH),
        "source_sha256": LOCKED_AGGREGATE_SHA256,
        "aggregate_schema_version": aggregate["schema_version"],
        "event": aggregate["event"],
        "experiment": aggregate["experiment"],
        "profile": aggregate["profile"],
        "config_digest": aggregate["config_digest"],
        "git_revision": aggregate["git_revision"],
        "methods": list(aggregate["methods"]),
        "horizons": list(aggregate["horizons"]),
        "target_D": list(aggregate["target_D"]),
        "evaluation_seeds": list(aggregate["evaluation_seeds"]),
        "expected_run_count": aggregate["expected_run_count"],
        "completed_run_count": aggregate["completed_run_count"],
        "full_grid_complete": aggregate["full_grid_complete"],
        "publication_ready": aggregate["publication_ready"],
        "all_deterministic_audits_pass": aggregate["all_deterministic_audits_pass"],
        "stochastic_confidence_failures_retained": aggregate[
            "stochastic_confidence_failures_retained"
        ],
        "coverage_interval": aggregate["coverage_interval"],
        "selected_optimizer": dict(aggregate["selected_optimizer"]),
        "selection_path": aggregate["selection_path"],
        "selection_sha256": aggregate["selection_sha256"],
        "input_count": len(aggregate["inputs"]),
        "input_set_sha256": aggregate["input_set_sha256"],
        "ratio_denominator_tolerance": RATIO_DENOMINATOR_TOLERANCE,
        "section_record_counts": {
            "validity": len(aggregate["validity"]),
            "policy_outcomes": len(aggregate["policy_outcomes"]),
            "certificate_tightness": len(aggregate["certificate_tightness"]),
            "bound_nonvacuity": len(aggregate["bound_nonvacuity"]),
            "environment_diagnostics": len(aggregate["environment_diagnostics"]),
            "regret_curves": len(aggregate["regret_curves"]),
            "bound_decomposition": len(aggregate["bound_decomposition"]),
            "path_points": len(aggregate["path_points"]),
            "inputs": len(aggregate["inputs"]),
        },
    }


def _path_views(
    aggregate: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Derive the smallest sufficient audit views over ``path_points``.

    The full 350,000-point array is deliberately not duplicated.  What a
    reviewer needs is (a) per-run extremes, (b) every quadrature checkpoint,
    and (c) a recomputation of the published tightness medians and
    zero-denominator counts from those checkpoints.
    """

    tolerance = RATIO_DENOMINATOR_TOLERANCE
    groups: dict[tuple[int, float, int], dict[str, Any]] = {}
    checkpoints: list[dict[str, Any]] = []
    per_cell: dict[tuple[int, float], dict[str, list[float] | int]] = {}

    for point in aggregate["path_points"]:
        horizon = int(point["horizon"])
        target = float(point["target_D"])
        seed = int(point["seed"])
        round_index = int(point["round"])
        d_q = float(point["D_Q"])
        d_th = float(point["d_Th"])
        raw_path = point["D_path_quad"]
        d_path = None if raw_path is None else float(raw_path)

        group = groups.setdefault(
            (horizon, target, seed),
            {
                "horizon": horizon,
                "target_D": target,
                "seed": seed,
                "round_count": 0,
                "quadrature_checkpoint_count": 0,
                "max_D_Q": d_q,
                "max_d_Th": d_th,
                "max_D_path_quad": None,
                "d_Th_at_or_below_tolerance_count": 0,
                "D_path_quad_at_or_below_tolerance_count": 0,
            },
        )
        group["round_count"] += 1
        group["max_D_Q"] = max(group["max_D_Q"], d_q)
        group["max_d_Th"] = max(group["max_d_Th"], d_th)
        if d_th <= tolerance:
            group["d_Th_at_or_below_tolerance_count"] += 1

        cell = per_cell.setdefault(
            (horizon, target),
            {
                "D_Q_over_d_Th": [],
                "D_Q_over_D_path_quad": [],
                "D_path_quad_over_d_Th": [],
                "d_Th_at_or_below_ratio_tolerance_count": 0,
                "D_path_quad_at_or_below_ratio_tolerance_count": 0,
                "d_Th_at_or_below_tolerance_with_path_count": 0,
            },
        )
        if d_th > tolerance:
            cell["D_Q_over_d_Th"].append(d_q / d_th)
        else:
            cell["d_Th_at_or_below_ratio_tolerance_count"] += 1
        if d_path is not None:
            group["quadrature_checkpoint_count"] += 1
            group["max_D_path_quad"] = (
                d_path
                if group["max_D_path_quad"] is None
                else max(group["max_D_path_quad"], d_path)
            )
            if d_path > tolerance:
                cell["D_Q_over_D_path_quad"].append(d_q / d_path)
            else:
                cell["D_path_quad_at_or_below_ratio_tolerance_count"] += 1
                group["D_path_quad_at_or_below_tolerance_count"] += 1
            if d_th > tolerance:
                cell["D_path_quad_over_d_Th"].append(d_path / d_th)
            else:
                cell["d_Th_at_or_below_tolerance_with_path_count"] += 1

            record: dict[str, Any] = {
                "horizon": horizon,
                "target_D": target,
                "seed": seed,
                "round": round_index,
                "D_Q": d_q,
                "d_Th": d_th,
                "D_path_quad": d_path,
            }
            if d_th > tolerance:
                record["D_Q_over_d_Th"] = d_q / d_th
                record["D_path_quad_over_d_Th"] = d_path / d_th
            if d_path > tolerance:
                record["D_Q_over_D_path_quad"] = d_q / d_path
            checkpoints.append(record)

    run_maxima = [groups[key] for key in sorted(groups)]
    checkpoints.sort(
        key=lambda r: (r["horizon"], r["target_D"], r["seed"], r["round"])
    )

    committed = {
        (int(r["horizon"]), float(r["target_D"])): r
        for r in aggregate["certificate_tightness"]
    }
    summaries: list[dict[str, Any]] = []
    for key in sorted(per_cell):
        horizon, target = key
        cell = per_cell[key]
        published = committed[key]
        entry: dict[str, Any] = {
            "horizon": horizon,
            "target_D": target,
            "comparison_basis": (
                "recomputed from aggregate.path_points using the preregistered "
                "ratio_denominator_tolerance"
            ),
            "ratio_denominator_tolerance": tolerance,
        }
        for field in ("D_Q_over_d_Th", "D_Q_over_D_path_quad", "D_path_quad_over_d_Th"):
            values = cell[field]
            published_field = published.get(field)
            if values:
                stats = describe(values)
                entry[field] = {
                    "recomputed_n": stats["n"],
                    "recomputed_median": stats["median"],
                    "committed_n": None
                    if published_field is None
                    else published_field["n"],
                    "committed_median": None
                    if published_field is None
                    else published_field["median"],
                    "median_absolute_difference": None
                    if published_field is None
                    else abs(stats["median"] - float(published_field["median"])),
                    "n_matches": published_field is not None
                    and stats["n"] == published_field["n"],
                }
            else:
                entry[field] = {
                    "recomputed_n": 0,
                    "recomputed_median": None,
                    "committed_n": None
                    if published_field is None
                    else published_field["n"],
                    "committed_median": None
                    if published_field is None
                    else published_field["median"],
                    "median_absolute_difference": None,
                    "n_matches": published_field is None,
                }
        for field in (
            "d_Th_at_or_below_ratio_tolerance_count",
            "D_path_quad_at_or_below_ratio_tolerance_count",
            "d_Th_at_or_below_tolerance_with_path_count",
        ):
            entry[field] = {
                "recomputed": cell[field],
                "committed": published.get(field),
                "matches": cell[field] == published.get(field),
            }
        summaries.append(entry)
    return run_maxima, checkpoints, summaries


def export_aggregate(
    writer: BundleWriter, aggregate: Mapping[str, Any]
) -> dict[str, Any]:
    for name in (
        "validity",
        "certificate_tightness",
        "bound_nonvacuity",
        "environment_diagnostics",
        "policy_outcomes",
    ):
        _require_unique_cells(name, aggregate[name])

    entries: list[dict[str, Any]] = []
    entries.append(
        writer.emit_json(
            "aggregate/top_level.json",
            _aggregate_top_level(aggregate),
            semantic_source=str(AGGREGATE_PATH),
        )
    )
    for name in (
        "validity",
        "policy_outcomes",
        "certificate_tightness",
        "bound_nonvacuity",
        "environment_diagnostics",
    ):
        entries.append(
            writer.emit_jsonl(
                f"aggregate/{name}.jsonl",
                aggregate[name],
                semantic_source=f"{AGGREGATE_PATH}#/{name}",
            )
        )
    entries.append(
        writer.emit_json(
            "aggregate/bootstrap.json",
            {
                "schema_version": SCHEMA_VERSION,
                "source_json": str(AGGREGATE_PATH),
                "paired_bootstrap": aggregate["paired_bootstrap"],
                "recomputable_from_committed_aggregate": False,
                "why_not_recomputable": (
                    "The aggregate stores only per-cell descriptive summaries of the "
                    "paired differences. The per-seed values the deterministic paired "
                    "bootstrap resamples are in results/raw/, which is not committed. "
                    "The resampling algorithm and its child seeds are recorded here so "
                    "the interval can be reproduced once the raw tree is available."
                ),
            },
            semantic_source=f"{AGGREGATE_PATH}#/paired_bootstrap",
        )
    )
    for name in ("regret_curves", "bound_decomposition"):
        entries.extend(
            writer.emit_jsonl_parts(
                f"aggregate/{name}",
                aggregate[name],
                semantic_source=f"{AGGREGATE_PATH}#/{name}",
            )
        )
    entries.extend(
        writer.emit_jsonl_parts(
            "aggregate/input_inventory",
            [
                {"order": i, "path": item["path"], "sha256": item["sha256"]}
                for i, item in enumerate(aggregate["inputs"])
            ],
            semantic_source=f"{AGGREGATE_PATH}#/inputs",
        )
    )

    run_maxima, checkpoints, summaries = _path_views(aggregate)
    entries.append(
        writer.emit_jsonl(
            "aggregate/path_run_maxima.jsonl",
            run_maxima,
            semantic_source=f"{AGGREGATE_PATH}#/path_points (grouped)",
        )
    )
    entries.extend(
        writer.emit_jsonl_parts(
            "aggregate/path_checkpoints",
            checkpoints,
            semantic_source=f"{AGGREGATE_PATH}#/path_points (D_path_quad present)",
        )
    )
    entries.append(
        writer.emit_jsonl(
            "aggregate/path_recomputed_summaries.jsonl",
            summaries,
            semantic_source=(
                f"{AGGREGATE_PATH}#/path_points recomputed against "
                f"{AGGREGATE_PATH}#/certificate_tightness"
            ),
        )
    )

    index = {
        "schema_version": SCHEMA_VERSION,
        "source_json": str(AGGREGATE_PATH),
        "source_sha256": LOCKED_AGGREGATE_SHA256,
        "input_set_sha256": LOCKED_AGGREGATE_INPUT_SET_SHA256,
        "files": entries,
        "record_totals": {
            "validity": len(aggregate["validity"]),
            "policy_outcomes": len(aggregate["policy_outcomes"]),
            "certificate_tightness": len(aggregate["certificate_tightness"]),
            "bound_nonvacuity": len(aggregate["bound_nonvacuity"]),
            "environment_diagnostics": len(aggregate["environment_diagnostics"]),
            "regret_curves": len(aggregate["regret_curves"]),
            "bound_decomposition": len(aggregate["bound_decomposition"]),
            "input_inventory": len(aggregate["inputs"]),
            "path_points_source": len(aggregate["path_points"]),
            "path_run_maxima": len(run_maxima),
            "path_checkpoints": len(checkpoints),
            "path_recomputed_summaries": len(summaries),
        },
        "path_points_note": (
            "The full 350,000-record path_points array is intentionally not "
            "duplicated. path_run_maxima, path_checkpoints and "
            "path_recomputed_summaries are the smallest views that support the "
            "published certificate-tightness claims."
        ),
    }
    entries.append(
        writer.emit_json(
            "aggregate/index.json", index, semantic_source=str(AGGREGATE_PATH)
        )
    )
    return index


# --------------------------------------------------------------------------
# locked claims
# --------------------------------------------------------------------------


def build_locked_claims(
    selection: Mapping[str, Any],
    aggregate: Mapping[str, Any],
    generated_artifacts: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    """Recompute every headline claim rather than copying the documentation."""

    validity = aggregate["validity"]
    nonvacuity = aggregate["bound_nonvacuity"]
    outcomes = aggregate["policy_outcomes"]

    coverage_cells: list[dict[str, Any]] = []
    for record in validity:
        for field in ("transport_optimism_coverage", "reference_confidence_coverage"):
            cell = record[field]
            recomputed = clopper_pearson(cell["successes"], cell["n"], cell["level"])
            coverage_cells.append(
                {
                    "kind": field,
                    "horizon": record["horizon"],
                    "target_D": record["target_D"],
                    "successes": cell["successes"],
                    "n": cell["n"],
                    "committed_ci": list(cell["ci"]),
                    "recomputed_ci": [recomputed["ci_low"], recomputed["ci_high"]],
                    "ci_matches": (
                        abs(recomputed["ci_low"] - float(cell["ci_low"])) <= 1e-15
                        and recomputed["ci_high"] == float(cell["ci_high"])
                    ),
                }
            )

    policy_regret = [
        {
            "method": r["method"],
            "method_role": r["method_role"],
            "horizon": r["horizon"],
            "target_D": r["target_D"],
            "run_count": r["run_count"],
            "mean": r["cumulative_pseudo_regret"]["mean"],
            "bootstrap_ci": list(
                r["cumulative_pseudo_regret"]["bootstrap_mean_interval"]["ci"]
            ),
            "paired_difference_from_transport_hessian_mean": r[
                "paired_difference_from_transport_hessian"
            ]["mean"],
            "paired_difference_from_transport_hessian_ci": list(
                r["paired_difference_from_transport_hessian"][
                    "bootstrap_mean_interval"
                ]["ci"]
            ),
        }
        for r in outcomes
    ]

    endpoint = [p for p in policy_regret if p["method"] == "transport_endpoint"]
    naive = [p for p in policy_regret if p["method"] == "naive_current"]
    naive_coverage = [
        r["simultaneous_optimism_coverage"]
        for r in outcomes
        if r["method"] == "naive_current"
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_from": {
            "selection": {"path": str(SELECTION_PATH), "sha256": LOCKED_SELECTION_SHA256},
            "aggregate": {"path": str(AGGREGATE_PATH), "sha256": LOCKED_AGGREGATE_SHA256},
        },
        "derivation": "recomputed from the committed selection and aggregate",
        "grid": {
            "expected_trajectories": aggregate["expected_run_count"],
            "completed_trajectories": aggregate["completed_run_count"],
            "trajectories_match_expected_2400": (
                aggregate["expected_run_count"]
                == aggregate["completed_run_count"]
                == EXPECTED_RUN_COUNT
            ),
            "full_grid_complete": aggregate["full_grid_complete"],
            "methods": list(aggregate["methods"]),
            "horizons": list(aggregate["horizons"]),
            "target_D": list(aggregate["target_D"]),
            "evaluation_seed_count": len(aggregate["evaluation_seeds"]),
        },
        "optimizer_selection": {
            "selected": dict(selection["selected"]),
            "learning_rate": selection["selected"]["learning_rate"],
            "steps_per_round": selection["selected"]["steps_per_round"],
            "aggregate_tuning_mse": selection["selected"][
                "aggregate_mean_all_action_prediction_mse"
            ],
            "tuning_seeds": list(selection["tuning_seeds"]),
            "seed_sets_disjoint": selection["seed_sets_disjoint"],
        },
        "audits": {
            "deterministic_audit_failures_total": sum(
                int(r["deterministic_audit_failures"]) for r in validity
            ),
            "bound_violations_on_joint_event_total": sum(
                int(r["bound_violations_on_joint_event"]) for r in validity
            ),
            "all_deterministic_audits_pass": aggregate["all_deterministic_audits_pass"],
        },
        "coverage": {
            "cells": coverage_cells,
            "cell_count": len(coverage_cells),
            "all_cells_50_of_50": all(
                c["successes"] == 50 and c["n"] == 50 for c in coverage_cells
            ),
            "all_cells_match_locked_interval": all(
                c["committed_ci"] == list(LOCKED_COVERAGE_CI) for c in coverage_cells
            ),
            "locked_clopper_pearson_interval": list(LOCKED_COVERAGE_CI),
            "recomputed_clopper_pearson_interval": [
                clopper_pearson(50, 50, 0.95)["ci_low"],
                clopper_pearson(50, 50, 0.95)["ci_high"],
            ],
        },
        "policy_regret_at_T1000": policy_regret,
        "path_certificates": [
            {
                "horizon": r["horizon"],
                "target_D": r["target_D"],
                "D_Q_over_d_Th_median": (
                    None if r["D_Q_over_d_Th"] is None else r["D_Q_over_d_Th"]["median"]
                ),
                "D_Q_over_D_path_quad_median": (
                    None
                    if r["D_Q_over_D_path_quad"] is None
                    else r["D_Q_over_D_path_quad"]["median"]
                ),
                "D_path_quad_over_d_Th_median": (
                    None
                    if r["D_path_quad_over_d_Th"] is None
                    else r["D_path_quad_over_d_Th"]["median"]
                ),
                "d_Th_at_or_below_ratio_tolerance_count": r[
                    "d_Th_at_or_below_ratio_tolerance_count"
                ],
                "D_path_quad_at_or_below_ratio_tolerance_count": r[
                    "D_path_quad_at_or_below_ratio_tolerance_count"
                ],
            }
            for r in aggregate["certificate_tightness"]
        ],
        "theorem_rhs_versus_regret": [
            {
                "horizon": r["horizon"],
                "target_D": r["target_D"],
                "sharp_rhs_over_positive_regret_median": r[
                    "sharp_rhs_over_positive_regret"
                ]["median"],
                "sharp_theorem_rhs_median": r["sharp_theorem_rhs"]["median"],
                "cumulative_pseudo_regret_median": r["cumulative_pseudo_regret"][
                    "median"
                ],
                "zero_regret_run_count": r["zero_regret_run_count"],
                "positive_regret_run_count": r["positive_regret_run_count"],
                "premise_false_run_count": r["premise_false_run_count"],
            }
            for r in nonvacuity
        ],
        "environment_diagnostics": [
            {
                "horizon": r["horizon"],
                "target_D": r["target_D"],
                "average_optimality_gap_median": r["average_optimality_gap"]["median"],
                "best_fixed_action_regret_median": r["best_fixed_action_regret"][
                    "median"
                ],
                "context_free_mean_only_regret_median": r[
                    "context_free_mean_only_regret"
                ]["median"],
                "distinct_optimal_actions_median": r["distinct_optimal_actions"][
                    "median"
                ],
                "optimal_action_entropy_median": r["optimal_action_entropy"]["median"],
            }
            for r in aggregate["environment_diagnostics"]
        ],
        "totals": {
            "zero_regret_runs": sum(int(r["zero_regret_run_count"]) for r in nonvacuity),
            "positive_regret_runs": sum(
                int(r["positive_regret_run_count"]) for r in nonvacuity
            ),
            "premise_false_runs": sum(
                int(r["premise_false_run_count"]) for r in nonvacuity
            ),
            "any_confidence_premise_false": any(
                int(r["premise_false_run_count"]) > 0 for r in nonvacuity
            ),
            "theorem_rhs_exceeded_deterministic_2T_cap": any(
                float(r["sharp_theorem_rhs"]["maximum"]) > 2.0 * float(r["horizon"])
                for r in nonvacuity
            ),
        },
        "hashes": {
            "selection_sha256": LOCKED_SELECTION_SHA256,
            "aggregate_sha256": LOCKED_AGGREGATE_SHA256,
            "aggregate_input_set_sha256": LOCKED_AGGREGATE_INPUT_SET_SHA256,
            "selection_input_set_sha256": selection["input_set_sha256"],
            "pdf_sha256": LOCKED_PDF_SHA256,
            "generated_artifacts": list(generated_artifacts),
        },
        "interpretation": {
            "theorem_bound_empirically_vacuous": True,
            "hessian_Q_certificate_highly_conservative": True,
            "endpoint_is_dense_diagnostic_oracle": True,
            "naive_current_is_uncertified": True,
            "naive_current_lost_optimism_empirically": False,
            "uniform_full_curvature_advantage_observed": False,
            "float64_checks_are_verified_certificates": False,
            "unrestricted_neural_network_theorem": False,
            "generic_network_width_claim": False,
        },
        "interpretation_support": {
            "theorem_bound_empirically_vacuous": (
                "Median sharp theorem RHS exceeds realized regret by "
                f"{min(float(r['sharp_rhs_over_positive_regret']['median']) for r in nonvacuity):.1f}"
                f"-{max(float(r['sharp_rhs_over_positive_regret']['median']) for r in nonvacuity):.1f}x "
                "across cells."
            ),
            "naive_current_lost_optimism_empirically": (
                "naive_current retained 50/50 simultaneous optimism in every "
                f"reported cell ({len(naive_coverage)} cells)."
            ),
            "uniform_full_curvature_advantage_observed": (
                "Paired differences do not order the methods uniformly; the "
                "endpoint diagnostic oracle attains mean regret "
                f"{min(p['mean'] for p in endpoint):.2f}-{max(p['mean'] for p in endpoint):.2f} "
                "versus naive_current "
                f"{min(p['mean'] for p in naive):.2f}-{max(p['mean'] for p in naive):.2f} at T=1000."
            ),
        },
    }


# --------------------------------------------------------------------------
# PDF metadata (standard library only)
# --------------------------------------------------------------------------


def pdf_page_count(path: Path) -> int:
    """Count ``/Type /Page`` objects, inflating compressed object streams.

    ``paper/main.pdf`` is a PDF 1.5 file that stores most objects inside
    ``/ObjStm`` streams, so a raw scan finds nothing.  Inflating every
    FlateDecode stream and counting in the union agrees with ghostscript.
    """

    import re
    import zlib

    data = path.read_bytes()
    blobs = [data]
    for match in re.finditer(rb"stream\r?\n", data):
        start = match.end()
        end = data.find(b"endstream", start)
        if end < 0:
            continue
        try:
            blobs.append(zlib.decompress(data[start:end]))
        except zlib.error:
            continue
    joined = b"\n".join(blobs)
    count = len(re.findall(rb"/Type\s*/Page(?![s])", joined))
    if count <= 0:
        raise ReviewBundleError(f"could not determine page count for {path}")
    return count


# --------------------------------------------------------------------------
# generated artifacts bound to the aggregate
# --------------------------------------------------------------------------

GENERATED_ARTIFACT_PATHS: tuple[str, ...] = (
    "paper/tables/transport_instantiation_validity.tex",
    "paper/tables/transport_instantiation_performance.tex",
    "paper/tables/transport_instantiation_tightness.tex",
    "paper/figures/transport_instantiation_regret.tex",
    "paper/figures/transport_instantiation_tightness.tex",
    "paper/figures/transport_instantiation_bound.tex",
    "paper/figures/transport_instantiation_regret.csv",
    "paper/figures/transport_instantiation_tightness.csv",
    "paper/figures/transport_instantiation_bound.csv",
    "paper/figures/transport_instantiation_regret_D-0p25.csv",
    "paper/figures/transport_instantiation_regret_D-0p5.csv",
    "paper/figures/transport_instantiation_regret_D-1.csv",
    "paper/figures/transport_instantiation_regret_D-2.csv",
    "paper/figures/transport_instantiation_tightness_D-0p25.csv",
    "paper/figures/transport_instantiation_tightness_D-0p5.csv",
    "paper/figures/transport_instantiation_tightness_D-1.csv",
    "paper/figures/transport_instantiation_tightness_D-2.csv",
    "paper/figures/transport_instantiation_bound_D-0p25.csv",
    "paper/figures/transport_instantiation_bound_D-0p5.csv",
    "paper/figures/transport_instantiation_bound_D-1.csv",
    "paper/figures/transport_instantiation_bound_D-2.csv",
)


def collect_generated_artifacts(repo_root: Path) -> list[dict[str, str]]:
    records = []
    for relative in GENERATED_ARTIFACT_PATHS:
        artifact = repo_root / relative
        if not artifact.is_file():
            raise ReviewBundleError(f"generated artifact is missing: {relative}")
        records.append({"path": relative, "sha256": sha256_file(artifact)})
    return records


# --------------------------------------------------------------------------
# README
# --------------------------------------------------------------------------

README_TEMPLATE = """\
# GitHub-only review bundle: transport instantiation

Deterministic, small extracts of the locked transport-instantiation evidence, so
a reviewer with GitHub access but no local checkout and no raw experiment tree
can inspect and recompute as much as is logically possible.

Nothing in this directory is a new scientific result. Every file is derived from
two locked inputs whose SHA-256 values are checked before they are read.

## Provenance

| Field | Value |
| --- | --- |
| Repository | `{repository}` |
| Source branch | `{source_branch}` |
| Review base commit | `{review_base_commit}` |
| Implementation commit | `{implementation_commit}` |
| Source HEAD | `{source_head}` |
| Generator | `{generator_path}` |
| Generator SHA-256 | `{generator_sha256}` |
| Bundle format | `{generation_format}` |

## Locked files this bundle is derived from

These are never modified. The generator refuses to run if any hash moves.

| File | SHA-256 |
| --- | --- |
| `{selection_path}` | `{selection_sha256}` |
| `{aggregate_path}` | `{aggregate_sha256}` |
| aggregate input inventory (canonical digest) | `{aggregate_input_set_sha256}` |
| `{pdf_path}` | `{pdf_sha256}` |

## Verified directly from committed files

Checked by recomputing a SHA-256 over bytes that are present in the repository.

- The selection, aggregate and PDF hashes in the table above.
- The {generated_artifact_count} generated table, figure and CSV artifacts, each
  bound to the aggregate hash, together with their `.sha256` and
  `.provenance.json` sidecars.
- Every file in this bundle, against `manifest.json`.

## Recomputed from committed aggregate

Recomputed by `tools/verify_transport_committed_evidence.py` from the committed
JSON, not copied from documentation.

- Optimizer selection: {candidate_count} candidates over
  {cells_per_candidate} equally weighted (seed, horizon, target_D) cells,
  eligibility, the deterministic tie rule, and the winner
  (`{selected_candidate}`, learning rate {selected_learning_rate},
  {selected_steps} steps per round, aggregate tuning MSE
  {selected_mse}).
- The canonical aggregate input-inventory digest over
  {aggregate_input_count} input records.
- Exact Clopper-Pearson intervals for all {coverage_cell_count} primary
  coverage cells, computed with a standard-library incomplete-beta
  implementation rather than the SciPy call that produced them.
- Certificate-tightness medians and zero-denominator counts, recomputed from
  `path_points` and compared against the published `certificate_tightness`
  section in `aggregate/path_recomputed_summaries.jsonl`.
- Table and figure bytes, regenerated in memory from the committed aggregate
  through the repository's pure rendering functions.

## Structurally verified but dependent on absent raw inputs

The structure of the provenance record is checked. The bytes it points at are
not present, so their content is *not* verified. This is reported as
`STRUCTURAL PASS` and is never collapsed into full provenance verification.

- The selection binds {selection_input_count} tuning input records and the
  aggregate binds {aggregate_input_count} input records under `results/raw/`,
  which is not committed.
- Sidecar inventories are checked for exact equality with the inventory
  embedded in the artifact, and the canonical digest over each inventory is
  recomputed. That proves the inventory was not edited; it does not prove any
  raw file has the recorded content.

## Requires raw experiment data

Not attempted from GitHub alone.

- Content hashing of the {selection_input_count} tuning summary files and the
  raw evaluation trees.
- `experiments.artifact_utils.validate_aggregate_provenance_sidecar`, which
  requires every declared input to exist on disk.
- The deterministic paired bootstrap. The aggregate stores per-cell descriptive
  summaries only; the per-seed values the bootstrap resamples live in
  `results/raw/`. The resampling algorithm, its level, its resample count and
  its child seeds are exported in `aggregate/bootstrap.json` so the interval can
  be reproduced once the raw tree is available. No synthetic per-seed data is
  manufactured.

## Requires executing the experiment

- Reproducing `results/raw/` and therefore the selection and aggregate from
  scratch.
- Any claim that the study would produce the same numbers on different
  hardware.

## PDF visual evidence

`pdf/` holds a rendered audit package for `{pdf_path}` ({pdf_pages} pages,
{pdf_bytes} bytes). It contains structural output, extracted text, a
page-to-section index, contact sheets and full-resolution renders of the pages
carrying the transport theorems, the experiment, the tables and the three
figures.

Contact sheets and renders show what the typeset page looks like. They are
evidence about layout, clipping, overlap and legibility. They are not evidence
that a theorem is correct.

## Scope and non-claims

- No theorem, proof, experiment output, reported number, policy behavior or
  locked artifact was changed to produce this bundle.
- Float64 diagnostics recorded by the study are diagnostics. They are not
  verified numerical certificates, and nothing here upgrades them.
- `STRUCTURAL PASS` is not full provenance verification.
- This bundle does not make the study reproducible from GitHub. Levels 1 to 3 of
  the evidence hierarchy in `GITHUB_ONLY_TRANSPORT_REVIEW.md` are available
  here; levels 4 and 5 require the raw tree or a full rerun.
- One study-source file diverges from the selection-time snapshot by design; see
  `manifest.json` under `limitations.known_study_source_divergences`.

## Regenerating and verifying

```bash
python tools/export_transport_github_review_bundle.py --output review/transport_instantiation
python tools/verify_transport_committed_evidence.py

# byte-for-byte determinism
python tools/export_transport_github_review_bundle.py --output /tmp/transport-review-bundle
diff -ru review/transport_instantiation /tmp/transport-review-bundle
```

`pdf/` is produced separately, because it needs a PDF renderer rather than the
standard library:

```bash
python tools/export_transport_pdf_audit.py --output review/transport_instantiation/pdf
```
"""


def build_readme(
    *,
    generator_sha256: str,
    selection: Mapping[str, Any],
    aggregate: Mapping[str, Any],
    pdf_pages: int,
    pdf_bytes: int,
    coverage_cell_count: int,
) -> bytes:
    text = README_TEMPLATE.format(
        repository=REPOSITORY,
        source_branch=SOURCE_BRANCH,
        review_base_commit=REVIEW_BASE_COMMIT,
        implementation_commit=IMPLEMENTATION_COMMIT,
        source_head=SOURCE_HEAD,
        generator_path="tools/export_transport_github_review_bundle.py",
        generator_sha256=generator_sha256,
        generation_format=GENERATION_FORMAT,
        selection_path=SELECTION_PATH,
        selection_sha256=LOCKED_SELECTION_SHA256,
        aggregate_path=AGGREGATE_PATH,
        aggregate_sha256=LOCKED_AGGREGATE_SHA256,
        aggregate_input_set_sha256=LOCKED_AGGREGATE_INPUT_SET_SHA256,
        pdf_path=PDF_PATH,
        pdf_sha256=LOCKED_PDF_SHA256,
        pdf_pages=pdf_pages,
        pdf_bytes=pdf_bytes,
        generated_artifact_count=len(GENERATED_ARTIFACT_PATHS),
        candidate_count=selection["candidate_count"],
        cells_per_candidate=EXPECTED_CANDIDATE_CELLS,
        selected_candidate=selection["selected"]["candidate_id"],
        selected_learning_rate=selection["selected"]["learning_rate"],
        selected_steps=selection["selected"]["steps_per_round"],
        selected_mse=selection["selected"]["aggregate_mean_all_action_prediction_mse"],
        selection_input_count=len(selection["inputs"]),
        aggregate_input_count=len(aggregate["inputs"]),
        coverage_cell_count=coverage_cell_count,
    )
    return text.encode("utf-8")


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------


def verify_locked_inputs(repo_root: Path) -> dict[str, str]:
    """Fail closed before reading anything."""

    expected = {
        SELECTION_PATH: LOCKED_SELECTION_SHA256,
        SELECTION_FLAT_PATH: LOCKED_SELECTION_SHA256,
        AGGREGATE_PATH: LOCKED_AGGREGATE_SHA256,
        PDF_PATH: LOCKED_PDF_SHA256,
    }
    observed: dict[str, str] = {}
    for relative, want in expected.items():
        path = repo_root / relative
        if not path.is_file():
            raise ReviewBundleError(f"locked input is missing: {relative}")
        got = sha256_file(path)
        if got != want:
            raise ReviewBundleError(
                f"locked input {relative} has SHA-256 {got}, expected {want}"
            )
        observed[str(relative)] = got
    return observed


def export_bundle(repo_root: Path, output: Path) -> dict[str, Any]:
    verify_locked_inputs(repo_root)

    generator_path = Path(__file__).resolve()
    generator_sha256 = sha256_file(generator_path)

    selection = load_json_strict(repo_root / SELECTION_PATH)
    aggregate = load_json_strict(repo_root / AGGREGATE_PATH)
    assert_all_finite(selection, where="selection")
    assert_all_finite(aggregate, where="aggregate")

    if input_set_sha256(aggregate["inputs"]) != LOCKED_AGGREGATE_INPUT_SET_SHA256:
        raise ReviewBundleError("aggregate input inventory digest does not match")
    if input_set_sha256(selection["inputs"]) != selection["input_set_sha256"]:
        raise ReviewBundleError("selection input inventory digest does not match")

    writer = BundleWriter(output)
    selection_index = export_selection(writer, selection)
    aggregate_index = export_aggregate(writer, aggregate)

    generated = collect_generated_artifacts(repo_root)
    claims = build_locked_claims(selection, aggregate, generated)
    writer.emit_json(
        "locked_claims.json", claims, semantic_source="recomputed from locked evidence"
    )

    pdf_path = repo_root / PDF_PATH
    pdf_pages = pdf_page_count(pdf_path)
    pdf_bytes = pdf_path.stat().st_size

    writer.emit(
        "README.md",
        build_readme(
            generator_sha256=generator_sha256,
            selection=selection,
            aggregate=aggregate,
            pdf_pages=pdf_pages,
            pdf_bytes=pdf_bytes,
            coverage_cell_count=len(claims["coverage"]["cells"]),
        ),
        record_count=1,
        semantic_source="generator template",
    )

    inventory = sorted(writer.entries, key=lambda item: item["path"])
    bundle_digest = sha256_bytes(
        canonical_json(
            [
                {
                    "path": item["path"],
                    "sha256": item["sha256"],
                    "bytes": item["bytes"],
                    "record_count": item["record_count"],
                }
                for item in inventory
            ]
        ).encode("ascii")
    )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generation_format": GENERATION_FORMAT,
        "repository": REPOSITORY,
        "source_branch": SOURCE_BRANCH,
        "review_base_commit": REVIEW_BASE_COMMIT,
        "implementation_commit": IMPLEMENTATION_COMMIT,
        "source_head": SOURCE_HEAD,
        "generator": {
            "path": "tools/export_transport_github_review_bundle.py",
            "sha256": generator_sha256,
        },
        "locked_inputs": {
            "selection": {
                "path": str(SELECTION_PATH),
                "sha256": LOCKED_SELECTION_SHA256,
                "input_set_sha256": selection["input_set_sha256"],
                "input_count": len(selection["inputs"]),
            },
            "selection_flat_copy": {
                "path": str(SELECTION_FLAT_PATH),
                "sha256": LOCKED_SELECTION_SHA256,
            },
            "aggregate": {
                "path": str(AGGREGATE_PATH),
                "sha256": LOCKED_AGGREGATE_SHA256,
                "input_set_sha256": LOCKED_AGGREGATE_INPUT_SET_SHA256,
                "input_count": len(aggregate["inputs"]),
            },
            "pdf": {
                "path": str(PDF_PATH),
                "sha256": LOCKED_PDF_SHA256,
                "bytes": pdf_bytes,
                "pages": pdf_pages,
            },
        },
        "generated_artifacts": generated,
        "outputs": inventory,
        "output_count": len(inventory),
        "output_total_bytes": sum(item["bytes"] for item in inventory),
        "max_output_bytes": max(item["bytes"] for item in inventory),
        "max_part_bytes_ceiling": MAX_PART_BYTES,
        "bundle_inventory_digest": bundle_digest,
        "indexes": {
            "selection": selection_index["record_totals"],
            "aggregate": aggregate_index["record_totals"],
        },
        "limitations": {
            "raw_results_tree_committed": False,
            "raw_input_bytes_verified": False,
            "selection_raw_input_count_unverified": len(selection["inputs"]),
            "aggregate_raw_input_count_unverified": sum(
                1 for item in aggregate["inputs"] if item["path"].startswith("results/raw/")
            ),
            "paired_bootstrap_recomputable_from_committed_aggregate": False,
            "paired_bootstrap_blocker": (
                "per-seed values required for resampling are not present in the "
                "committed aggregate"
            ),
            "full_provenance_validation_possible": False,
            "full_provenance_blocker": (
                "experiments.artifact_utils.validate_aggregate_provenance_sidecar "
                "requires every declared input file to exist on disk"
            ),
            "float64_diagnostics_are_verified_certificates": False,
            "pdf_byte_identical_rebuild_verified": False,
            "structural_pass_is_not_full_provenance": True,
            "known_study_source_divergences": {
                path: dict(record)
                for path, record in KNOWN_STUDY_SOURCE_DIVERGENCES.items()
            },
        },
    }
    writer._atomic_write(
        output / "manifest.json",
        (json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(
            "utf-8"
        ),
    )
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("review/transport_instantiation"),
        help="directory to write the review bundle into",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository root containing the locked evidence",
    )
    args = parser.parse_args(argv)
    try:
        manifest = export_bundle(args.repo_root.resolve(), args.output)
    except ReviewBundleError as error:
        print(f"export failed: {error}", file=sys.stderr)
        return 1
    print(
        f"wrote {manifest['output_count']} files "
        f"({manifest['output_total_bytes']} bytes, "
        f"largest {manifest['max_output_bytes']}) to {args.output}"
    )
    print(f"bundle_inventory_digest {manifest['bundle_inventory_digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
