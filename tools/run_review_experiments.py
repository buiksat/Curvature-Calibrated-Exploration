#!/usr/bin/env python3
"""Resume a separately registered CPU follow-up without touching locked evidence."""
from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import datetime as dt
import fcntl
import functools
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
THREAD_VARIABLES = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                    "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS")
for _name in THREAD_VARIABLES:
    os.environ[_name] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True


class WorkflowError(RuntimeError):
    pass


def read_json(path):
    return json.loads(Path(path).read_text())


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    from experiments.artifact_utils import atomic_write_text
    atomic_write_text(path, json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True).strip()


def source_inventory(config_path):
    from experiments.run_transport_instantiation_study import study_source_inventory
    paths = {REPO / item["path"] for item in study_source_inventory()}
    paths.update(REPO.glob("experiments/*.py"))
    paths.update({Path(__file__), config_path, REPO / "experiments/TRANSPORT_REVIEW_FOLLOWUP_PROTOCOL.md"})
    for relative in ("tools/run_review_experiments.sh", "tools/check_python_environment.py",
                     "tools/verify_review_experiment_export.py", "experiments/requirements-python312.lock"):
        path = REPO / relative
        if path.exists():
            paths.add(path)
    return [{"path": str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path),
             "sha256": sha256(path)} for path in sorted(paths)]


def ensure_external(path):
    resolved = Path(path).expanduser().resolve()
    if resolved == REPO or resolved.is_relative_to(REPO):
        raise WorkflowError("--output must be outside the Git checkout; raw evidence stays on the server.")
    return resolved


def _task_location(kind, task):
    from experiments.run_transport_instantiation import run_directory
    if kind == "_tuning_task":
        _, key, seed, horizon, target, _, root, _ = task
        phase = "tuning"
    elif kind == "_policy_task":
        _, key, seed, horizon, target, _, phase, _, root, _, _ = task
    else:
        raise WorkflowError(f"Unsupported task type: {kind}")
    return run_directory(root, phase=phase, horizon=horizon, target_d=target, run_key=key, seed=seed)


def install_quadrature_cache():
    """Memoize identical NumPy quadrature nodes; prohibit caller mutation."""
    import numpy as np
    original = np.polynomial.legendre.leggauss
    if getattr(original, "_review_cached", False):
        return
    @functools.lru_cache(maxsize=8)
    def cached(order):
        nodes, weights = original(order)
        nodes.setflags(write=False)
        weights.setflags(write=False)
        return nodes, weights
    cached._review_cached = True
    cached._review_original = original
    np.polynomial.legendre.leggauss = cached


def _resume_task(payload):
    """Only a verified completion receipt permits reuse; partial work is retained."""
    kind, task, signature = payload
    install_quadrature_cache()
    from experiments import run_transport_instantiation_study as study
    from experiments.run_transport_instantiation import REQUIRED_RUN_FILES
    directory = _task_location(kind, task)
    receipt_path = directory / ".review-complete.json"
    failure_path = directory / ".review-failed.json"
    if failure_path.exists():
        raise WorkflowError(f"Previous task failure preserved at {failure_path}; diagnose it before using a new output directory.")
    if receipt_path.exists():
        receipt = read_json(receipt_path)
        if receipt.get("signature") != signature:
            raise WorkflowError(f"Task provenance changed: {directory}")
        expected = receipt.get("files", {})
        if set(expected) != set(REQUIRED_RUN_FILES) or any(
            not (directory / name).is_file() or sha256(directory / name) != digest
            for name, digest in expected.items()
        ):
            raise WorkflowError(f"Completed task evidence changed or disappeared: {directory}")
        return {"destination": str(directory), **read_json(directory / "summary.json"), "resumed": True}
    if directory.exists():
        # No success receipt means interrupted output, never accepted evidence.
        root = Path(task[6] if kind == "_tuning_task" else task[8])
        quarantine = root.parent / "interrupted" / uuid.uuid4().hex
        quarantine.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(directory), str(quarantine))
        write_json(quarantine / ".original-location.json", {"path": str(directory)})
    try:
        result = getattr(study, kind)(task)
        inventory = {name: sha256(directory / name) for name in REQUIRED_RUN_FILES}
        write_json(receipt_path, {"signature": signature, "files": inventory})
        return {**result, "resumed": False}
    except Exception as error:
        directory.mkdir(parents=True, exist_ok=True)
        write_json(failure_path, {"signature": signature, "error_type": type(error).__name__, "error": str(error)})
        raise


