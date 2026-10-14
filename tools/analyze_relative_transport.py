#!/usr/bin/env python3
"""Exploratory endpoint-certificate audit of fixed recorded study histories.

Replays only the original representation update with logged actions/rewards;
never selects a new behavior action or generates a reward. Ordinary float64
checks are diagnostics, not verified enclosures or new adaptive experiments.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import platform
import sys
import time

import numpy as np
import scipy

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY))
from experiments import transport_instantiation as scientific

ORIGINAL = {
    "transport_hessian": "hessian_transport_scores",
    "transport_endpoint": "endpoint_transport_scores",
    "frozen_reference": "frozen_reference_scores",
    "naive_current": "naive_current_scores",
}
NEW = ("uniform_endpoint", "category_symmetric", "category_asymmetric")
METHODS = tuple(ORIGINAL) + NEW
CHECKPOINTS = (1, 2, 10, 100, 500, 1000)
TOLERANCE = scientific.NumericalTolerance()
REQUIRED = {"manifest.jsonl", "raw.jsonl", "summary.json", "summary.json.sha256"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def describe(values):
    x = np.asarray(values, dtype=np.float64)
    require(x.size > 0 and np.all(np.isfinite(x)), "Nonfinite/empty diagnostic values")
    return {"count": int(x.size), "min": float(np.min(x)), "mean": float(np.mean(x)),
            "p10": float(np.quantile(x, .1)), "median": float(np.median(x)),
            "p90": float(np.quantile(x, .9)), "max": float(np.max(x))}


def category_factors(counts, frozen_weights, current_scales):
    """Pre-action category comparison, with ridge ratio 1 included."""
    observed = counts > 0
    if not np.any(observed):
        return 1.0, 1.0, 0.0
    require(np.all(frozen_weights[observed] > 0), "Nonpositive collection weight")
    ratios = counts[observed] * current_scales[observed] ** 2 / frozen_weights[observed]
    require(np.all(np.isfinite(ratios)) and np.all(ratios > 0), "Invalid category ratio")
    lower, upper = min(1.0, float(np.min(ratios))), max(1.0, float(np.max(ratios)))
    return lower, upper, max(-math.log(lower), math.log(upper))


def kernel_times(environment, theta, counts, weights, frozen, current, repeats):
    """Fixed-state kernels; no metric assembly in dense comparison."""
    scales = 1 - np.tanh(environment.category_features @ theta / math.sqrt(environment.width)) ** 2
    tasks = {
        "category_ratios_precomputed_scales": lambda: category_factors(counts, weights, scales),
        "category_ratios_with_80_projections": lambda: category_factors(
            counts, weights, 1 - np.tanh(environment.category_features @ theta / math.sqrt(environment.width)) ** 2),
        "dense_endpoint_preassembled_metrics": lambda: scientific.thompson_distance(frozen, current),
    }
    results = {}
    for label, task in tasks.items():
        task()
        batches = []
        for _ in range(5):
            start = time.perf_counter_ns()
            for _ in range(repeats):
                task()
            batches.append((time.perf_counter_ns() - start) / repeats / 1e9)
        results[label] = describe(batches)
    return results


def audit_one(task):
    path, config, signature, config_digest, revision, selection_hash, benchmark_seed, repeats = task
    started = time.monotonic()
    leaf = Path(path).parent
    inventory = []

    def bound_read(name):
        data = (leaf / name).read_bytes()
        inventory.append({"path": str(leaf / name), "kind": name, "bytes": len(data), "sha256": digest(data)})
        return data

    receipt = json.loads(bound_read(".review-complete.json"))
    require(receipt["signature"] == signature and set(receipt["files"]) == REQUIRED, "Receipt signature/files")
    data = {name: bound_read(name) for name in sorted(REQUIRED)}
    for name in REQUIRED:
        require(digest(data[name]) == receipt["files"][name], "Receipt hash: " + str(leaf / name))
    summary, provenance = json.loads(data["summary.json"]), json.loads(data["manifest.jsonl"])
    require(summary["config_digest"] == provenance["config_digest"] == config_digest, "Config digest mismatch")
    require(provenance["config"] == config and provenance["git_revision"] == revision, "Provenance mismatch")
    require(summary["selection_sha256"] == selection_hash, "Optimizer selection provenance")
    require(summary["phase"] == "evaluation" and summary["horizon"] == 1000 and summary["deterministic_audit_pass"], "Unexpected source trajectory")
    W, seed, behavior = summary["W"], summary["seed"], summary["method"]
    environment = scientific.ScaledTanhEnvironment(
        width=W, feature_bound=config["environment"]["feature_bound"],
        theta_radius=config["teacher"]["theta_radius"], noise_std=config["environment"]["noise_std"],
        teacher_seed=config["teacher"]["seed"])
    optimizer = scientific.OptimizerSpec.from_mapping(summary["optimizer"])
    statistics = scientific.CategorySufficientStatistics()
    phi = environment.category_features
    frozen_weights = np.zeros(len(phi))
    frozen_direct = config["ridge"] * np.eye(scientific.FEATURE_DIMENSION)
    frozen_rhs = np.zeros(scientific.FEATURE_DIMENSION)
    theta = np.zeros(scientific.FEATURE_DIMENSION)
    uniform_D = 4 * math.log(math.cosh(environment.feature_bound * environment.theta_radius / math.sqrt(W)))
    uniform_factor = math.exp(uniform_D / 2)
    counters = {name: Counter() for name in METHODS}
    regret_sums, disagreements = defaultdict(float), Counter()
    ratios, scalars = defaultdict(list), defaultdict(list)
    checks, residuals, residual_ratios = Counter(), defaultdict(float), defaultdict(float)
    benchmark = []

    def check_close(label, actual, expected):
        actual, expected = np.asarray(actual), np.asarray(expected)
        error = float(np.max(np.abs(actual - expected)))
        allowed = TOLERANCE.value(actual, expected)
        residuals[label] = max(residuals[label], error)
        residual_ratios[label] = max(residual_ratios[label], error / allowed)
        checks[label] += 1
        require(np.isfinite(error) and error <= allowed, f"{label}: error {error} > {allowed}; {leaf}")

    def check_le(label, left, right):
        left, right = np.asarray(left), np.asarray(right)
        excess = float(np.max(left - right))
        allowed = TOLERANCE.value(left, right)
        residuals[label] = max(residuals[label], max(0.0, excess))
        residual_ratios[label] = max(residual_ratios[label], max(0.0, excess) / allowed)
        checks[label] += 1
        require(np.isfinite(excess) and excess <= allowed, f"{label}: excess {excess} > {allowed}; {leaf}")

    lines = data["raw.jsonl"].splitlines()
    require(len(lines) == 1000, "Wrong number of source rounds")
    for index, line in enumerate(lines):
        record = json.loads(line)
        m = record["metrics"]
        t = index + 1
        require(record["round"] == index and m["round"] == t and record["seed"] == seed, "Round identity")
        require(m["deterministic_audit_passed"], "Failed source-round audit")
        require(statistics.observation_count == index and int(sum(statistics.counts)) == index, "Pre-action timing")
        check_close("theta_t_norm", np.linalg.norm(theta), m["theta_t_norm"])
        check_le("theta_radius", np.linalg.norm(theta), environment.theta_radius)
        projected = phi @ theta / math.sqrt(W)
        scales = 1 - np.tanh(projected) ** 2
        lower, upper, Dcat = category_factors(statistics.counts, frozen_weights, scales)
        if t == 1:
            require((lower, upper, Dcat) == (1.0, 1.0, 0.0), "Empty history factors")
        c = np.asarray(m["corrected_centers"])
        current_w, frozen_w = np.asarray(m["current_widths"]), np.asarray(m["frozen_widths"])
        require(np.all(current_w > 0) and np.all(frozen_w > 0), "Unexpected zero candidate width")
        factors = {"transport_hessian": m["exp_bar_D_over_2"],
                   "transport_endpoint": m["exp_endpoint_distance_over_2"],
                   "naive_current": 1.0, "uniform_endpoint": uniform_factor,
                   "category_symmetric": math.exp(Dcat / 2), "category_asymmetric": math.sqrt(upper)}
        effective = {name: factor * current_w for name, factor in factors.items()}
        effective["frozen_reference"] = frozen_w
        scores = {name: np.asarray(m[field]) for name, field in ORIGINAL.items()}
        for name in NEW:
            scores[name] = c + (m["beta_t_corr"] * factors[name]) * current_w + m["current_bias"]
        check_le("endpoint_le_category_D", m["d_Th"], Dcat)
        check_le("category_le_uniform_D", Dcat, uniform_D)
        check_le("category_outward_width", frozen_w, effective["category_asymmetric"])
        check_le("category_return_width", current_w, frozen_w / math.sqrt(lower))
        check_le("asymmetric_le_symmetric_width", effective["category_asymmetric"], effective["category_symmetric"])
        check_le("category_le_uniform_width", effective["category_symmetric"], effective["uniform_endpoint"])
        check_le("endpoint_outward_width", frozen_w, effective["transport_endpoint"])
        check_le("hessian_outward_width", frozen_w, effective["transport_hessian"])
        scalars["category_m"].append(lower)
        scalars["category_M"].append(upper)
        scalars["category_D"].append(Dcat)
        scalars["endpoint_D"].append(m["d_Th"])
        scalars["hessian_D"].append(m["D_Q"])
        scalars["category_D_minus_endpoint_D"].append(Dcat - m["d_Th"])
        selections = {}
        true_means = np.asarray(m["true_means"])
        for name in METHODS:
            e, score, counter = effective[name], scores[name], counters[name]
            require(np.all(np.isfinite(score)), "Nonfinite score")
            base_w = frozen_w if name == "frozen_reference" else current_w
            a, aw = int(np.argmax(score)), int(np.argmax(base_w))
            selections[name] = a
            counter["rounds"] += 1
            counter["width_argmax_first_matches"] += int(a == aw)
            counter["width_argmax_set_matches"] += int(base_w[a] == max(base_w))
            counter["width_top_tie"] += int(np.sum(base_w == max(base_w)) > 1)
            counter["score_top_tie"] += int(np.sum(score == max(score)) > 1)
            # For scalar-current policies preserve the original beta*factor
            # rounding, then multiply the width gap, as in the earlier audit.
            coefficient = m["beta_t_corr"] if name == "frozen_reference" else m["beta_t_corr"] * factors[name]
            sorted_w = np.sort(base_w)
            counter["strict_width_dominance_sufficient"] += int(coefficient * (sorted_w[-1] - sorted_w[-2]) > np.ptp(c))
            normalized = base_w + c / coefficient
            counter["normalized_float_rank_difference"] += int(a != int(np.argmax(normalized)))
            counter["all_action_optimism_float"] += int(np.all(score + TOLERANCE.value(score, true_means) >= true_means))
            regret_sums[name] += float(np.max(true_means) - true_means[a])
            ratios[name].extend((e / frozen_w).tolist())
        require(selections[behavior] == m["selected_action"] and np.array_equal(scores[behavior], m["scores"]), "Logged action/score mismatch")
        for left, right in itertools.combinations(METHODS, 2):
            disagreements[left + "__vs__" + right] += selections[left] != selections[right]
        if t in CHECKPOINTS:
            grouped = config["ridge"] * np.eye(scientific.FEATURE_DIMENSION)
            grouped += np.tensordot(frozen_weights, environment.feature_outer_products, axes=(0, 0)) / environment.noise_std ** 2
            check_close("direct_vs_category_frozen_gram", grouped, frozen_direct)
            current = statistics.current_metric(theta, environment, ridge=config["ridge"])
            queries = environment.gradient(theta, environment.features[m["context_index"]])
            check_close("logged_frozen_width", scientific.inverse_quadratic_widths(frozen_direct, queries), frozen_w)
            check_close("logged_current_width", scientific.inverse_quadratic_widths(current, queries), current_w)
            theta_hat = scientific.cholesky_solve(frozen_direct, frozen_rhs)
            centers = scientific.corrected_center(theta, theta_hat, environment.features[m["context_index"]], environment)
            check_close("logged_corrected_centers", centers, c)
            distance, eigenvalues = scientific.thompson_distance(frozen_direct, current)
            check_close("logged_endpoint_distance", distance, m["d_Th"])
            check_close("logged_endpoint_eigenvalues", eigenvalues, m["endpoint_generalized_eigenvalues"])
            check_le("spectral_lower_sandwich", lower, np.min(eigenvalues))
            check_le("spectral_upper_sandwich", np.max(eigenvalues), upper)
            # Direct PSD residual checks retain the original operator-norm scale.
            for label, matrix in (("PSD_current_minus_m_frozen", current - lower * frozen_direct),
                                  ("PSD_M_frozen_minus_current", upper * frozen_direct - current)):
                minimum = float(np.linalg.eigvalsh((matrix + matrix.T) / 2)[0])
                allowed = TOLERANCE.value(current, frozen_direct)
                checks[label] += 1
                residuals[label] = max(residuals[label], max(0.0, -minimum))
                residual_ratios[label] = max(residual_ratios[label], max(0.0, -minimum) / allowed)
                require(minimum >= -allowed, label)
            if seed == benchmark_seed and t in (100, 500, 1000):
                benchmark.append({"round": t, "kernels_seconds_per_call": kernel_times(
                    environment, theta, statistics.counts, frozen_weights, frozen_direct, current, repeats)})
        # Collection query and weight use theta_t, before adding reward_t and
        # before the original representation optimizer computes theta_{t+1}.
        category = m["context_index"] * scientific.ACTION_COUNT + m["selected_action"]
        query = environment.gradient(theta, phi[category])
        pseudo = m["selected_reward"] - environment.mean(theta, phi[category]) + query @ theta
        check_close("logged_pseudo_response", pseudo, m["pseudo_response"])
        frozen_direct += np.outer(query, query) / environment.noise_std ** 2
        frozen_rhs += query * pseudo / environment.noise_std ** 2
        frozen_weights[category] += scales[category] ** 2
        statistics.add(category, m["selected_reward"])
        theta, optimizer_diagnostics = scientific.projected_gradient_update(
            statistics, theta, environment, optimizer=optimizer,
            training_ridge=config["training_ridge"], theta_radius=environment.theta_radius)
        check_close("theta_next_norm", np.linalg.norm(theta), m["theta_next_norm"])
        check_close("optimizer_displacement", optimizer_diagnostics.displacement_norm, m["optimizer_parameter_displacement"])
        require(optimizer_diagnostics.projection_occurred == m["optimizer_projection_occurred"], "Projection mismatch")
    check_close("actual_behavior_regret", regret_sums[behavior], summary["cumulative_pseudo_regret"])
    return {
        "W": W, "target_D": summary["target_D"], "seed": seed, "behavior_method": behavior,
        "rounds": len(lines), "optimizer": summary["optimizer"], "uniform_D": uniform_D,
        "uniform_width_factor": uniform_factor, "diagnostic_counts": {k: dict(v) for k, v in counters.items()},
        "same_history_mean_one_step_regret": {k: v / len(lines) for k, v in regret_sums.items()},
        "recommendation_disagreements": dict(disagreements),
        "effective_width_over_frozen_width": {k: describe(v) for k, v in ratios.items()},
        "scalar_distributions": {k: describe(v) for k, v in scalars.items()},
        "verification_counts": dict(checks), "maximum_absolute_residual_or_excess": dict(residuals),
        "maximum_residual_or_excess_over_original_tolerance": dict(residual_ratios),
        "fixed_state_kernel_timings": benchmark, "elapsed_seconds": time.monotonic() - started,
    }, inventory


def self_test():
    """Check the coefficient/ridge algebra against literal per-sample Grams."""
    rng = np.random.default_rng(8731)
    cases = 0
    for n in (0, 1, 7, 31):
        phi = rng.normal(size=(6, 4))
        phi /= np.maximum(1, np.linalg.norm(phi, axis=1))[:, None]
        categories = rng.integers(0, len(phi), n)
        collection_scales = rng.uniform(.08, 1, n)
        current_scales = rng.uniform(.08, 1, len(phi))
        counts = np.bincount(categories, minlength=len(phi)).astype(float)
        frozen = np.bincount(categories, weights=collection_scales ** 2, minlength=len(phi))
        low, high, distance = category_factors(counts, frozen, current_scales)
        A, C = np.eye(4), np.eye(4)
        for category, scale in zip(categories, collection_scales):
            A += scale ** 2 * np.outer(phi[category], phi[category]) / .25 ** 2
            C += current_scales[category] ** 2 * np.outer(phi[category], phi[category]) / .25 ** 2
        grouped = np.eye(4) + np.einsum("c,ci,cj->ij", frozen, phi, phi) / .25 ** 2
        require(np.allclose(A, grouped, rtol=1e-13, atol=1e-13), "Literal/grouped Gram test")
        require(np.linalg.eigvalsh(C - low * A)[0] >= -1e-12, "Lower PSD test")
        require(np.linalg.eigvalsh(high * A - C)[0] >= -1e-12, "Upper PSD test")
        require(scientific.thompson_distance(A, C)[0] <= distance + 1e-12, "Endpoint test")
        if n == 0:
            require((low, high, distance) == (1.0, 1.0, 0.0), "Empty history test")
        cases += 1
    print(encode({"self_test": "passed", "literal_sample_vs_category_cases": cases}), flush=True)


def run(args):
    started = time.monotonic()
    root, output = args.raw_root.resolve(), args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    require(not (output / "per_seed.jsonl").exists(), "Refusing overwrite; use a new output directory")
    global_inventory = []

    def load_bound(path, kind):
        data = path.read_bytes()
        global_inventory.append({"path": str(path), "kind": kind, "bytes": len(data), "sha256": digest(data)})
        return data

    manifest = json.loads(load_bound(root / "run.json", "run_manifest"))
    config = json.loads(load_bound(root / "execution_config.json", "execution_config"))
    load_bound(root / "source_config.json", "source_config")
    selection = load_bound(root / "selection.json", "optimizer_selection")
    require(digest(selection) == manifest["selection_sha256"], "Selection file hash mismatch")
    require(manifest["status"] == "complete" and manifest["evaluation_complete"], "Source evaluation incomplete")
    require(sys.version == manifest["python"], "Python build differs from source run")
    require(np.__version__ == manifest["packages"]["numpy"] and scipy.__version__ == manifest["packages"]["scipy"], "Scientific dependency versions differ")
    require(all(os.environ.get(k) == "1" for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS")), "Use original single-thread worker settings")
    source = load_bound(REPOSITORY / "experiments/transport_instantiation.py", "scientific_source")
    recorded_hash = next(v["sha256"] for v in manifest["source_inputs"] if v["path"] == "experiments/transport_instantiation.py")
    require(digest(source) == recorded_hash, "Scientific source changed")
    require(config["profile"] == "full" and config["horizons"] == [1000], "Unexpected source profile")
    require(config["numerics"]["algebra_tolerance_constant"] == TOLERANCE.multiplier, "Tolerance changed")
    require(not list((root / "raw/evaluation").rglob(".review-failed.json")), "Failed source task marker")
    paths = sorted((root / "raw/evaluation").rglob("summary.json"))
    expected = set(itertools.product(config["target_D"], config["methods"], config["seed_sets"]["evaluation"]))
    actual = []
    for path in paths:
        summary = json.loads(path.read_bytes())
        actual.append((summary["target_D"], summary["method"], summary["seed"]))
    require(len(paths) == len(expected) == 600 and len(set(actual)) == 600 and set(actual) == expected, "Incomplete/duplicate grid")
    if args.max_trajectories:
        paths = paths[:args.max_trajectories]
    tasks = [(str(p), config, manifest["signature"], manifest["config_digest"], manifest["git_revision"],
              manifest["selection_sha256"], min(config["seed_sets"]["evaluation"]), args.benchmark_repeats) for p in paths]
    rows, inventory = [], list(global_inventory)
    with (output / "per_seed.jsonl").open("w") as stream:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            pending = {executor.submit(audit_one, task): task[0] for task in tasks}
            for future in as_completed(pending):
                try:
                    row, inputs = future.result()
                except Exception as error:
                    (output / "FAILURE.json").write_text(encode({"path": pending[future], "error": repr(error)}))
                    for other in pending:
                        other.cancel()
                    raise
                rows.append(row)
                inventory.extend(inputs)
                stream.write(encode(row) + "\n")
                stream.flush()
                if len(rows) % 25 == 0 or len(rows) == len(tasks):
                    print(encode({"completed_trajectories": len(rows), "total": len(tasks), "elapsed_seconds": time.monotonic()-started}), flush=True)
    rows.sort(key=lambda r: (r["target_D"], r["behavior_method"], r["seed"]))
    (output / "per_seed.jsonl").write_text("".join(encode(row) + "\n" for row in rows))
    inventory.sort(key=lambda r: r["path"])
    (output / "input_inventory.jsonl").write_text("".join(encode(row) + "\n" for row in inventory))
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["target_D"], row["behavior_method"])].append(row)
    groups = []
    for (target, behavior), seeds in sorted(grouped.items()):
        counts = {name: dict(sum((Counter(s["diagnostic_counts"][name]) for s in seeds), Counter())) for name in METHODS}
        variation = {name: {metric: describe([s["diagnostic_counts"][name][metric] / s["rounds"] for s in seeds])
                            for metric in ("width_argmax_first_matches", "width_argmax_set_matches", "strict_width_dominance_sufficient", "score_top_tie")}
                     for name in METHODS}
        groups.append({"W": seeds[0]["W"], "target_D": target, "behavior_method": behavior,
                       "seeds": [r["seed"] for r in seeds], "rounds": sum(r["rounds"] for r in seeds),
                       "diagnostic_counts": counts, "seed_fraction_variation": variation,
                       "same_history_mean_one_step_regret": {name: describe([s["same_history_mean_one_step_regret"][name] for s in seeds]) for name in METHODS},
                       "width_overhead_seed_mean_variation": {name: describe([s["effective_width_over_frozen_width"][name]["mean"] for s in seeds]) for name in METHODS},
                       "width_overhead_minimum": {name: min(s["effective_width_over_frozen_width"][name]["min"] for s in seeds) for name in METHODS},
                       "width_overhead_maximum": {name: max(s["effective_width_over_frozen_width"][name]["max"] for s in seeds) for name in METHODS},
                       "category_D_seed_mean_variation": describe([s["scalar_distributions"]["category_D"]["mean"] for s in seeds]),
                       "category_D_maximum": max(s["scalar_distributions"]["category_D"]["max"] for s in seeds),
                       "uniform_D": seeds[0]["uniform_D"], "uniform_width_factor": seeds[0]["uniform_width_factor"]})
    result = {"schema_version": 1, "scope": "exploratory post-outcome fixed-history endpoint audit",
              "new_adaptive_experiments": False, "optimizer_replayed_on_logged_actions_rewards": True,
              "floating_point_checks_are_verified_certificates": False, "source_run_status": manifest["status"],
              "source_run_historical_error": manifest.get("error"), "source_run_revision": manifest["git_revision"],
              "source_run_signature": manifest["signature"], "source_config_digest": manifest["config_digest"],
              "scientific_source_sha256": recorded_hash, "script_sha256": digest(Path(__file__).read_bytes()),
              "selection_sha256": manifest["selection_sha256"], "raw_root": str(root),
              "complete_600_trajectory_audit": len(rows) == 600, "trajectories": len(rows), "rounds": sum(r["rounds"] for r in rows),
              "checkpoint_rounds": CHECKPOINTS, "original_tolerance_multiplier": TOLERANCE.multiplier,
              "verification_counts": dict(sum((Counter(r["verification_counts"]) for r in rows), Counter())),
              "maximum_absolute_residual_or_excess": {k: max(r["maximum_absolute_residual_or_excess"][k] for r in rows) for k in rows[0]["maximum_absolute_residual_or_excess"]},
              "maximum_residual_or_excess_over_original_tolerance": {k: max(r["maximum_residual_or_excess_over_original_tolerance"][k] for r in rows) for k in rows[0]["maximum_residual_or_excess_over_original_tolerance"]},
              "elapsed_seconds": time.monotonic()-started, "workers": args.workers,
              "versions": {"python": platform.python_version(), "python_build": sys.version, "numpy": np.__version__, "scipy": scipy.__version__},
              "thread_environment": {k: os.environ.get(k) for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")},
              "tie_rule": "first maximum action index on stored/replayed float64 scores; exact equality only",
              "arithmetic": "No high-precision replay. Normalized-score differences measure float expression sensitivity, not exact decisions.",
              "conditional_scope": "Off-diagonal recommendations hold each behavior's history fixed; their mean one-step regret is not alternate adaptive cumulative regret.",
              "timing_scope": "Five repeated batches at seed 30200 and rounds 100/500/1000 for each behavior/W; fixed-state kernels only. Dense metrics preassembled. Parallel analysis load present. No end-to-end speedup claim.",
              "benchmark_repeats_per_batch": args.benchmark_repeats, "input_files": len(inventory),
              "input_bytes": sum(v["bytes"] for v in inventory), "groups": groups}
    (output / "analysis.json").write_text(json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n")
    artifact_names = ("analysis.json", "input_inventory.jsonl", "per_seed.jsonl")
    (output / "ARTIFACTS.sha256").write_text("".join(digest((output/name).read_bytes()) + "  " + name + "\n" for name in artifact_names))
    print(encode({"complete": True, "trajectories": len(rows), "elapsed_seconds": result["elapsed_seconds"], "output": str(output)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=Path("/workspace/cce-full-local"))
    parser.add_argument("--output-dir", type=Path, default=REPOSITORY/"review/transport_relative_diagnostics/full")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-trajectories", type=int, default=0, help="Timing/verification sample only; never labelled a complete audit")
    parser.add_argument("--benchmark-repeats", type=int, default=20)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    require(args.workers > 0 and args.max_trajectories >= 0 and args.benchmark_repeats > 0, "Invalid counts")
    if args.self_test:
        self_test()
    else:
        run(args)
