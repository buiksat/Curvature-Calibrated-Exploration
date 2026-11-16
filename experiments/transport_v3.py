"""Protocol v3 harness: low-dimensional scaled-tanh bandit (PROTOCOL_V3.md).

Environment: contexts x are normalized Rademacher vectors in R^2 (4 contexts),
K = 3 actions, features phi(x, a) = kron(x, e_a) in R^6 with ||phi|| = 1, and a
regular-simplex interaction teacher with ||theta_o|| = R = 1.  The four
corrected-center UCB policies reuse the scoring and confidence code of
``experiments.transport_instantiation``; UCB-GLM follows Li, Lu and Zhou
(2017, Algorithm 1).  Current matrices use category counts; dense replay checks
them at fixed rounds.

Usage:
  python -m experiments.transport_v3 --phase development --seeds 41000-41009 \
      --c 1 10 100 --output OUT_DIR [--workers 4]
  python -m experiments.transport_v3 --phase tuning --seeds 41100-41109 --c C \
      --methods tuning_uniform --learning-rate 3e-6 1e-5 3e-5 --steps 5 20 --output OUT_DIR
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import asdict, dataclass
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from experiments import transport_instantiation as ti

CONTEXT_DIM, K = 2, 3
D = CONTEXT_DIM * K
CONTEXTS = np.asarray([[i, j] for i in (-1.0, 1.0) for j in (-1.0, 1.0)]) / math.sqrt(2.0)
FEATURES = np.asarray([[np.kron(x, np.eye(K)[a]) for a in range(K)] for x in CONTEXTS])  # (4, K, D)
CATEGORY_FEATURES = FEATURES.reshape(-1, D)  # category = context * K + action
CORRECTED_METHODS = ("transport_hessian", "transport_endpoint", "frozen_reference", "naive_current")
METHODS = CORRECTED_METHODS + ("ucb_glm",)
CHECKPOINTS = (1, 10, 100, 1000, 10000, 20000)


@dataclass(frozen=True)
class Spec:
    horizon: int = 20000
    c: float = 1.0
    sigma: float = 0.25
    ridge: float = 1.0
    training_ridge: float = 1.0
    radius: float = 1.0
    delta: float = 0.05
    teacher_seed: int = 1729
    learning_rate: float = 1e-5
    steps_per_round: int = 20

    @property
    def width(self) -> float:
        return self.c * self.horizon


def teacher(seed: int, radius: float) -> np.ndarray:
    """Regular-simplex interaction teacher: theta[i*K + a] = v_a[i] / sqrt(K)."""
    basis = np.zeros((K, K - 1))
    for col in range(K - 1):
        den = math.sqrt((col + 1) * (col + 2))
        basis[: col + 1, col] = 1.0 / den
        basis[col + 1, col] = -(col + 1) / den
    vertices = math.sqrt(K / (K - 1)) * basis  # unit rows
    q, r = np.linalg.qr(np.random.default_rng(seed).normal(size=(K - 1, K - 1)))
    vertices = vertices @ (q * np.where(np.diag(r) < 0, -1.0, 1.0))
    theta = vertices.T.reshape(-1)
    return theta * radius / np.linalg.norm(theta)


def mean(theta, feats, width):
    return math.sqrt(width) * np.tanh(feats @ theta / math.sqrt(width))


def weight(theta, feats, width):  # sech^2 of the index
    return 1.0 - np.tanh(feats @ theta / math.sqrt(width)) ** 2


def stream(seed: int, spec: Spec, theta_o: np.ndarray):
    rng_c = np.random.default_rng(ti.derive_child_seed(seed, "transport_v3/context"))
    rng_n = np.random.default_rng(ti.derive_child_seed(seed, "transport_v3/noise"))
    ctx = rng_c.integers(0, len(CONTEXTS), size=spec.horizon)
    mu = np.stack([mean(theta_o, FEATURES[i], spec.width) for i in range(len(CONTEXTS))])[ctx]
    return ctx, mu, mu + rng_n.normal(0.0, spec.sigma, size=(spec.horizon, K))


def context_free_regret(mu, rewards) -> float:
    sums, counts, regret = np.zeros(K), np.zeros(K), 0.0
    for t in range(len(mu)):
        a = t if t < K else int(np.argmax(sums / counts))
        regret += mu[t].max() - mu[t, a]
        sums[a] += rewards[t, a]
        counts[a] += 1
    return float(regret)


def tolerance(*arrays) -> float:
    scale = max([1.0] + [float(np.max(np.abs(a))) for a in arrays])
    return 4096.0 * np.finfo(float).eps * D * scale


def run_corrected(method: str, seed: int, spec: Spec) -> dict:
    theta_o = teacher(spec.teacher_seed, spec.radius)
    ctx, mu, rewards = stream(seed, spec, theta_o)
    width, sigma2 = spec.width, spec.sigma ** 2
    c_h = ti.smoothness_constant(1.0)
    lip = c_h / math.sqrt(width)
    theta = np.zeros(D)
    frozen, rhs = spec.ridge * np.eye(D), np.zeros(D)
    counts, frozen_weights, reward_sums = np.zeros(len(CATEGORY_FEATURES)), np.zeros(len(CATEGORY_FEATURES)), np.zeros(len(CATEGORY_FEATURES))
    theta_sum, theta_sq_sum = np.zeros(D), 0.0
    categories, thetas = np.zeros(spec.horizon, dtype=np.int64), np.zeros((spec.horizon, D))
    hist_energy = regret = bias_sum = beta_sq_sum = a5_sum = 0.0
    zero_width_ok = gap_dominated = width_argmax = ratio_count = 0
    ratios, checks, beta_log, failures = [], [], {}, []
    start = time.perf_counter()
    for t in range(spec.horizon):
        i = int(ctx[t])
        feats = FEATURES[i]
        q = weight(theta, feats, width)[:, None] * feats
        w_cat = weight(theta, CATEGORY_FEATURES, width)
        current = spec.ridge * np.eye(D) + (CATEGORY_FEATURES.T * (counts * w_cat ** 2)) @ CATEGORY_FEATURES / sigma2
        theta_hat = ti.cholesky_solve(frozen, rhs)
        centers = mean(theta, feats, width) + q @ (theta_hat - theta)
        sbar, s = ti.inverse_quadratic_widths(frozen, q), ti.inverse_quadratic_widths(current, q)
        gamma = ti.information_gain(frozen, spec.ridge)
        beta, beta_stat, beta_hist = ti.confidence_radius(
            gamma, delta=spec.delta, ridge=spec.ridge, theta_radius=spec.radius,
            historical_error_energy=hist_energy, noise_std=spec.sigma)
        bias = 0.5 * lip * (spec.radius + np.linalg.norm(theta)) ** 2
        q_t = t * float(theta @ theta) - 2.0 * float(theta @ theta_sum) + theta_sq_sum
        d_q = 2.0 * lip * math.sqrt(max(q_t, 0.0)) / (spec.sigma * math.sqrt(spec.ridge))
        d_th, _ = ti.thompson_distance(frozen, current)
        scores = ti.policy_scores(method, centers, beta=beta, current_bias=bias, frozen_widths=sbar,
                                  current_widths=s, hessian_path_bound=d_q, endpoint_distance=d_th)
        a = int(np.argmax(scores))
        regret += float(mu[t].max() - mu[t, a])
        # Diagnostics (A2-A6 analogues) on this policy's own history.
        own_w = {"transport_hessian": math.exp(0.5 * d_q) * s, "transport_endpoint": math.exp(0.5 * d_th) * s,
                 "frozen_reference": sbar, "naive_current": s}[method]
        top = np.sort(beta * own_w)
        gap_dominated += int(top[-1] - top[-2] > np.ptp(centers))
        width_argmax += int(a == int(np.argmax(own_w)))
        zero_width_ok += int(np.sum(centers + bias >= mu[t]))
        ratios.extend((s / sbar).tolist())
        if t + 1 in CHECKPOINTS:
            dense_current = spec.ridge * np.eye(D)
            for c_s in categories[:t]:
                g = weight(theta, CATEGORY_FEATURES[c_s], width) * CATEGORY_FEATURES[c_s]
                dense_current += np.outer(g, g) / sigma2
            cat_frozen = spec.ridge * np.eye(D) + (CATEGORY_FEATURES.T * frozen_weights) @ CATEGORY_FEATURES / sigma2
            dense_q = float(np.sum((thetas[:t] - theta) ** 2))
            checks.append({"round": t + 1,
                           "current_category_vs_dense": float(np.max(np.abs(current - dense_current))),
                           "frozen_dense_vs_category": float(np.max(np.abs(frozen - cat_frozen))),
                           "q_running_vs_dense": abs(q_t - dense_q),
                           "tolerance": tolerance(current, dense_current, frozen, cat_frozen, [q_t, dense_q])})
            if max(checks[-1]["current_category_vs_dense"], checks[-1]["frozen_dense_vs_category"],
                   checks[-1]["q_running_vs_dense"]) > checks[-1]["tolerance"]:
                failures.append(f"category_vs_dense_replay_round_{t + 1}")
            beta_log[t + 1] = {"beta": beta, "stochastic": beta_stat - math.sqrt(spec.ridge) * spec.radius,
                               "ridge": math.sqrt(spec.ridge) * spec.radius, "historical": beta_hist,
                               "bias": bias, "d_Q": d_q, "d_Th": d_th}
        # Observe the selected reward only.
        cat = i * K + a
        g = q[a]
        y = rewards[t, a] - mean(theta, feats[a], width) + g @ theta
        frozen += np.outer(g, g) / sigma2
        rhs += g * y / sigma2
        counts[cat] += 1.0
        frozen_weights[cat] += float(weight(theta, feats[a], width)) ** 2
        reward_sums[cat] += rewards[t, a]
        categories[t], thetas[t] = cat, theta
        theta_sum += theta
        theta_sq_sum += float(theta @ theta)
        hist_energy += bias ** 2
        bias_sum += bias
        beta_sq_sum += beta ** 2
        a5_sum += gamma + 2.0 * math.log(1.0 / spec.delta)
        for _ in range(spec.steps_per_round):  # projected full-batch GD on category statistics
            w_c = weight(theta, CATEGORY_FEATURES, width)
            resid = counts * mean(theta, CATEGORY_FEATURES, width) - reward_sums
            theta = theta - spec.learning_rate * ((w_c * resid) @ CATEGORY_FEATURES / sigma2 + spec.training_ridge * theta)
        norm = np.linalg.norm(theta)
        if norm > spec.radius:
            theta *= spec.radius / norm
    gamma_t = ti.information_gain(frozen, spec.ridge)
    potential = spec.sigma ** 2 + 1.0 / spec.ridge  # G = B_phi = 1
    cap = 2.0 * spec.horizon * min(spec.radius, math.sqrt(width))
    ratios = np.asarray(ratios)
    return {
        "method": method, "seed": seed, "spec": asdict(spec), "W": width,
        "regret": regret, "context_free_regret": context_free_regret(mu, rewards), "cap": cap,
        "gamma_T": gamma_t,
        "A5": 2.0 * math.sqrt(potential * gamma_t * a5_sum),
        "frozen_form_bound": 2.0 * math.sqrt(potential * gamma_t * beta_sq_sum) + 2.0 * bias_sum,
        "bias_sum": bias_sum, "beta_by_round": beta_log, "replay_checks": checks,
        "gap_dominated_fraction": gap_dominated / spec.horizon,
        "width_argmax_fraction": width_argmax / spec.horizon,
        "zero_width_optimism_fraction": zero_width_ok / (K * spec.horizon),
        "s_over_sbar_quantiles": {str(p): float(np.quantile(ratios, p)) for p in (0.0, 0.1, 0.5, 0.9, 1.0)},
        "final_theta_norm": float(np.linalg.norm(theta)),
        "failures": failures, "runtime_seconds": time.perf_counter() - start,
    }


def run_ucb_glm(seed: int, spec: Spec) -> dict:
    """Li, Lu and Zhou (2017), Algorithm 1 (UCB-GLM), with link sqrt(W) tanh(u / sqrt(W))."""
    theta_o = teacher(spec.teacher_seed, spec.radius)
    ctx, mu, rewards = stream(seed, spec, theta_o)
    width, d, T = spec.width, D, spec.horizon
    kappa = 1.0 / math.cosh((spec.radius + 1.0) / math.sqrt(width)) ** 2  # inf over ||x||<=1, ||theta-theta*||<=1
    alpha = spec.sigma / kappa * math.sqrt(d / 2.0 * math.log(1.0 + 2.0 * T / d) + math.log(1.0 / spec.delta))
    rng = np.random.default_rng(ti.derive_child_seed(seed, "transport_v3/ucb_glm_init"))
    gram, counts, sums = np.zeros((d, d)), np.zeros(len(CATEGORY_FEATURES)), np.zeros(len(CATEGORY_FEATURES))
    theta_hat, tau, regret, newton_failures = np.zeros(d), None, 0.0, 0
    start = time.perf_counter()
    for t in range(T):
        i = int(ctx[t])
        feats = FEATURES[i]
        if tau is None:  # random initialization until lambda_min(V_{tau+1}) >= 1 (their Lemma 3 premise)
            a = int(rng.integers(0, K))
        else:
            for _ in range(50):  # Newton on the convex GLM objective sum_c n_c W log cosh(u/sqrt W) - S_c u
                u = CATEGORY_FEATURES @ theta_hat
                grad = (counts * mean(theta_hat, CATEGORY_FEATURES, width) - sums) @ CATEGORY_FEATURES
                if np.linalg.norm(grad) <= 1e-10 * max(1.0, float(np.sum(np.abs(sums)))):
                    break
                hess = (CATEGORY_FEATURES.T * (counts * (1.0 - np.tanh(u / math.sqrt(width)) ** 2))) @ CATEGORY_FEATURES
                theta_hat = theta_hat - np.linalg.solve(hess, grad)
            else:
                newton_failures += 1
            bonus = alpha * ti.inverse_quadratic_widths(gram, feats)
            a = int(np.argmax(feats @ theta_hat + bonus))
        regret += float(mu[t].max() - mu[t, a])
        x = feats[a]
        gram += np.outer(x, x)
        counts[i * K + a] += 1.0
        sums[i * K + a] += rewards[t, a]
        if tau is None and np.linalg.eigvalsh(gram)[0] >= 1.0:
            tau = t + 1
    return {"method": "ucb_glm", "seed": seed, "spec": asdict(spec), "W": width, "regret": regret,
            "context_free_regret": context_free_regret(mu, rewards), "kappa": kappa, "alpha": alpha,
            "tau": tau, "newton_failures": newton_failures,
            "failures": ["newton_nonconvergence"] * (newton_failures > 0),
            "runtime_seconds": time.perf_counter() - start}


def run_tuning(seed: int, spec: Spec) -> dict:
    """Uniform-random behavior; all-action prediction MSE of the shared optimizer after a 10% burn-in."""
    theta_o = teacher(spec.teacher_seed, spec.radius)
    ctx, mu, rewards = stream(seed, spec, theta_o)
    rng = np.random.default_rng(ti.derive_child_seed(seed, "transport_v3/behavior"))
    width, sigma2, burn_in = spec.width, spec.sigma ** 2, spec.horizon // 10
    theta = np.zeros(D)
    counts, reward_sums = np.zeros(len(CATEGORY_FEATURES)), np.zeros(len(CATEGORY_FEATURES))
    mse = []
    for t in range(spec.horizon):
        i = int(ctx[t])
        if t >= burn_in:
            mse.append(float(np.mean((mean(theta, FEATURES[i], width) - mu[t]) ** 2)))
        a = int(rng.integers(0, K))
        counts[i * K + a] += 1.0
        reward_sums[i * K + a] += rewards[t, a]
        for _ in range(spec.steps_per_round):
            w_c = weight(theta, CATEGORY_FEATURES, width)
            resid = counts * mean(theta, CATEGORY_FEATURES, width) - reward_sums
            theta = theta - spec.learning_rate * ((w_c * resid) @ CATEGORY_FEATURES / sigma2 + spec.training_ridge * theta)
        if not np.all(np.isfinite(theta)):
            return {"method": "tuning_uniform", "seed": seed, "spec": asdict(spec), "mse": None, "failures": ["nonfinite_iterate"]}
        norm = np.linalg.norm(theta)
        if norm > spec.radius:
            theta *= spec.radius / norm
    return {"method": "tuning_uniform", "seed": seed, "spec": asdict(spec), "mse": float(np.mean(mse)), "failures": []}


def run(job):
    method, seed, spec = job
    if method == "tuning_uniform":
        return run_tuning(seed, spec)
    return run_ucb_glm(seed, spec) if method == "ucb_glm" else run_corrected(method, seed, spec)


def parse_seeds(text: str) -> list[int]:
    lo, _, hi = text.partition("-")
    seeds = list(range(int(lo), int(hi or lo) + 1))
    if any(30000 <= s <= 30249 for s in seeds):
        raise SystemExit("seeds 30000-30249 are reserved by the earlier study")
    return seeds


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=("development", "tuning", "evaluation"))
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--c", type=float, nargs="+", default=[1.0])
    parser.add_argument("--horizon", type=int, default=Spec.horizon)
    parser.add_argument("--learning-rate", type=float, nargs="+", default=[Spec.learning_rate])
    parser.add_argument("--steps", type=int, nargs="+", default=[Spec.steps_per_round])
    parser.add_argument("--methods", nargs="+", default=list(METHODS), choices=METHODS + ("tuning_uniform",))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    jobs = [(m, s, Spec(horizon=args.horizon, c=c, learning_rate=lr, steps_per_round=k))
            for c in args.c for lr in args.learning_rate for k in args.steps
            for s in parse_seeds(args.seeds) for m in args.methods]
    with Pool(args.workers) as pool, (args.output / "runs.jsonl").open("w") as out:
        for result in pool.imap(run, jobs):
            result["phase"] = args.phase
            out.write(json.dumps(result, sort_keys=True) + "\n")
            out.flush()


if __name__ == "__main__":
    main()