def resumable_scheduler(signature, progress_path):
    def schedule(function, tasks, workers):
        count, results, reused = len(tasks), [], 0
        started = time.monotonic()
        kind = function.__name__
        payloads = iter((kind, task, signature) for task in tasks)
        executor = ProcessPoolExecutor(max_workers=workers)
        pending = set()
        try:
            for _ in range(min(workers, count)):
                pending.add(executor.submit(_resume_task, next(payloads)))
            while pending:
                finished, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in finished:
                    result = future.result()
                    results.append(result)
                    reused += int(result.get("resumed", False))
                    progress = {"phase": kind, "completed": len(results), "total": count,
                                "reused": reused, "elapsed_seconds": time.monotonic() - started}
                    write_json(progress_path, progress)
                    print(f"{kind}: {len(results)}/{count} ({reused} reused)", flush=True)
                    item = next(payloads, None)
                    if item is not None:
                        pending.add(executor.submit(_resume_task, item))
        except BaseException:
            for future in pending:
                future.cancel()
            executor.shutdown(wait=True, cancel_futures=True)
            raise
        executor.shutdown(wait=True)
        return results
    return schedule


def phase_ready(root, name):
    """A phase receipt distinguishes complete artifacts from interrupted writes."""
    paths = [root / name, root / (name + ".provenance.json"), root / (name + ".sha256")]
    receipt_path = root / ("." + name + ".complete.json")
    if receipt_path.exists():
        expected = read_json(receipt_path)
        if set(expected) != {path.name for path in paths} or any(
            not path.is_file() or sha256(path) != expected[path.name] for path in paths
        ):
            raise WorkflowError(f"Completed phase artifact changed: {name}")
        return True
    existing = [path for path in paths if path.exists()]
    if existing:
        quarantine = root / "interrupted" / uuid.uuid4().hex
        quarantine.mkdir(parents=True)
        for path in existing:
            shutil.move(str(path), str(quarantine / path.name))
    return False


def finish_phase(root, name):
    paths = [root / name, root / (name + ".provenance.json"), root / (name + ".sha256")]
    write_json(root / ("." + name + ".complete.json"), {path.name: sha256(path) for path in paths})


