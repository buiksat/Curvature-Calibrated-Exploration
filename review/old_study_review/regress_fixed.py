"""Rerun 12 old-study evaluation trajectories (one per W x method, seed 30200) with the FIXED code
and compare every per-round metric and the summary with the replay's raw logs from the original code.
Only D_Q_over_d_Th and D_Q_over_path_quad may differ (the ratio-tolerance fix); report any change there.
Also check policy_scores at d8c97288 (before the fixes) against the current one, bitwise, on random finite inputs.

Usage (repository root on PYTHONPATH): python regress_fixed.py REPLAY_OUT_DIR
"""
import importlib.util
import json
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

OUT = Path(sys.argv[1])
RATIO = {"D_Q_over_d_Th", "D_Q_over_path_quad"}
VOLATILE = {"runtime_seconds", "config_digest", "selection_sha256"}


def norm(x):
    return json.loads(json.dumps(x, default=lambda o: o.tolist() if hasattr(o, "tolist") else float(o)))


def one(job):
    from experiments.transport_instantiation import OptimizerSpec, run_policy_trajectory
    method, cond = job
    config = json.loads((OUT / "execution_config.json").read_text())
    target = json.loads((OUT / "run.json").read_text())["plan"]["target_D"]
    token = {"D-97p3242004848": target[0], "D-389p296801939": target[1], "D-778p593603878": target[2]}[cond]
    run = run_policy_trajectory(config, method, 30200, 1000, token, OptimizerSpec(0.0003, 20), "evaluation")
    raw_dir = OUT / f"raw/evaluation/T-1000/{cond}/{method}/seed-30200"
    logged = [json.loads(line)["metrics"] for line in (raw_dir / "raw.jsonl").open()]
    diffs, ratio_changes = 0, 0
    for new, old in zip(norm(list(run.rounds)), logged):
        for k in set(new) | set(old):
            if new.get(k) != old.get(k):
                if k in RATIO:
                    ratio_changes += 1
                else:
                    diffs += 1
    summary_old = json.loads((raw_dir / "summary.json").read_text())
    summary_new = norm(run.summary)
    # the saved summary adds event/phase/schema_version and serializes optimizer; compare shared keys
    sdiff = sorted(k for k in set(summary_old) & set(summary_new)
                   if k not in VOLATILE and summary_old[k] != summary_new[k])
    sdiff += [f"only-saved:{k}" for k in sorted(set(summary_old) - set(summary_new) - {"event", "phase", "schema_version", "optimizer"} - VOLATILE)]
    sdiff += [f"only-new:{k}" for k in sorted(set(summary_new) - set(summary_old))]
    return cond, method, len(run.rounds), len(logged), diffs, ratio_changes, sdiff


if __name__ == "__main__":
    jobs = [(m, c) for c in ("D-97p3242004848", "D-389p296801939", "D-778p593603878")
            for m in ("transport_hessian", "transport_endpoint", "frozen_reference", "naive_current")]
    with ProcessPoolExecutor(12) as pool:
        results = list(pool.map(one, jobs))
    bad = False
    for cond, method, n_new, n_old, diffs, ratio_changes, sdiff in results:
        print(f"{cond} {method:20s} rounds {n_new}/{n_old}  other-field diffs {diffs}  ratio-field changes {ratio_changes}  summary diffs {sdiff or 'none'}")
        bad |= n_new != n_old or diffs > 0 or bool(sdiff)
    # policy_scores: old (d8c97288, before the fixes) vs new, bitwise, on random finite inputs
    old_src = subprocess.check_output(["git", "show", "d8c972887c9de091a0472bbe0bffcb8ce6db7cae:experiments/transport_instantiation.py"], text=True)
    spec = importlib.util.spec_from_loader("old_ti", loader=None)
    old = importlib.util.module_from_spec(spec)
    old.__package__ = "experiments"
    sys.modules["old_ti"] = old
    exec(compile(old_src, "old_ti", "exec"), old.__dict__)
    from experiments import transport_instantiation as new
    rng = np.random.default_rng(0)
    checked = 0
    for _ in range(2000):
        a = dict(beta=float(rng.uniform(0, 50)), current_bias=float(rng.uniform(0, 3)),
                 frozen_widths=rng.uniform(0, 1, 5), current_widths=rng.uniform(0, 1, 5),
                 hessian_path_bound=float(rng.uniform(0, 300)), endpoint_distance=float(rng.uniform(0, 5)))
        c = rng.normal(size=5)
        for m in ("transport_hessian", "transport_endpoint", "frozen_reference", "naive_current"):
            assert np.array_equal(old.policy_scores(m, c, **a), new.policy_scores(m, c, **a))
            checked += 1
    print(f"policy_scores old vs new: {checked} calls bitwise equal")
    raise SystemExit(1 if bad else 0)
