#!/usr/bin/env python3
"""Reproduce the CODE@MIT post-review descriptive calculations.

Scientific inputs are read from Git objects at REVIEWED.  The script does not
import experiment code, execute an experiment, or read scientific inputs from
the mutable worktree.  It writes one deterministic JSON file next to itself.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from decimal import Decimal, ROUND_HALF_UP, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any


REVIEWED = "5718995cae80f34b5b98b464f3d9090758be4871"
LOCKED_AGGREGATE_SHA256 = (
    "0ddebd4915dd2e264e24b7b25047d24f86c3cdf63930a1e6df77585e0b97de02"
)
REVIEW_ROOT = "review/transport_instantiation"
INDEX_PATH = f"{REVIEW_ROOT}/aggregate/index.json"
AGGREGATE_PATH = "results/derived/transport_instantiation/full_aggregate.json"
CONFIG_PATH = "experiments/configs/transport_instantiation.yaml"
TARGETS = (0.25, 0.5, 1.0, 2.0)
PRIMARY_HORIZON = 1000


class VerificationError(RuntimeError):
    """Raised when a pinned input does not satisfy its provenance contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def run_git(repo: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise VerificationError(
            f"git {' '.join(arguments)} failed with {completed.returncode}: {detail}"
        )
    return completed.stdout


def git_show(repo: Path, path: str) -> bytes:
    return run_git(repo, "show", f"{REVIEWED}:{path}")


def git_blob(repo: Path, path: str) -> str:
    return run_git(repo, "rev-parse", f"{REVIEWED}:{path}").decode().strip()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_git_object(repo: Path, path: str) -> tuple[str, int]:
    """Hash a large pinned Git object without loading it all into memory."""

    process = subprocess.Popen(
        ["git", "-C", str(repo), "show", f"{REVIEWED}:{path}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    require(process.stdout is not None, "git show stdout pipe was not created")
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = process.stdout.read(1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
        size += len(chunk)
    stderr = process.stderr.read() if process.stderr is not None else b""
    returncode = process.wait()
    if returncode:
        detail = stderr.decode("utf-8", errors="replace").strip()
        raise VerificationError(
            f"git show {REVIEWED}:{path} failed with {returncode}: {detail}"
        )
    return digest.hexdigest(), size


def fixed(value: float, places: int) -> str:
    quantum = Decimal(1).scaleb(-places)
    return format(
        Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP),
        f".{places}f",
    )


def target_key(value: float) -> str:
    return format(value, "g")


def fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def decimal_text(value: Fraction, precision: int = 50) -> str:
    with localcontext() as context:
        context.prec = precision
        return format(Decimal(value.numerator) / Decimal(value.denominator), "f")


def scientific_text(value: Fraction, decimal_places: int) -> str:
    with localcontext() as context:
        context.prec = 50
        decimal_value = Decimal(value.numerator) / Decimal(value.denominator)
        return format(decimal_value, f".{decimal_places}E").replace("E", "e")


def json_lines(data: bytes, path: str) -> list[tuple[int, dict[str, Any]]]:
    records: list[tuple[int, dict[str, Any]]] = []
    for line_number, raw_line in enumerate(data.decode("utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        value = json.loads(raw_line)
        require(isinstance(value, dict), f"{path}:{line_number} is not a JSON object")
        records.append((line_number, value))
    return records


def source_record(
    repo: Path,
    path: str,
    data: bytes,
    *,
    indexed: dict[str, Any] | None,
    record_count: int | None = None,
) -> dict[str, Any]:
    actual_sha256 = sha256(data)
    result: dict[str, Any] = {
        "path": path,
        "reviewed_revision": REVIEWED,
        "git_blob_oid": git_blob(repo, path),
        "sha256": actual_sha256,
        "bytes": len(data),
    }
    if indexed is not None:
        require(
            indexed["sha256"] == actual_sha256,
            f"SHA-256 mismatch for indexed extract {path}",
        )
        require(indexed["bytes"] == len(data), f"byte-count mismatch for {path}")
        if record_count is not None:
            require(
                indexed["record_count"] == record_count,
                f"record-count mismatch for {path}",
            )
        result["index_entry"] = {
            "path": indexed["path"],
            "sha256": indexed["sha256"],
            "bytes": indexed["bytes"],
            "record_count": indexed["record_count"],
            "semantic_source": indexed["semantic_source"],
        }
        result["index_validation"] = {
            "sha256_matches": True,
            "bytes_match": True,
            "record_count_matches": record_count is None
            or indexed["record_count"] == record_count,
        }
    return result


def main() -> None:
    script_path = Path(__file__).resolve()
    repo = Path(
        run_git(script_path.parent, "rev-parse", "--show-toplevel").decode().strip()
    )
    resolved_reviewed = run_git(repo, "rev-parse", f"{REVIEWED}^{{commit}}").decode().strip()
    require(resolved_reviewed == REVIEWED, "REVIEWED did not resolve to the pinned commit")

    index_bytes = git_show(repo, INDEX_PATH)
    index = json.loads(index_bytes)
    require(isinstance(index, dict), "aggregate index is not a JSON object")
    require(index.get("schema_version") == 1, "unsupported aggregate index schema")
    require(isinstance(index.get("files"), list), "aggregate index files is not a list")
    index_entries = {entry["path"]: entry for entry in index["files"]}
    require(
        len(index_entries) == len(index["files"]),
        "aggregate index contains duplicate paths",
    )
    require(index.get("source_json") == AGGREGATE_PATH, "unexpected aggregate source path")
    require(
        index.get("source_sha256") == LOCKED_AGGREGATE_SHA256,
        "aggregate index is not bound to the expected locked aggregate",
    )

    index_source = source_record(repo, INDEX_PATH, index_bytes, indexed=None)
    aggregate_sha256, aggregate_bytes = hash_git_object(repo, AGGREGATE_PATH)
    require(
        aggregate_sha256 == LOCKED_AGGREGATE_SHA256,
        "pinned aggregate bytes do not match the locked SHA-256",
    )

    consumed_sources: dict[str, dict[str, Any]] = {}

    def load_extract(path: str, kind: str) -> Any:
        index_key = path.removeprefix(f"{REVIEW_ROOT}/")
        require(index_key in index_entries, f"extract absent from index: {path}")
        data = git_show(repo, path)
        if kind == "jsonl":
            parsed = json_lines(data, path)
            count = len(parsed)
        elif kind == "json":
            parsed = json.loads(data)
            count = 1
        else:
            raise VerificationError(f"unsupported extract kind: {kind}")
        consumed_sources[path] = source_record(
            repo,
            path,
            data,
            indexed=index_entries[index_key],
            record_count=count,
        )
        return parsed

    top_level_path = f"{REVIEW_ROOT}/aggregate/top_level.json"
    top_level = load_extract(top_level_path, "json")
    require(top_level.get("source_sha256") == LOCKED_AGGREGATE_SHA256, "top-level binding mismatch")
    require(top_level.get("profile") == "full", "top-level extract is not the full profile")
    require(top_level.get("full_grid_complete") is True, "top-level grid is incomplete")
    require(top_level.get("horizons") == [250, 500, 1000], "unexpected horizons")
    require(top_level.get("target_D") == list(TARGETS), "unexpected target_D grid")

    decomposition_paths = (
        f"{REVIEW_ROOT}/aggregate/bound_decomposition.part-000.jsonl",
        f"{REVIEW_ROOT}/aggregate/bound_decomposition.part-001.jsonl",
    )
    decomposition_rows: list[tuple[str, int, dict[str, Any]]] = []
    for path in decomposition_paths:
        for line_number, record in load_extract(path, "jsonl"):
            if record.get("horizon") == PRIMARY_HORIZON and record.get("round") == PRIMARY_HORIZON:
                decomposition_rows.append((path, line_number, record))
    require(len(decomposition_rows) == 4, "expected four terminal decomposition means")
    require(
        {record["target_D"] for _, _, record in decomposition_rows} == set(TARGETS),
        "terminal decomposition target grid mismatch",
    )
    expected_decomposition_lines = {
        0.25: (decomposition_paths[0], 1000),
        0.5: (decomposition_paths[0], 2000),
        1.0: (decomposition_paths[1], 608),
        2.0: (decomposition_paths[1], 1608),
    }

    decomposition: dict[str, Any] = {}
    for path, line_number, record in sorted(
        decomposition_rows, key=lambda item: item[2]["target_D"]
    ):
        target = record["target_D"]
        require(
            (path, line_number) == expected_decomposition_lines[target],
            f"unexpected terminal decomposition selector for D={target}",
        )
        sharp_rhs = record["sharp_theorem_rhs"]
        statistical = record["statistical_bound_component"]
        historical = record["historical_bound_component"]
        path_increment = record["path_inflation_component"]
        current_bias = record["current_bias_cumulative"]
        mean_regret = record["cumulative_pseudo_regret"]
        component_sum = statistical + historical + path_increment + current_bias
        closure_residual = sharp_rhs - component_sum
        require(
            math.isclose(sharp_rhs, component_sum, rel_tol=1e-15, abs_tol=1e-9),
            f"decomposition does not close for D={target}",
        )
        mean_b0 = sharp_rhs - path_increment
        mean_b0_from_components = statistical + historical + current_bias
        b0_residual = mean_b0 - mean_b0_from_components
        require(
            math.isclose(mean_b0, mean_b0_from_components, rel_tol=1e-15, abs_tol=1e-9),
            f"B0 component calculation does not close for D={target}",
        )
        cap = 2 * record["horizon"]
        uplift_percent = 100.0 * (sharp_rhs / mean_b0 - 1.0)
        share_percent = 100.0 * path_increment / sharp_rhs
        b0_over_cap = mean_b0 / cap
        b0_over_mean_regret = mean_b0 / mean_regret
        decomposition[target_key(target)] = {
            "stable_id": f"decomposition_t1000_D{target_key(target).replace('.', 'p')}",
            "source_selector": {
                "path": path,
                "line": line_number,
                "predicate": "horizon == round == 1000 and target_D matches",
            },
            "aggregation": (
                "Stored fields are means over 50 primary-policy trajectories after "
                "per-trajectory nonlinear bound evaluation; derived ratios are ratios "
                "of those means."
            ),
            "units": {
                "bound_and_regret": "cumulative pseudo-regret units",
                "ratios": "dimensionless",
                "percentages": "percent",
            },
            "inputs": {
                "mean_BD_sharp_theorem_rhs": sharp_rhs,
                "mean_statistical_component": statistical,
                "mean_historical_component": historical,
                "mean_path_increment": path_increment,
                "mean_current_bias_component": current_bias,
                "mean_cumulative_pseudo_regret": mean_regret,
                "trajectory_count": 50,
                "deterministic_2T_cap": cap,
            },
            "derived": {
                "mean_B0": mean_b0,
                "path_uplift_percent_of_B0": uplift_percent,
                "path_component_share_percent_of_BD": share_percent,
                "B0_over_2T_cap": b0_over_cap,
                "B0_over_mean_regret": b0_over_mean_regret,
            },
            "checks": {
                "component_sum": component_sum,
                "component_closure_residual": closure_residual,
                "B0_from_nonpath_components": mean_b0_from_components,
                "B0_closure_residual": b0_residual,
                "component_closure_pass": True,
                "B0_closure_pass": True,
            },
            "display": {
                "mean_BD_2dp": fixed(sharp_rhs, 2),
                "mean_path_increment_2dp": fixed(path_increment, 2),
                "mean_B0_2dp": fixed(mean_b0, 2),
                "path_uplift_percent_2dp": fixed(uplift_percent, 2),
                "path_component_share_percent_2dp": fixed(share_percent, 2),
                "B0_over_2T_cap_4dp": fixed(b0_over_cap, 4),
                "B0_over_mean_regret_4dp": fixed(b0_over_mean_regret, 4),
            },
            "packet_refs": [
                "inputs/packet_01_received.md:352-395",
                "inputs/packet_02_received.md:25-100",
                "inputs/packet_02_received.md:201-215",
            ],
        }

    policy_path = f"{REVIEW_ROOT}/aggregate/policy_outcomes.jsonl"
    policy_rows = load_extract(policy_path, "jsonl")
    policy_by_key: dict[tuple[int, float, str], tuple[int, dict[str, Any]]] = {}
    for line_number, record in policy_rows:
        key = (record["horizon"], record["target_D"], record["method"])
        require(key not in policy_by_key, f"duplicate policy outcome {key}")
        policy_by_key[key] = (line_number, record)

    retained_regret_means: dict[str, Any] = {}
    retained_methods = (
        "transport_hessian",
        "transport_endpoint",
        "frozen_reference",
        "naive_current",
    )
    for target in TARGETS:
        target_rows: dict[str, Any] = {}
        for method in retained_methods:
            line_number, record = policy_by_key[(PRIMARY_HORIZON, target, method)]
            summary = record["cumulative_pseudo_regret"]
            require(summary["n"] == 50, f"retained regret n mismatch for {target}/{method}")
            target_rows[method] = {
                "source_selector": {
                    "path": policy_path,
                    "line": line_number,
                    "predicate": (
                        f"horizon == 1000, target_D == {target_key(target)}, "
                        f"method == {method}"
                    ),
                    "field": "cumulative_pseudo_regret.mean",
                },
                "aggregation": (
                    "Terminal cumulative pseudo-regret per trajectory, then arithmetic "
                    "mean across 50 evaluation seeds within condition."
                ),
                "units": "cumulative pseudo-regret",
                "unrounded_value": summary["mean"],
                "display_2dp": fixed(summary["mean"], 2),
                "verification_pass": True,
            }
        retained_regret_means[target_key(target)] = target_rows

    expected_policy_lines = {
        0.25: (1, 4),
        0.5: (5, 8),
        1.0: (9, 12),
        2.0: (13, 16),
    }
    paired_results: dict[str, Any] = {}
    for target in TARGETS:
        h_line, hessian = policy_by_key[(PRIMARY_HORIZON, target, "transport_hessian")]
        n_line, naive = policy_by_key[(PRIMARY_HORIZON, target, "naive_current")]
        require((h_line, n_line) == expected_policy_lines[target], f"policy selector mismatch for D={target}")
        h_summary = hessian["cumulative_pseudo_regret"]
        n_summary = naive["cumulative_pseudo_regret"]
        paired = naive["paired_difference_from_transport_hessian"]
        n = paired["n"]
        require(n == h_summary["n"] == n_summary["n"] == 50, f"paired n mismatch for D={target}")
        stored_interval = paired["bootstrap_mean_interval"]
        require(
            stored_interval["ci"] == [stored_interval["ci_low"], stored_interval["ci_high"]],
            f"stored interval representation mismatch for D={target}",
        )
        delta = -paired["mean"]
        mean_difference = h_summary["mean"] - n_summary["mean"]
        require(
            math.isclose(delta, mean_difference, rel_tol=1e-14, abs_tol=1e-12),
            f"stored paired mean disagrees with marginal means for D={target}",
        )
        sd = paired["standard_deviation"]
        stored_se = paired["standard_error"]
        computed_se = sd / math.sqrt(n)
        se_error = stored_se - computed_se
        se_pass = math.isclose(stored_se, computed_se, rel_tol=1e-15, abs_tol=1e-15)
        require(se_pass, f"paired SE check failed for D={target}")
        reversed_interval = [-stored_interval["ci_high"], -stored_interval["ci_low"]]
        relative_excess = 100.0 * delta / n_summary["mean"]
        paired_results[target_key(target)] = {
            "stable_id": f"paired_hessian_minus_naive_t1000_D{target_key(target).replace('.', 'p')}",
            "source_selector": {
                "path": policy_path,
                "hessian_line": h_line,
                "naive_line": n_line,
                "predicate": (
                    "horizon == 1000, target_D matches, methods are "
                    "transport_hessian and naive_current"
                ),
            },
            "aggregation": (
                "Fifty matched evaluation seeds within condition. The stored paired "
                "field is naive minus Hessian; sign reversal reports Hessian minus naive."
            ),
            "units": {
                "means_sd_se_interval": "cumulative pseudo-regret units",
                "relative_excess": "percent, ratio of means",
            },
            "inputs": {
                "n": n,
                "hessian_mean": h_summary["mean"],
                "naive_mean": n_summary["mean"],
                "stored_naive_minus_hessian_mean": paired["mean"],
                "stored_paired_standard_deviation": sd,
                "stored_paired_standard_error": stored_se,
                "stored_naive_minus_hessian_bootstrap_interval": [
                    stored_interval["ci_low"],
                    stored_interval["ci_high"],
                ],
                "bootstrap_level": stored_interval["level"],
                "bootstrap_method": stored_interval["method"],
                "bootstrap_resamples": stored_interval["resamples"],
            },
            "derived": {
                "hessian_minus_naive_mean": delta,
                "paired_standard_deviation": sd,
                "paired_standard_error": stored_se,
                "hessian_minus_naive_bootstrap_interval": reversed_interval,
                "relative_regret_excess_percent": relative_excess,
            },
            "checks": {
                "marginal_mean_difference": mean_difference,
                "paired_mean_matches_marginal_difference": True,
                "standard_error_from_sd_over_sqrt_n": computed_se,
                "stored_minus_computed_standard_error": se_error,
                "standard_error_check_pass": se_pass,
            },
            "display": {
                "hessian_mean_2dp": fixed(h_summary["mean"], 2),
                "naive_mean_2dp": fixed(n_summary["mean"], 2),
                "hessian_minus_naive_mean_2dp": fixed(delta, 2),
                "hessian_minus_naive_mean_6dp": fixed(delta, 6),
                "paired_standard_deviation_6dp": fixed(sd, 6),
                "paired_standard_error_2dp": fixed(stored_se, 2),
                "paired_standard_error_6dp": fixed(stored_se, 6),
                "hessian_minus_naive_interval_6dp": [
                    fixed(reversed_interval[0], 6),
                    fixed(reversed_interval[1], 6),
                ],
                "relative_regret_excess_percent_2dp": fixed(relative_excess, 2),
            },
            "packet_refs": [
                "inputs/packet_02_received.md:142-187",
                "inputs/packet_02_received.md:216-220",
            ],
        }

    tightness_path = f"{REVIEW_ROOT}/aggregate/certificate_tightness.jsonl"
    tightness_rows = load_extract(tightness_path, "jsonl")
    pooled_inflation: dict[str, Any] = {}
    retained_path_ratios: dict[str, Any] = {}
    expected_tightness_lines = {0.25: 9, 0.5: 10, 1.0: 11, 2.0: 12}
    selected_tightness = [
        (line_number, record)
        for line_number, record in tightness_rows
        if record.get("horizon") == PRIMARY_HORIZON
    ]
    require(len(selected_tightness) == 4, "expected four primary-horizon tightness records")
    for line_number, record in sorted(selected_tightness, key=lambda item: item[1]["target_D"]):
        target = record["target_D"]
        require(line_number == expected_tightness_lines[target], f"tightness selector mismatch for D={target}")
        summary = record["exp_D_Q_over_2"]
        require(summary["n"] == 50_000, f"pooled inflation n mismatch for D={target}")
        path_summary = record["D_Q_over_D_path_quad"]
        require(path_summary["n"] == 5_000, f"path-ratio n mismatch for D={target}")
        retained_path_ratios[target_key(target)] = {
            "source_selector": {
                "path": tightness_path,
                "line": line_number,
                "predicate": "horizon == 1000 and target_D matches",
                "field": "D_Q_over_D_path_quad.median",
            },
            "aggregation": (
                "Median after pooling 5,000 eligible primary-policy seed-checkpoint "
                "ratios with D_path_quad > 1e-12 within condition."
            ),
            "units": "dimensionless ratio",
            "unrounded_value": path_summary["median"],
            "display_3_significant": format(path_summary["median"], ".3g"),
            "verification_pass": True,
        }
        pooled_inflation[target_key(target)] = {
            "stable_id": f"pooled_inflation_t1000_D{target_key(target).replace('.', 'p')}",
            "source_selector": {
                "path": tightness_path,
                "line": line_number,
                "predicate": "horizon == 1000 and target_D matches",
                "field": "exp_D_Q_over_2",
            },
            "aggregation": (
                "Median pooled over 50 primary-policy seeds and all 1000 rounds "
                "(50,000 seed-round values); not a terminal or run-maximum summary."
            ),
            "units": "dimensionless multiplicative inflation",
            "inputs": {
                "n": summary["n"],
                "median": summary["median"],
            },
            "display": {"median_2dp": fixed(summary["median"], 2)},
            "packet_refs": [
                "inputs/packet_02_received.md:102-140",
                "inputs/packet_02_received.md:221-224",
            ],
        }

    validity_path = f"{REVIEW_ROOT}/aggregate/validity.jsonl"
    validity_rows = load_extract(validity_path, "jsonl")
    retained_endpoint_medians: dict[str, Any] = {}
    expected_validity_lines = {0.25: 9, 0.5: 10, 1.0: 11, 2.0: 12}
    selected_validity = [
        (line_number, record)
        for line_number, record in validity_rows
        if record.get("horizon") == PRIMARY_HORIZON
    ]
    require(len(selected_validity) == 4, "expected four primary-horizon validity records")
    for line_number, record in sorted(selected_validity, key=lambda item: item[1]["target_D"]):
        target = record["target_D"]
        require(line_number == expected_validity_lines[target], f"validity selector mismatch for D={target}")
        summary = record["max_endpoint_Thompson_distance"]
        require(summary["n"] == 50, f"endpoint run-max n mismatch for D={target}")
        retained_endpoint_medians[target_key(target)] = {
            "source_selector": {
                "path": validity_path,
                "line": line_number,
                "predicate": "horizon == 1000 and target_D matches",
                "field": "max_endpoint_Thompson_distance.median",
            },
            "aggregation": (
                "Maximum endpoint Thompson distance across 1,000 rounds per primary "
                "trajectory, then median across 50 evaluation seeds."
            ),
            "units": "dimensionless Thompson distance",
            "unrounded_value": summary["median"],
            "display_3_significant": format(summary["median"], ".3g"),
            "verification_pass": True,
        }

    config_bytes = git_show(repo, CONFIG_PATH)
    config = json.loads(config_bytes)
    config_source = source_record(repo, CONFIG_PATH, config_bytes, indexed=None)
    base = config["base"]
    require(base["horizons"] == [250, 500, 1000], "config horizon grid mismatch")
    require(base["target_D"] == list(TARGETS), "config target_D grid mismatch")
    require(base["model"]["family"] == "scaled_tanh", "unexpected model family")
    require(
        base["model"]["smoothness_constant"]
        == "4 * feature_bound^2 / (3 * sqrt(3))",
        "unexpected smoothness formula",
    )
    require(
        base["model"]["W_rule"]
        == "(4 * c_h * theta_radius * sqrt(horizon - 1) / (noise_std * sqrt(ridge) * target_D))^2",
        "unexpected W rule",
    )
    feature_bound = Fraction(str(base["environment"]["feature_bound"]))
    theta_radius = Fraction(str(base["teacher"]["theta_radius"]))
    noise_std = Fraction(str(base["environment"]["noise_std"]))
    ridge = Fraction(str(base["ridge"]))
    # Square the configured W rule and c_h expression symbolically so all
    # design-rule values remain exact rationals.
    w_coefficient = (
        Fraction(256, 27)
        * feature_bound**4
        * theta_radius**2
        * (PRIMARY_HORIZON - 1)
        / (noise_std**2 * ridge)
    )
    require(w_coefficient == 151_552, "unexpected T=1000 W coefficient")
    near_linearity: dict[str, Any] = {}
    for target in TARGETS:
        target_fraction = Fraction(str(target))
        w = w_coefficient / target_fraction**2
        relative_error_bound = Fraction(1, 1) / (3 * w)
        require(w.denominator == 1, f"expected integral W for D={target}")
        near_linearity[target_key(target)] = {
            "stable_id": f"near_linearity_t1000_D{target_key(target).replace('.', 'p')}",
            "inputs": {
                "target_D_exact": fraction_text(target_fraction),
                "horizon": PRIMARY_HORIZON,
                "feature_bound_exact": fraction_text(feature_bound),
                "theta_radius_exact": fraction_text(theta_radius),
                "noise_std_exact": fraction_text(noise_std),
                "ridge_exact": fraction_text(ridge),
            },
            "derived": {
                "W_exact_fraction": fraction_text(w),
                "W": w.numerator,
                "one_over_3W_exact_fraction": fraction_text(relative_error_bound),
                "one_over_3W_decimal_50_digit_context": decimal_text(relative_error_bound),
                "one_over_3W_float64": float(relative_error_bound),
            },
            "display": {
                "W_grouped": f"{w.numerator:,}",
                "one_over_3W_11_significant_scientific": scientific_text(
                    relative_error_bound, 10
                ),
                "one_over_3W_4_significant_scientific": scientific_text(
                    relative_error_bound, 3
                ),
            },
            "units": {
                "W": "dimensionless scaled-tanh smoothness parameter",
                "one_over_3W": "dimensionless uniform relative-error upper bound for |u| <= 1",
            },
            "aggregation": "Analytic design-rule calculation; not an empirical statistic.",
            "packet_refs": ["inputs/packet_01_received.md:189-226"],
        }

    packet_specs = {
        "packet_01": {
            "path": "submissions/code_mit_2026/author_review/postreview_20260910/inputs/packet_01_received.md",
            "sections": [
                "near-linearity: lines 189-226",
                "bound-attribution interpretation: lines 352-395",
            ],
        },
        "packet_02": {
            "path": "submissions/code_mit_2026/author_review/postreview_20260910/inputs/packet_02_received.md",
            "sections": [
                "decomposition: lines 25-100",
                "paired comparison: lines 142-187",
                "provenance ledger: lines 201-224",
            ],
        },
    }
    packet_sources: dict[str, Any] = {}
    for packet_id, specification in packet_specs.items():
        packet_path = repo / specification["path"]
        packet_bytes = packet_path.read_bytes()
        packet_sources[packet_id] = {
            **specification,
            "sha256": sha256(packet_bytes),
            "bytes": len(packet_bytes),
            "git_blob_oid": None,
            "binding": "Workspace review input; not present at REVIEWED.",
        }

    output = {
        "schema_version": 1,
        "artifact": "CODE@MIT 2026 post-review calculations",
        "reviewed_revision": REVIEWED,
        "calculation_scope": (
            "Post-review descriptive analysis of the locked evaluation; no experiment "
            "execution, bootstrap replay, or raw-trajectory reconstruction."
        ),
        "provenance": {
            "scientific_read_policy": (
                "All scientific inputs were read from Git objects using REVIEWED:path, "
                "not from mutable worktree files."
            ),
            "index": {
                **index_source,
                "schema_version": index["schema_version"],
                "input_set_sha256": index["input_set_sha256"],
                "source_json": index["source_json"],
                "source_sha256": index["source_sha256"],
                "aggregate_binding_verified": True,
            },
            "locked_aggregate": {
                "path": AGGREGATE_PATH,
                "reviewed_revision": REVIEWED,
                "git_blob_oid": git_blob(repo, AGGREGATE_PATH),
                "sha256": aggregate_sha256,
                "bytes": aggregate_bytes,
                "matches_expected_sha256": True,
                "matches_index_source_sha256": True,
            },
            "consumed_indexed_extracts": consumed_sources,
            "config_source": {
                **config_source,
                "selectors": [
                    "/base/horizons",
                    "/base/target_D",
                    "/base/environment/feature_bound",
                    "/base/environment/noise_std",
                    "/base/teacher/theta_radius",
                    "/base/model/smoothness_constant",
                    "/base/model/W_rule",
                    "/base/ridge",
                ],
                "reported_resolved_config_digest": top_level["config_digest"],
            },
            "review_packet_sources": packet_sources,
            "validation_summary": {
                "reviewed_commit_resolved_exactly": True,
                "index_schema_inspected": True,
                "indexed_extract_digests_validated": len(consumed_sources),
                "all_indexed_extract_digests_match": True,
                "locked_aggregate_bytes_hashed": True,
                "index_and_top_level_bind_to_locked_aggregate": True,
            },
        },
        "calculations": {
            "retained_manuscript_table": {
                "stable_id": "retained_manuscript_table_t1000",
                "regret_means": retained_regret_means,
                "path_ratio_medians": retained_path_ratios,
                "endpoint_run_max_medians": retained_endpoint_medians,
                "pooled_inflation_medians": pooled_inflation,
                "packet_refs": [
                    "inputs/packet_01_received.md:296-313",
                    "inputs/packet_02_received.md:6-19",
                ],
            },
            "terminal_mean_decomposition": {
                "stable_id": "terminal_mean_decomposition_t1000",
                "by_target_D": decomposition,
            },
            "paired_hessian_minus_naive": {
                "stable_id": "paired_hessian_minus_naive_t1000",
                "by_target_D": paired_results,
            },
            "pooled_seed_round_inflation": {
                "stable_id": "pooled_seed_round_inflation_t1000",
                "by_target_D": pooled_inflation,
            },
            "analytic_near_linearity": {
                "stable_id": "analytic_near_linearity_t1000",
                "formula": {
                    "configured_c_h": "4 * feature_bound^2 / (3 * sqrt(3))",
                    "configured_W_rule": base["model"]["W_rule"],
                    "squared_exact_rule": (
                        "W = 256 * feature_bound^4 * theta_radius^2 * (horizon - 1) "
                        "/ (27 * noise_std^2 * ridge * target_D^2)"
                    ),
                    "T1000_simplification": "W = 151552 / target_D^2",
                    "relative_error_bound": "1 / (3 * W)",
                },
                "by_target_D": near_linearity,
            },
        },
        "interpretation_limits": [
            "B0 is a same-trajectory algebraic attribution, not a baseline-policy rerun or a guarantee for a policy executed without transport.",
            "Decomposition percentages and relative regret percentages are ratios of stored means, not means of per-trajectory ratios.",
            "Paired intervals are sign-reversed stored comparisonwise intervals; the bootstrap was not replayed.",
            "Pooled inflation medians combine seed-round values and are not terminal or run-maximum summaries.",
            "Near-linearity bounds are analytic consequences of the configured design rule, not empirical estimates or floating-point exactness claims.",
        ],
    }

    output_path = script_path.with_name("calculations.json")
    output_path.write_text(
        json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(output_path)


if __name__ == "__main__":
    main()