def export_compact(root, aggregate, manifest, destination):
    """Transfer exact seed outcomes and validated summaries, not raw trajectories."""
    destination = Path(destination).resolve()
    allowed = (REPO / "review/transport_review_followup").resolve()
    if not destination.is_relative_to(allowed) or destination == allowed:
        raise WorkflowError("Export must be a new child of review/transport_review_followup/.")
    source_id = {"aggregate_sha256": sha256(root / "aggregate.json"),
                 "execution_sha256": sha256(root / "execution_config.json")}
    executed = read_json(root / "execution_config.json")
    gradient_radius = executed["environment"]["feature_bound"] * executed["teacher"]["theta_radius"]
    if destination.exists():
        receipt = destination / "export_manifest.json"
        if receipt.is_file() and read_json(receipt).get("source") == source_id:
            for entry in read_json(receipt)["files"]:
                path = destination / entry["path"]
                if not path.is_file() or sha256(path) != entry["sha256"]:
                    raise WorkflowError(f"Existing compact export was modified: {path}")
            return destination
        raise WorkflowError(f"Refusing to overwrite a different existing export: {destination}")
    staging = destination.with_name("." + destination.name + ".tmp-" + uuid.uuid4().hex)
    staging.mkdir(parents=True)
    for name in ("execution_config.json", "source_config.json", "selection.json"):
        shutil.copyfile(root / name, staging / name)
    write_json(staging / "run_manifest.json", manifest)
    excluded = {"path_points", "regret_curves", "inputs", "bound_decomposition"}
    compact = {key: value for key, value in aggregate.items() if key not in excluded}
    compact["export_note"] = "New follow-up evidence. Raw provenance validated on the server; raw inputs remain there."
    write_json(staging / "aggregate_compact.json", compact)
    summaries, round_drift = [], []
    with (staging / "seed_summaries.jsonl").open("w") as handle:
        for path in sorted((root / "raw/evaluation").rglob("summary.json")):
            row = read_json(path)
            summaries.append(row)
            handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
            counts, rounds = {str(value): 0 for value in (0.01, 0.1, 1.0)}, 0
            with (path.parent / "raw.jsonl").open() as raw:
                for line in raw:
                    endpoint = json.loads(line)["metrics"]["endpoint_thompson_distance"]
                    rounds += 1
                    for threshold in counts:
                        counts[threshold] += int(endpoint >= float(threshold))
            if rounds != row["horizon"]:
                raise WorkflowError(f"Round count changed during compact export: {path.parent}")
            round_drift.append({key: row[key] for key in ("seed", "horizon", "target_D", "W", "method")}
                               | {"round_count": rounds, "endpoint_at_least_threshold_counts": counts})
    with (staging / "round_drift_summaries.jsonl").open("w") as handle:
        for row in round_drift:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    for phase in ("tuning", "development"):
        with (staging / (phase + "_summaries.jsonl")).open("w") as handle:
            for path in sorted((root / "raw" / phase).rglob("summary.json")):
                handle.write(json.dumps(read_json(path), sort_keys=True, allow_nan=False) + "\n")
    with (staging / "raw_input_inventory.jsonl").open("w") as handle:
        for item in aggregate["inputs"]:
            handle.write(json.dumps(item, sort_keys=True) + "\n")
    terminal = [row for row in aggregate["bound_decomposition"] if row["round"] == row["horizon"]]
    write_json(staging / "terminal_bound_decomposition.json", terminal)
    diagnostics = []
    cells = sorted({(row["horizon"], row["target_D"], row["method"]) for row in summaries})
    for horizon, target, method in cells:
        rows = [row for row in summaries if (row["horizon"], row["target_D"], row["method"]) == (horizon, target, method)]
        endpoint = [row["max_endpoint_thompson_distance"] for row in rows]
        drift_rows = [row for row in round_drift if (row["horizon"], row["target_D"], row["method"]) == (horizon, target, method)]
        denominator = sum(row["round_count"] for row in drift_rows)
        reference_rhs = [row["statistical_bound_component"] + row["historical_bound_component"] + row["current_bias_cumulative"] for row in rows]
        regret_cap = 2 * horizon * min(gradient_radius, math.sqrt(rows[0]["W"]))
        diagnostics.append({"horizon": horizon, "target_D": target, "W": rows[0]["W"], "method": method,
            "seeds": len(rows), "endpoint_maximum_across_seeds": max(endpoint),
            "endpoint_maximum_at_least_threshold_fraction": {str(threshold): sum(value >= threshold for value in endpoint) / len(rows) for threshold in (0.01, 0.1, 1.0)},
            "total_rounds": denominator,
            "endpoint_round_at_least_threshold_fraction": {str(threshold): sum(row["endpoint_at_least_threshold_counts"][str(threshold)] for row in drift_rows) / denominator for threshold in (0.01, 0.1, 1.0)},
            "reference_geometry_rhs_mean_on_own_trajectory": sum(reference_rhs) / len(rows),
            "reference_geometry_rhs_below_2T_fraction": sum(value < 2 * horizon for value in reference_rhs) / len(rows),
            "deterministic_regret_cap": regret_cap,
            "regret_cap_formula": "2*T*min(feature_bound*theta_radius,sqrt(W))",
            "reference_geometry_rhs_below_cap_fraction": sum(value < regret_cap for value in reference_rhs) / len(rows),
            "reference_rhs_note": "Statistical + historical + current-bias components on this method's actual trajectory; frozen-policy evidence only for frozen_reference. No policy-dominance inference."})
    write_json(staging / "drift_and_reference_diagnostics.json", diagnostics)
    (staging / "README.md").write_text(
        "# New transport follow-up results\n\n"
        f"Profile: **{manifest['requested_profile']}**. Source revision: `{manifest['git_revision']}`.\n\n"
        "These are fresh experiments, not reconstructed historical trajectories. "
        "Pilot output is not publication evidence. The strict aggregator validated every "
        "raw input on the server before this export. Git contains exact per-seed outcome "
        "summaries, aggregate statistics, configuration, selection and SHA-256 inventory; "
        "the full raw trajectories and aggregate remain at the recorded server output path. "
        "The portable export can reproduce terminal regret confidence intervals, but cannot "
        "independently replay roundwise audits or regret-curve confidence intervals.\n\n"
        "`export_manifest.json` binds all transferred files. Keep the server output directory "
        "and its raw data after pushing this folder.\n"
    )
    files = [{"path": path.name, "sha256": sha256(path), "bytes": path.stat().st_size}
             for path in sorted(staging.iterdir()) if path.is_file()]
    if sum(item["bytes"] for item in files) > 32 * 1024 * 1024:
        raise WorkflowError(f"Compact export exceeds 32 MiB; preserved staging directory: {staging}")
    write_json(staging / "export_manifest.json", {"schema_version": 1, "source": source_id, "files": files,
        "raw_data_included": False, "server_raw_validation_passed": True})
    staging.rename(destination)
    return destination


