"""Secondary policy study: frozen, naive and endpoint policies on their own histories.

Environment, teacher, context and potential-outcome streams, and the projected
optimizer are those of ``experiments.transport_v3`` (d = 6, K = 3, 12 categories,
learning rate 3e-6 and 5 steps per round as selected there).  The confidence
construction is the corrected center with the new certified-envelope variant
(``relin_coverage.sharp_envelope``) in both the historical part of beta_t and the
actionwise allowance b_t(a).  Each policy acts on its own adaptive history; seeds
share context and potential-outcome streams across policies, and each learner
sees only its selected reward.

Usage:
  python -m experiments.relin_policy --phase development --seeds 51000-51015 \
      --widths 1 10 100 --output OUT --workers 4
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
import traceback
from dataclasses import asdict, dataclass
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from experiments import relin_coverage as rc
from experiments import transport_instantiation as ti
from experiments import transport_v3 as v3

METHODS = ("frozen_reference", "naive_current", "transport_endpoint")


@dataclass(frozen=True)
class PolicySpec:
    width: float
    horizon: int = 20000
    sigma: float = 0.25
    ridge: float = 1.0
    training_ridge: float = 1.0
    radius: float = 1.0
    delta: float = 0.05
    teacher_seed: int = 1729
    learning_rate: float = 3e-6
    steps_per_round: int = 5


def mean_table(spec: PolicySpec) -> np.ndarray:
    theta_o = v3.teacher(spec.teacher_seed, spec.radius)
    return np.stack([v3.mean(theta_o, v3.FEATURES[i], spec.width) for i in range(len(v3.CONTEXTS))])


def run_policy(method: str, seed: int, spec: PolicySpec, envelope: str = "sharp") -> dict:
    """``envelope='original'`` exists only to test this port against transport_v3.run_corrected."""
    theta_o = v3.teacher(spec.teacher_seed, spec.radius)
    ctx, mu, rewards = v3.stream(seed, spec, theta_o)  # evaluator side; the learner reads rewards[t, a_t] only
    W, sigma2, T, D, K = spec.width, spec.sigma ** 2, spec.horizon, v3.D, v3.K
    model = rc.ModelClass(width=W, radius=spec.radius)
    cats = v3.CATEGORY_FEATURES
    theta = np.zeros(D)
    frozen, rhs = spec.ridge * np.eye(D), np.zeros(D)
    counts, frozen_weights, reward_sums = np.zeros(len(cats)), np.zeros(len(cats)), np.zeros(len(cats))
    categories, hist_energy, regret = np.zeros(T, dtype=np.int64), 0.0, 0.0
    rec = {"action": np.empty(T, dtype=np.int8), "center": np.empty((T, K)), "sbar": np.empty((T, K)),
           "s": np.empty((T, K)), "b": np.empty((T, K)), "beta": np.empty(T), "d_th": np.empty(T),
           "theta_norm": np.empty(T)}
    checks, failures, start = [], [], time.perf_counter()
    for t in range(T):
        i = int(ctx[t])
        feats = v3.FEATURES[i]
        q = v3.weight(theta, feats, W)[:, None] * feats
        current = spec.ridge * np.eye(D) + (cats.T * (counts * v3.weight(theta, cats, W) ** 2)) @ cats / sigma2
        theta_hat = ti.cholesky_solve(frozen, rhs)
        centers = v3.mean(theta, feats, W) + q @ (theta_hat - theta)
        sbar, s = ti.inverse_quadratic_widths(frozen, q), ti.inverse_quadratic_widths(current, q)
        beta, _, _ = ti.confidence_radius(ti.information_gain(frozen, spec.ridge), delta=spec.delta, ridge=spec.ridge,
                                          theta_radius=spec.radius, historical_error_energy=hist_energy,
                                          noise_std=spec.sigma)
        if envelope == "sharp":
            bias = rc.sharp_envelope(feats @ theta, spec.radius * np.linalg.norm(feats, axis=1), model)
        else:
            bias = np.full(K, rc.original_envelope(np.linalg.norm(theta), 1.0, model))
        d_th, _ = ti.thompson_distance(frozen, current)
        own = {"frozen_reference": sbar, "naive_current": s, "transport_endpoint": math.exp(0.5 * d_th) * s}[method]
        a = int(np.argmax(centers + beta * own + bias))
        regret += float(mu[t].max() - mu[t, a])
        rec["action"][t], rec["center"][t], rec["sbar"][t], rec["s"][t] = a, centers, sbar, s
        rec["b"][t], rec["beta"][t], rec["d_th"][t], rec["theta_norm"][t] = bias, beta, d_th, np.linalg.norm(theta)
        if t + 1 in v3.CHECKPOINTS:
            dense = spec.ridge * np.eye(D)
            for c_s in categories[:t]:
                g = v3.weight(theta, cats[c_s], W) * cats[c_s]
                dense += np.outer(g, g) / sigma2
            cat_frozen = spec.ridge * np.eye(D) + (cats.T * frozen_weights) @ cats / sigma2
            check = {"round": t + 1,
                     "current_category_vs_dense": [float(np.max(np.abs(current - dense))), v3.tolerance(current, dense)],
                     "frozen_dense_vs_category": [float(np.max(np.abs(frozen - cat_frozen))), v3.tolerance(frozen, cat_frozen)]}
            checks.append(check)
            failures += [f"{k}_round_{t + 1}" for k, v in check.items() if k != "round" and v[0] > v[1]]
        cat = i * K + a
        g = q[a]
        y = rewards[t, a] - v3.mean(theta, feats[a], W) + g @ theta  # pseudo-response at collection time
        frozen += np.outer(g, g) / sigma2
        rhs += g * y / sigma2
        counts[cat] += 1.0
        frozen_weights[cat] += float(v3.weight(theta, feats[a], W)) ** 2
        reward_sums[cat] += rewards[t, a]
        categories[t] = cat
        hist_energy += float(bias[a]) ** 2  # computed before r_t
        for _ in range(spec.steps_per_round):  # the v3 projected full-batch optimizer on category statistics
            w_c = v3.weight(theta, cats, W)
            resid = counts * v3.mean(theta, cats, W) - reward_sums
            theta = theta - spec.learning_rate * ((w_c * resid) @ cats / sigma2 + spec.training_ridge * theta)
        if not np.all(np.isfinite(theta)):
            raise FloatingPointError(f"nonfinite optimizer iterate after round {t + 1}")
        norm = np.linalg.norm(theta)
        if norm > spec.radius:
            theta *= spec.radius / norm
    meta = {"method": method, "seed": seed, "spec": asdict(spec), "regret": regret,
            "context_free_regret": v3.context_free_regret(mu, rewards),
            "gamma_T": ti.information_gain(frozen, spec.ridge), "replay_checks": checks, "failures": failures,
            "final_theta_norm": float(np.linalg.norm(theta)), "runtime_seconds": time.perf_counter() - start}
    return {"meta": meta, "records": rec | {"context": ctx.astype(np.int8)}}


def _job(args):
    method, seed, spec, out, phase = args
    stem = out / f"W{spec.width:g}_{method}_{seed}"
    try:
        result = run_policy(method, seed, spec)
        np.savez_compressed(f"{stem}.npz", **result["records"])
        Path(f"{stem}.json").write_text(json.dumps(result["meta"] | {"phase": phase}, indent=1, sort_keys=True) + "\n")
        return stem.name, None
    except Exception:
        tb = traceback.format_exc()
        Path(f"{stem}.crash.json").write_text(json.dumps({"method": method, "seed": seed, "spec": asdict(spec),
                                                          "phase": phase, "crashed": True, "traceback": tb}) + "\n")
        return stem.name, tb


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--phase", required=True, choices=("development", "evaluation"))
    p.add_argument("--seeds", required=True)
    p.add_argument("--widths", type=float, nargs="+", required=True)
    p.add_argument("--horizon", type=int, default=PolicySpec.horizon)
    p.add_argument("--methods", nargs="+", default=list(METHODS), choices=METHODS)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--protocol", type=Path)
    args = p.parse_args()
    if args.phase == "evaluation" and (args.protocol is None or len(args.widths) != 1):
        p.error("evaluation requires --protocol and exactly one width")
    args.output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    files = ("experiments/relin_policy.py", "experiments/relin_coverage.py", "experiments/transport_v3.py",
             "experiments/transport_instantiation.py")
    manifest = {"argv": {k: str(v) for k, v in vars(args).items()}, **rc.provenance(root, files)}
    if args.protocol:
        manifest["protocol_sha256"] = hashlib.sha256(args.protocol.read_bytes()).hexdigest()
    rc.write_manifest(args.output, manifest)
    jobs = []
    for W in args.widths:
        spec = PolicySpec(width=W, horizon=args.horizon)
        for seed in rc.parse_seeds(args.seeds):
            for m in args.methods:
                stem = args.output / f"W{W:g}_{m}_{seed}"
                if not rc.resume_done(stem, {"method": m, "seed": seed, "spec": asdict(spec), "phase": args.phase}):
                    jobs.append((m, seed, spec, args.output, args.phase))
    start = time.perf_counter()
    with Pool(args.workers) as pool:
        for name, tb in pool.imap_unordered(_job, jobs):
            print(f"{name}: {'CRASH' if tb else 'ok'}", flush=True)
    print(f"{len(jobs)} runs in {time.perf_counter() - start:.1f}s wall", flush=True)


if __name__ == "__main__":
    main()
