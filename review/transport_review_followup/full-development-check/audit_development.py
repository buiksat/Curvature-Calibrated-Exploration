#!/usr/bin/env python3
"""Read-only audit of a completed development-only follow-up; standard library only.

This checks provenance and stored numerical diagnostics. It does not rerun the
policy, recompute matrix factorizations, or establish verified enclosures.
"""
import argparse
import copy
import hashlib
import itertools
import json
import math
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def merge(left, right):
    result = copy.deepcopy(left)
    for k, v in right.items():
        result[k] = merge(result[k], v) if isinstance(v, dict) and isinstance(result.get(k), dict) else copy.deepcopy(v)
    return result


def finite(value):
    if isinstance(value, float):
        require(math.isfinite(value), "Nonfinite numeric value")
    elif isinstance(value, dict):
        for v in value.values():
            finite(v)
    elif isinstance(value, list):
        for v in value:
            finite(v)


def audit(raw_root, repository):
    root, repo = Path(raw_root), Path(repository)
    manifest = load(root / "run.json")
    config = load(root / "execution_config.json")
    source = load(root / "source_config.json")
    progress = load(root / "progress.json")
    require(manifest["status"] == "development_complete", "Development gate not complete")
    require(manifest["evaluation_complete"] is False, "Not a development-only snapshot")
    require(manifest["requested_profile"] == "full" and config["profile"] == "full", "Wrong profile")
    require(manifest["git_dirty_at_start"] is False, "Full development did not start clean")
    require(not any((root / p).exists() for p in ("selection.json", "aggregate.json", "raw/tuning", "raw/evaluation", "interrupted")), "Unexpected tuning/evaluation or interrupted outputs")
    require(not list(root.rglob(".review-failed.json")), "Failure marker present")
    cfg_digest = hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()
    require(cfg_digest == manifest["config_digest"], "Configuration digest mismatch")
    resolved = merge(merge({k: v for k, v in source.items() if k not in ("base", "profiles")}, source["base"]), source["profiles"]["full"])
    resolved["profile"] = "full"
    resolved["execution"]["workers"] = manifest["plan"]["workers"]
    resolved["execution"]["blas_threads_per_worker"] = 1
    require(resolved == config, "Execution config does not resolve from source config")
    for item in manifest["source_inputs"]:
        require(digest(repo / item["path"]) == item["sha256"], "Source mismatch: " + item["path"])
    bound_config = next(item for item in manifest["source_inputs"] if item["path"] == "experiments/configs/transport_review_followup.yaml")
    require(digest(root / "source_config.json") == bound_config["sha256"], "Saved source config not bound to run")
    identity_keys = ("git_revision", "source_inputs", "config_digest", "requested_profile", "packages", "python", "output", "quadrature_node_cache")
    identity = {k: manifest[k] for k in identity_keys}
    signature = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    require(signature == manifest["signature"], "Run signature mismatch")
    splits = [set(config["seed_sets"][k]) for k in ("development", "tuning", "evaluation")]
    require(all(not a.intersection(b) for a, b in itertools.combinations(splits, 2)), "Seed sets overlap")
    expected = set(itertools.product(config["horizons"], config["target_D"], config["methods"], config["seed_sets"]["development"]))
    paths = sorted((root / "raw/development").rglob("summary.json"))
    require(len(paths) == len(expected) == 24, "Incomplete or extra development grid")
    require(progress["completed"] == progress["total"] == 24 and progress["phase"] == "_policy_task", "Progress is incomplete")
    inventory, receipts, summaries, diagnostics, seen = [], [], [], [], set()
    required = {"manifest.jsonl", "raw.jsonl", "summary.json", "summary.json.sha256"}
    quad = config["transport"]["quadrature"]
    declared_optimizer = {k: config["representation_update"]["development_optimizer"][k] for k in ("learning_rate", "steps_per_round")}
    for path in paths:
        leaf = path.parent
        receipt = load(leaf / ".review-complete.json")
        require(receipt["signature"] == signature and set(receipt["files"]) == required, "Invalid completion receipt")
        for name, sha in receipt["files"].items():
            require(digest(leaf / name) == sha, "Receipt hash mismatch: " + str(leaf / name))
        for name in sorted(required | {".review-complete.json"}):
            f = leaf / name
            inventory.append({"path": str(f.relative_to(root)), "bytes": f.stat().st_size, "sha256": digest(f)})
        receipts.append({"directory": str(leaf.relative_to(root)), "receipt": receipt})
        s, m = load(path), load(leaf / "manifest.jsonl")
        finite(s)
        require((leaf / "summary.json.sha256").read_text().split() == [digest(path), "summary.json"], "Summary sidecar mismatch")
        key = (s["horizon"], s["target_D"], s["method"], s["seed"])
        require(key in expected and key not in seen, "Duplicate/unexpected development cell")
        seen.add(key)
        token = format(s["target_D"], ".12g").replace("-", "m").replace(".", "p")
        canonical = Path("raw/development") / ("T-" + str(s["horizon"])) / ("D-" + token) / s["method"] / ("seed-" + str(s["seed"]))
        require(leaf.relative_to(root) == canonical, "Noncanonical cell path")
        require(m["config"] == config and m["config_digest"] == s["config_digest"] == cfg_digest, "Per-run configuration mismatch")
        require(m["git_revision"] == manifest["git_revision"], "Per-run source revision mismatch")
        require(s["optimizer"] == declared_optimizer, "Development optimizer mismatch")
        for k in ("method", "horizon", "target_D", "seed", "W", "phase", "profile"):
            require(m[k] == s[k], "Run metadata mismatch: " + k)
        require(s["phase"] == "development" and s["selection_sha256"] is None and m["selection_sha256"] is None, "Unexpected selected/evaluation run")
        require(s["deterministic_audit_pass"] is True and s["deterministic_audit_passed"] is True and s["deterministic_audit_failure_count"] == 0 and s["deterministic_audit_failures"] == [], "Summary audit failure")
        i = config["target_D"].index(s["target_D"])
        require(math.isclose(s["W"], config["followup"]["prespecified_width_W"][i], rel_tol=1e-12), "W pairing mismatch")
        radius = config["teacher"]["theta_radius"]
        c_h = 4 * config["environment"]["feature_bound"] ** 2 / (3 * math.sqrt(3))
        expected_w = (4 * c_h * radius * math.sqrt(s["horizon"] - 1) / (config["environment"]["noise_std"] * math.sqrt(config["ridge"]) * s["target_D"])) ** 2
        require(math.isclose(s["W"], expected_w, rel_tol=1e-12), "W target rule mismatch")
        counts = {str(t): 0 for t in config["followup"]["descriptive_drift_reporting_thresholds"]}
        maximum, dqmax, pathmax, diffmax, checkpoints, qratio, n = 0.0, 0.0, 0.0, 0.0, 0, 0.0, 0
        confidence, optimism = True, True
        with (leaf / "raw.jsonl").open() as f:
            for n, line in enumerate(f, 1):
                r = json.loads(line)
                v = r["metrics"]
                finite(v)
                require(r["event"] == "round" and r["round"] == n - 1 and v["round"] == n and r["seed"] == s["seed"] and r["run_id"] == m["run_id"], "Round sequence/identity mismatch")
                require(v["deterministic_audit_passed"] is True and v["deterministic_audit_failure_count"] == 0 and v["deterministic_audit_failures"] == [], "Raw deterministic audit failure")
                require(v["instantaneous_bound_status"] != "bound_violation_on_event" and v["cumulative_bound_status"] != "bound_violation_on_event", "On-event bound violation")
                d, dq = v["d_Th"], v["D_Q"]
                require(d == v["endpoint_thompson_distance"], "Endpoint alias mismatch")
                maximum, dqmax = max(maximum, d), max(dqmax, dq)
                for threshold in counts:
                    counts[threshold] += int(d >= float(threshold))
                confidence = confidence and v["reference_confidence_all_actions"]
                optimism = optimism and v["method_optimism_all_actions"]
                checkpoint = n % quad["full_checkpoint_period"] == 0 or n in config["horizons"] or n == s["horizon"]
                plen, half = v["factor_path_length_quad"], v["factor_path_length_half_order"]
                require(checkpoint == (plen is not None) == (half is not None), "Quadrature checkpoint mismatch")
                if checkpoint:
                    checkpoints += 1
                    tolerance = max(quad["convergence_absolute_tolerance"] + quad["convergence_relative_tolerance"] * max(1.0, abs(d), abs(plen), abs(dq)), v["algebra_tolerance"])
                    diff = abs(plen - half)
                    require(diff <= tolerance and max(0, d - plen) <= tolerance and max(0, plen - dq) <= tolerance, "Stored quadrature convergence/inequality failure")
                    diffmax, pathmax, qratio = max(diffmax, diff), max(pathmax, plen), max(qratio, diff / tolerance)
                require(v["prefix_simultaneous_reference_confidence"] == confidence and v["prefix_simultaneous_method_optimism"] == optimism, "Confidence-prefix mismatch")
        require(n == s["rounds"] == s["horizon"] == 1000 and checkpoints == 100, "Wrong horizon/checkpoint count")
        for observed, name in ((maximum, "max_endpoint_thompson_distance"), (dqmax, "max_realized_D_Q"), (pathmax, "max_factor_path_length_quad"), (diffmax, "max_quadrature_order_difference")):
            require(observed == s[name], "Raw/summary maximum mismatch: " + name)
        require(confidence == s["simultaneous_reference_confidence"] and optimism == s["simultaneous_method_optimism"], "Raw/summary event mismatch")
        for name in ("cumulative_pseudo_regret", "sharp_theorem_rhs", "simple_theorem_rhs", "statistical_bound_component", "historical_bound_component", "path_inflation_component", "current_bias_cumulative"):
            require(v[name] == s[name], "Terminal raw/summary mismatch: " + name)
        summaries.append(s)
        diagnostics.append({"method": s["method"], "seed": s["seed"], "horizon": n, "target_D": s["target_D"], "W": s["W"], "round_count": n, "quadrature_checkpoints": checkpoints, "endpoint_at_least_threshold_counts": counts, "endpoint_at_least_threshold_fractions": {k: c/n for k,c in counts.items()}, "max_endpoint_thompson_distance": maximum, "max_realized_D_Q": dqmax, "max_quadrature_order_difference": diffmax, "max_order_difference_over_configured_tolerance": qratio, "simultaneous_reference_confidence": confidence, "simultaneous_method_optimism": optimism})
    require(seen == expected, "Grid mismatch")
    report = {"schema_version": 1, "status": "pass", "scope": "development-only stored-data audit; no experiment rerun or verified enclosure", "raw_root": str(root), "source_revision": manifest["git_revision"], "source_input_files_checked": len(manifest["source_inputs"]), "config_digest": cfg_digest, "run_signature": signature, "completed_development_runs": len(summaries), "raw_rounds_checked": sum(d["round_count"] for d in diagnostics), "quadrature_checkpoints_checked": sum(d["quadrature_checkpoints"] for d in diagnostics), "raw_and_receipt_files_hashed": len(inventory), "development_phase_elapsed_seconds": progress["elapsed_seconds"], "development_runs_reused": progress["reused"], "sum_trajectory_runtime_seconds": sum(s["runtime_seconds"] for s in summaries), "max_order_difference": max(d["max_quadrature_order_difference"] for d in diagnostics), "max_order_difference_over_configured_tolerance": max(d["max_order_difference_over_configured_tolerance"] for d in diagnostics), "simultaneous_reference_confidence_runs": sum(s["simultaneous_reference_confidence"] for s in summaries), "simultaneous_method_optimism_runs": sum(s["simultaneous_method_optimism"] for s in summaries), "tuning_runs": 0, "evaluation_runs": 0, "raw_trajectories_included_in_compact_export": False}
    return report, summaries, diagnostics, inventory, receipts