def run(args):
    from experiments import run_transport_instantiation_study as study
    from experiments.aggregate_transport_instantiation import aggregate_transport_instantiation
    from experiments.artifact_utils import validate_aggregate_provenance_sidecar, write_aggregate_with_provenance, write_sha256_sidecar
    from experiments.config import config_digest, load_config, get_seed_set
    root = ensure_external(args.output)
    config_path = args.config.resolve()
    profile = "smoke" if args.profile == "pilot" else "full"
    config = load_config(config_path, profile=profile)
    config["execution"]["workers"] = args.workers
    config["execution"]["blas_threads_per_worker"] = 1
    if config.get("outputs", {}).get("required_selection_export") is not None:
        raise WorkflowError("Follow-up config must disable required_selection_export to protect locked artifacts.")
    study.validate_transport_config(config)
    cells = len(study.study_cells(config))
    plan = {"profile": args.profile, "horizons": config["horizons"], "target_D": config["target_D"],
            "workers": args.workers, "blas_threads_per_worker": 1,
            "development_runs": cells * len(config["methods"]) * len(get_seed_set(config, "development")),
            "tuning_runs": cells * len(study.optimizer_grid(config)) * len(get_seed_set(config, "tuning")),
            "evaluation_runs": cells * len(config["methods"]) * len(get_seed_set(config, "evaluation")),
            "output": str(root), "GPU_required": False}
    print(json.dumps(plan, indent=2), flush=True)
    if args.plan:
        return 0
    checker = REPO / "tools/check_python_environment.py"
    if not checker.is_file():
        raise WorkflowError("Dependency preflight is missing; use the complete committed workflow.")
    subprocess.run([sys.executable, str(checker)], check=True, cwd=REPO)
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".launcher.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise WorkflowError("Another launcher owns this output directory.") from None
        manifest_path = root / "run.json"
        source = source_inventory(config_path)
        revision = git("rev-parse", "HEAD")
        identity = {"git_revision": revision, "source_inputs": source,
                    "config_digest": config_digest(config), "requested_profile": args.profile,
                    "packages": {name: importlib.metadata.version(name) for name in ("numpy", "scipy", "psutil")},
                    "python": sys.version, "output": str(root),
                    "quadrature_node_cache": {"function": "numpy.polynomial.legendre.leggauss", "maxsize": 8,
                                              "scope": "per worker process", "arrays": "unchanged values, read-only"}}
        signature = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        if manifest_path.exists():
            manifest = read_json(manifest_path)
            if manifest.get("signature") != signature:
                raise WorkflowError("Source, revision, configuration, Python or package versions changed. Preserve this run and choose a new --output directory.")
            if read_json(root / "execution_config.json") != config or sha256(root / "source_config.json") != sha256(config_path):
                raise WorkflowError("Saved execution configuration was modified.")
        else:
            dirty = bool(git("status", "--porcelain", "--untracked-files=normal"))
            if args.profile == "full" and dirty:
                raise WorkflowError("Commit the protocol, configuration and code before full evaluation; full runs require a clean starting checkout.")
            manifest = {**identity, "signature": signature, "git_dirty_at_start": dirty,
                        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                        "plan": plan, "status": "prepared", "raw_retention_required": True}
            write_json(root / "execution_config.json", config)
            shutil.copyfile(config_path, root / "source_config.json")
            write_json(manifest_path, manifest)
        def check_sources():
            if git("rev-parse", "HEAD") != revision or source_inventory(config_path) != source:
                raise WorkflowError("Study source changed during execution; preserve outputs and start a new run from a fixed revision.")
        original_scheduler = study._map_tasks
        study._map_tasks = resumable_scheduler(signature, root / "progress.json")
        try:
            check_sources()
            manifest["status"] = "development"
            write_json(manifest_path, manifest)
            study.run_development(config, root / "raw", overwrite=False)
            check_sources()
            if args.development_only:
                manifest.update(status="development_complete", evaluation_complete=False)
                write_json(manifest_path, manifest)
                print("Declared development grid passed; tuning and evaluation have not been run.")
                return 0
            manifest["status"] = "tuning"
            write_json(manifest_path, manifest)
            selection_path = root / "selection.json"
            if phase_ready(root, "selection.json"):
                study.load_selection(selection_path, config)
            else:
                study.run_tuning(config, root / "raw", selection_path,
                                 config_path=root / "source_config.json", overwrite=False)
                finish_phase(root, "selection.json")
            check_sources()
            manifest.update(status="evaluation", selection_sha256=sha256(selection_path))
            write_json(manifest_path, manifest)
            study.run_evaluation(config, root / "raw", selection_path, overwrite=False)
            check_sources()
            manifest["status"] = "aggregating"
            write_json(manifest_path, manifest)
            aggregate_path = root / "aggregate.json"
            if phase_ready(root, "aggregate.json"):
                validate_aggregate_provenance_sidecar(aggregate_path)
                aggregate = read_json(aggregate_path)
            else:
                aggregate = aggregate_transport_instantiation(config, selection_path, root / "raw",
                    profile=profile, config_path=root / "source_config.json")
                write_aggregate_with_provenance(aggregate, aggregate_path)
                write_sha256_sidecar(aggregate_path)
                finish_phase(root, "aggregate.json")
            check_sources()
            manifest.update(status="complete", aggregate_sha256=sha256(aggregate_path),
                            completed_at=dt.datetime.now(dt.timezone.utc).isoformat(), evaluation_complete=True)
            write_json(manifest_path, manifest)
            export_path = args.export_dir or REPO / "review/transport_review_followup" / f"{args.profile}-{root.name}"
            exported = export_compact(root, aggregate, manifest, export_path)
            subprocess.run([sys.executable, str(REPO / "tools/verify_review_experiment_export.py"), str(exported)], check=True, cwd=REPO)
            print(f"Complete. Compact GitHub export: {exported}\nKeep raw evidence: {root}")
        except BaseException as error:
            manifest.update(status="incomplete", error=f"{type(error).__name__}: {error}")
            write_json(manifest_path, manifest)
            raise
        finally:
            study._map_tasks = original_scheduler
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("pilot", "full"), default="pilot")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=REPO / "experiments/configs/transport_review_followup.yaml")
    available = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else (os.cpu_count() or 1)
    parser.add_argument("--workers", type=int, default=min(8, available))
    parser.add_argument("--export-dir", type=Path)
    parser.add_argument("--development-only", action="store_true", help="Run the entire declared development grid and stop before tuning/evaluation.")
    parser.add_argument("--plan", action="store_true", help="Print workload without running experiments or writing artifacts.")
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= available:
        parser.error(f"--workers must be between 1 and the {available} available logical CPUs")
    try:
        return run(args)
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Workflow stopped: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted. Completed trajectories are preserved; rerun the identical command to resume.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