def verify_bundle(bundle):
    """Check transferred evidence without implying availability of raw rounds."""
    bundle = Path(bundle)
    export = load(bundle / "export_manifest.json")
    require(export["development_only"] is True and export["raw_trajectories_included"] is False, "Unexpected export scope")
    actual = {p.name for p in bundle.iterdir() if p.is_file() and p.name != "export_manifest.json"}
    require(actual == {e["path"] for e in export["files"]}, "Export file inventory differs")
    for entry in export["files"]:
        path = bundle / entry["path"]
        require(path.parent == bundle and digest(path) == entry["sha256"] and path.stat().st_size == entry["bytes"], "Transferred file mismatch: " + entry["path"])
    manifest, config = load(bundle / "run_manifest.json"), load(bundle / "execution_config.json")
    report = load(bundle / "audit_report.json")
    rows = [json.loads(line) for line in (bundle / "development_summaries.jsonl").read_text().splitlines()]
    diagnostics = [json.loads(line) for line in (bundle / "round_drift_summaries.jsonl").read_text().splitlines()]
    receipts = [json.loads(line) for line in (bundle / "completion_receipts.jsonl").read_text().splitlines()]
    inventory = [json.loads(line) for line in (bundle / "raw_input_inventory.jsonl").read_text().splitlines()]
    cfg_digest = hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()
    require(manifest["status"] == "development_complete" and manifest["evaluation_complete"] is False, "Export is not development-only")
    require(cfg_digest == manifest["config_digest"] == report["config_digest"], "Transferred config digest mismatch")
    require(digest(bundle / "run_manifest.json") == export["source"]["run_manifest_sha256"], "Transferred run manifest mismatch")
    source_entry = next(e for e in manifest["source_inputs"] if e["path"] == "experiments/configs/transport_review_followup.yaml")
    require(digest(bundle / "source_config.json") == source_entry["sha256"], "Transferred source config mismatch")
    expected = set(itertools.product(config["horizons"], config["target_D"], config["methods"], config["seed_sets"]["development"]))
    identity = lambda r: (r["horizon"], r["target_D"], r["method"], r["seed"])
    require(len(rows) == len(diagnostics) == len(receipts) == len(expected) == 24, "Transferred row count mismatch")
    require({identity(r) for r in rows} == {identity(r) for r in diagnostics} == expected, "Transferred grid mismatch")
    require(len(inventory) == 120 and len({r["path"] for r in inventory}) == 120, "Raw hash inventory mismatch")
    inv = {r["path"]: r["sha256"] for r in inventory}
    for item in receipts:
        require(item["receipt"]["signature"] == manifest["signature"], "Transferred receipt signature mismatch")
        for name, sha in item["receipt"]["files"].items():
            require(inv[str(Path(item["directory"]) / name)] == sha, "Receipt/inventory mismatch")
    for r in rows:
        finite(r)
        require(r["config_digest"] == cfg_digest and r["phase"] == "development" and r["selection_sha256"] is None and r["deterministic_audit_pass"] is True, "Transferred summary scope/status mismatch")
        d = next(d for d in diagnostics if identity(d) == identity(r))
        require(d["round_count"] == r["rounds"] == 1000 and d["quadrature_checkpoints"] == 100, "Transferred diagnostic count mismatch")
        for name in ("max_endpoint_thompson_distance", "max_realized_D_Q", "max_quadrature_order_difference"):
            require(d[name] == r[name], "Transferred diagnostic/summary mismatch")
        for threshold, count in d["endpoint_at_least_threshold_counts"].items():
            require(isinstance(count, int) and 0 <= count <= 1000 and d["endpoint_at_least_threshold_fractions"][threshold] == count/1000, "Transferred drift fraction mismatch")
    require(report["status"] == "pass" and report["completed_development_runs"] == 24 and report["tuning_runs"] == report["evaluation_runs"] == 0, "Transferred audit scope/status mismatch")
    return {"status": "pass", "transferred_files_checked": len(export["files"]), "development_summaries_checked": len(rows), "raw_data_read": False, "note": "Integrity and internal consistency only; raw diagnostics were not replayed by this check."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--raw-root", type=Path, help="Optional retained raw directory for the full stored-data audit")
    parser.add_argument("--repository", type=Path, help="Checkout whose source hashes match the run; required with --raw-root")
    args = parser.parse_args()
    result = {"transferred_evidence": verify_bundle(args.bundle)}
    if args.raw_root is not None:
        if args.repository is None:
            parser.error("--repository is required with --raw-root")
        raw_report, *_ = audit(args.raw_root, args.repository)
        recorded = load(args.bundle / "audit_report.json")
        require({k:v for k,v in raw_report.items() if k != "raw_root"} == {k:v for k,v in recorded.items() if k != "raw_root"}, "Replayed audit differs from recorded audit")
        result["raw_stored_data_audit"] = raw_report
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))
