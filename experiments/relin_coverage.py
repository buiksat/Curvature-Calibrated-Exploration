"""Controlled relinearization coverage study: scalar scaled tanh, delayed update.

Question: on a realizable learning trajectory, can substituting the current
(relinearized) width for the reference width invalidate the reference
confidence band, while endpoint transport keeps coverage at informative widths?

Model: h(u) = sqrt(W) tanh(u / sqrt(W)), mu_theta(phi) = h(phi theta), actions
phi in {-1, +1}, known region [-R, R].  The environment's teacher theta_star is
never passed to the learner.  For ``block`` rounds the representation is held
at theta = R and the frozen-reference UCB policy (corrected center) selects
actions.  After the block the learner takes one projected batch gradient step
on L(theta) = (1 / 2n) sum_s (h(phi_s theta) - r_s)^2 and, at round block + 1,
every confidence construction is evaluated before another reward is observed.
This is an intentionally controlled, delayed-update learner.

The two actions are symmetric: within a construction both receive the same
bonus, so this study tests confidence validity only.  It cannot show a regret
advantage from transport.

Usage:
  python -m experiments.relin_coverage --phase development --seeds 50000-50015 --output OUT
  python -m experiments.relin_coverage --phase deterministic --output OUT
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import time
import traceback
from dataclasses import asdict, dataclass
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from experiments import transport_instantiation as ti

ACTIONS = np.asarray([-1.0, 1.0])  # index order is the tie-break order (smallest index wins)
CONSTRUCTIONS = ("frozen", "naive", "endpoint")
ENVELOPES = ("sharp", "original")
CHECKPOINTS = (1, 2, 10, 100, 1000, 4096, 8192, 8193)
RESERVED = ((30000, 30249), (41200, 41249))


@dataclass(frozen=True)
class ModelClass:
    """Declared constants available to the learner.  No teacher here."""

    width: float = 6.25
    radius: float = 1.0
    ridge: float = 1.0
    sigma: float = 0.25
    delta: float = 0.05
    block: int = 8192
    link: str = "tanh"  # "linear" gives the explicit linear-model limit

    @property
    def horizon(self) -> int:
        return self.block + 1


def h(u, model: ModelClass):
    if model.link == "linear":
        return np.asarray(u, dtype=float) * 1.0
    scale = math.sqrt(model.width)
    return scale * np.tanh(np.asarray(u, dtype=float) / scale)


def dh(u, model: ModelClass):
    if model.link == "linear":
        return np.ones_like(np.asarray(u, dtype=float))
    return 1.0 - np.tanh(np.asarray(u, dtype=float) / math.sqrt(model.width)) ** 2


def remainder(v, x, model: ModelClass):
    """Signed Taylor remainder h(v) - h(x) - h'(x)(v - x)."""
    return h(v, model) - h(x, model) - dh(x, model) * (v - x)


def sharp_envelope(x, a, model: ModelClass):
    """New certified-envelope variant: sup_{|v| <= a} |h(v) - h(x) - h'(x)(v - x)|.

    ``x = phi^T theta`` and ``a = R ||phi||``; requires |x| <= a (current parameter in
    the radius-R ball).  The signed remainder has derivative h'(v) - h'(x), which
    vanishes only at v = +-x because h' = sech^2 is even and strictly decreasing in
    |v|.  So its extrema over [-a, a] lie in {-a, a, -x, x}.  phi = 0 gives a = 0.
    """
    x, a = np.broadcast_arrays(np.asarray(x, dtype=float), np.asarray(a, dtype=float))
    if np.any(np.abs(x) > a * (1.0 + 1e-12) + 1e-15):
        raise ValueError("sharp_envelope needs |x| <= a: parameter outside the certified region")
    values = np.max(np.abs(np.stack([remainder(v, x, model) for v in (-a, a, -x, x)])), axis=0)
    return np.where(a == 0.0, 0.0, values)


def original_envelope(theta_norm, feature_norm, model: ModelClass):
    """The manuscript's envelope 0.5 (c_h / sqrt W) (R + ||theta||)^2 (experiments/transport_instantiation.py)."""
    if model.link == "linear":
        return np.zeros_like(np.asarray(theta_norm, dtype=float))
    lip = ti.smoothness_constant(float(feature_norm)) / math.sqrt(model.width)
    return 0.5 * lip * (model.radius + np.asarray(theta_norm, dtype=float)) ** 2


class Learner:
    """Sees only the declared model class, its own actions and their rewards."""

    def __init__(self, model: ModelClass):
        self.model = model
        self.theta = model.radius  # held at R during the block
        self.vbar = model.ridge  # reference matrix (1x1), rank-one accumulated
        self.rhs = 0.0
        self.energy = {e: 0.0 for e in ENVELOPES}
        size = model.block
        self.n = 0
        self._phis, self._thetas, self._queries = np.empty(size), np.empty(size), np.empty(size)
        self._pseudo, self._rewards = np.empty(size), np.empty(size)
        self._pending = None
        self.update_record = None

    phis = property(lambda self: self._phis[: self.n])
    thetas = property(lambda self: self._thetas[: self.n])
    queries = property(lambda self: self._queries[: self.n])
    pseudo = property(lambda self: self._pseudo[: self.n])
    rewards = property(lambda self: self._rewards[: self.n])

    def evaluate(self) -> dict:
        """Everything the scores need, computed before this round's reward."""
        m, sigma2 = self.model, self.model.sigma ** 2
        x = ACTIONS * self.theta
        mu = h(x, m)
        q = dh(x, m) * ACTIONS  # current queries
        theta_hat = self.rhs / self.vbar
        center = mu + q * (theta_hat - self.theta)  # corrected center
        phis = self.phis
        vcur = m.ridge + float(np.sum((dh(phis * self.theta, m) * phis) ** 2)) / sigma2  # dense replay
        # Sufficient statistics: counts of each feature value.
        counts = np.asarray([np.sum(phis == a) for a in ACTIONS], dtype=float)
        vcur_suff = m.ridge + float(np.sum(counts * (dh(ACTIONS * self.theta, m) * ACTIONS) ** 2)) / sigma2
        vbar_dense = m.ridge + float(np.sum(np.square(self.queries))) / sigma2
        gamma = math.log(self.vbar / m.ridge)
        stat = math.sqrt(gamma + 2.0 * math.log(1.0 / m.delta)) + math.sqrt(m.ridge) * m.radius
        beta = {e: stat + math.sqrt(self.energy[e]) / m.sigma for e in ENVELOPES}
        bias = {"sharp": sharp_envelope(x, m.radius * np.abs(ACTIONS), m),
                "original": np.full(2, original_envelope(abs(self.theta), 1.0, m))}
        record = {
            "theta": self.theta, "center": center, "q": q,
            "sbar": np.abs(q) / math.sqrt(self.vbar), "s": np.abs(q) / math.sqrt(vcur),
            "d_th": abs(math.log(vcur / self.vbar)), "vbar": self.vbar, "vcur": vcur, "gamma": gamma,
            "beta_sharp": beta["sharp"], "beta_original": beta["original"],
            "b_sharp": bias["sharp"], "b_original": bias["original"],
            "vcur_suff_rel": abs(vcur_suff - vcur) / vcur, "vbar_dense_rel": abs(vbar_dense - self.vbar) / self.vbar,
        }
        self._pending = (mu, q, bias)
        return record

    def observe(self, k: int, reward: float) -> None:
        mu, q, bias = self._pending
        self._pending = None
        sigma2 = self.model.sigma ** 2
        y = reward - mu[k] + q[k] * self.theta  # pseudo-response at collection time
        n = self.n
        self._phis[n], self._thetas[n], self._queries[n] = ACTIONS[k], self.theta, q[k]
        self._pseudo[n], self._rewards[n] = y, reward
        self.n = n + 1
        self.vbar += q[k] ** 2 / sigma2
        self.rhs += q[k] * y / sigma2
        for e in ENVELOPES:  # historical envelope = this round's pre-reward allowance at a_s
            self.energy[e] += float(bias[e][k]) ** 2

    def delayed_update(self) -> None:
        """One projected batch gradient step of L(theta) = (1/2n) sum (h(phi theta) - r)^2 at theta = R."""
        m = self.model
        if self.theta != m.radius:
            raise RuntimeError("the delayed update starts from theta = R")
        phis, rewards, R = self.phis, self.rewards, m.radius
        grad = float(np.mean((h(phis * R, m) - rewards) * dh(phis * R, m) * phis))
        closed = float(dh(R, m) * (h(R, m) - np.mean(phis * rewards)))  # uses h odd, h' even, phi^2 = 1
        eta = R / (2.0 * float(h(R, m)) * float(dh(R, m)))
        raw = R - eta * grad
        self.theta = float(np.clip(raw, -R, R))
        self.update_record = {"gradient": grad, "closed_form_gradient": closed, "eta": eta,
                              "raw_theta": raw, "theta_new": self.theta, "projected": raw != self.theta}


def noise_table(seed: int, model: ModelClass) -> np.ndarray:
    rng = np.random.default_rng(ti.derive_child_seed(seed, "relin_coverage/noise"))
    return rng.normal(0.0, model.sigma, size=(model.block, len(ACTIONS)))  # potential outcomes


def run_seed(seed: int, model: ModelClass, teacher: float, *, noise: np.ndarray | None = None) -> dict:
    """One frozen-reference behavior trajectory with all constructions scored on each prefix."""
    if noise is None:
        noise = noise_table(seed, model)
    if abs(teacher) > model.radius:
        raise ValueError("the teacher must lie in the known region")
    mu_star = h(ACTIONS * teacher, model)  # evaluator only
    T, start = model.horizon, time.perf_counter()
    learner = Learner(model)
    keys = ("theta", "d_th", "vbar", "vcur", "gamma", "beta_sharp", "beta_original", "vcur_suff_rel", "vbar_dense_rel")
    pair_keys = ("center", "q", "sbar", "s", "b_sharp", "b_original")
    rec = {k: np.empty(T) for k in keys} | {k: np.empty((T, 2)) for k in pair_keys}
    rec |= {"action": np.empty(T, dtype=np.int64), "reward": np.full(T, np.nan),
            "remainder_current": np.empty((T, 2)), "argmax_agree": np.empty((T, 4), dtype=bool)}
    for t in range(T):
        r = learner.evaluate()
        for k in keys + pair_keys:
            rec[k][t] = r[k]
        widths = {"frozen": r["sbar"], "naive": r["s"], "endpoint": math.exp(0.5 * r["d_th"]) * r["s"]}
        scores = {(c, e): r["center"] + r[f"beta_{e}"] * widths[c] + r[f"b_{e}"] for c in CONSTRUCTIONS for e in ENVELOPES}
        k = int(np.argmax(scores[("frozen", "sharp")]))  # behavior policy; argmax returns the smallest index
        rec["action"][t] = k
        rec["argmax_agree"][t] = [int(np.argmax(scores[c])) == k for c in
                                  (("naive", "sharp"), ("endpoint", "sharp"), ("frozen", "original"), ("naive", "original"))]
        # Evaluator-side check of the current allowance against the realized teacher remainder.
        rec["remainder_current"][t] = np.abs(remainder(ACTIONS * teacher, ACTIONS * r["theta"], model))
        if t < model.block:
            reward = float(mu_star[k] + noise[t, k])  # only the selected potential outcome is revealed
            rec["reward"][t] = reward
            learner.observe(k, reward)
            if t == model.block - 1:
                learner.delayed_update()
    stored_q = dh(learner.phis * learner.thetas, model) * learner.phis
    meta = {
        "seed": seed, "model": asdict(model), "teacher": teacher, "mu_star": mu_star.tolist(),
        "update": learner.update_record, "runtime_seconds": time.perf_counter() - start,
        "max_stored_query_recompute_error": float(np.max(np.abs(stored_q - learner.queries))),
        "thompson_scipy_checks": [
            [t, float(rec["d_th"][t - 1]), ti.thompson_distance([[rec["vbar"][t - 1]]], [[rec["vcur"][t - 1]]])[0]]
            for t in CHECKPOINTS if t <= T],
    }
    return {"meta": meta, "records": rec | {"mu_star": np.broadcast_to(mu_star, (T, 2)).copy()}}


def write_seed(result: dict, out: Path, phase: str) -> None:
    seed = result["meta"]["seed"]
    np.savez_compressed(out / f"seed_{seed}.npz", **result["records"])
    (out / f"seed_{seed}.json").write_text(json.dumps(result["meta"] | {"phase": phase}, indent=1, sort_keys=True) + "\n")


def _job(args):
    seed, model, teacher, out, phase, deterministic = args
    try:
        noise = np.zeros((model.block, 2)) if deterministic else None
        write_seed(run_seed(seed, model, teacher, noise=noise), out, phase)
        return seed, None
    except Exception:
        tb = traceback.format_exc()
        (out / f"seed_{seed}.crash.json").write_text(json.dumps(
            {"seed": seed, "model": asdict(model), "teacher": teacher, "phase": phase, "crashed": True,
             "traceback": tb}) + "\n")
        return seed, tb


def parse_seeds(text: str) -> list[int]:
    lo, _, hi = text.partition("-")
    seeds = list(range(int(lo), int(hi or lo) + 1))
    if not seeds or any(a <= s <= b for s in seeds for a, b in RESERVED):
        raise SystemExit(f"invalid or reserved seed range {text!r}")
    return seeds


def provenance(root: Path, files: tuple[str, ...]) -> dict:
    git = lambda *a: subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True).stdout.strip()
    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain", "--", "experiments")),
            "source_sha256": {f: hashlib.sha256((root / f).read_bytes()).hexdigest() for f in files},
            "numpy": np.__version__}


def manifest_key(manifest: dict) -> tuple:
    """Fields that every manifest in one run directory must share (seeds, workers and paths may differ)."""
    argv = {k: v for k, v in manifest["argv"].items() if k not in ("seeds", "workers", "output", "protocol")}
    return argv, manifest.get("model"), manifest["source_sha256"], manifest.get("protocol_sha256")


def write_manifest(output: Path, manifest: dict) -> None:
    """Refuse to resume into a directory written with another configuration, source or protocol."""
    for path in sorted(output.glob("manifest_*.json")):
        if manifest_key(json.loads(path.read_text())) != manifest_key(manifest):
            raise SystemExit(f"{path} records a different configuration, source or protocol; use a new output directory")
    (output / f"manifest_{time.time_ns()}.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")


def resume_done(stem: Path, expected: dict) -> bool:
    """True if this run already has a complete record written with `expected`; refuse partial or mismatched ones."""
    for suffix, companion in ((".json", ".npz"), (".crash.json", None)):
        path = Path(f"{stem}{suffix}")
        if not path.exists():
            continue
        if companion and not Path(f"{stem}{companion}").exists():
            raise SystemExit(f"{path} has no {companion}; remove it and rerun")
        recorded = json.loads(path.read_text())
        diff = {k: (recorded.get(k), v) for k, v in expected.items() if recorded.get(k) != v}
        if diff:
            raise SystemExit(f"{path} was written with a different configuration (recorded, current): {diff}")
        return True
    return False


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--phase", required=True, choices=("deterministic", "development", "evaluation"))
    p.add_argument("--seeds", default="0")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--block", type=int, default=ModelClass.block)
    p.add_argument("--width", type=float, default=ModelClass.width)
    p.add_argument("--teacher", type=float, default=-1.0)
    p.add_argument("--protocol", type=Path, help="frozen protocol file; its sha256 is recorded")
    args = p.parse_args()
    if args.phase == "evaluation" and args.protocol is None:
        p.error("evaluation requires --protocol")
    model = ModelClass(width=args.width, block=args.block)
    args.output.mkdir(parents=True, exist_ok=True)  # existing per-seed outputs are kept (checkpoint resume)
    root = Path(__file__).resolve().parents[1]
    manifest = {"argv": {k: str(v) for k, v in vars(args).items()}, "model": asdict(model),
                **provenance(root, ("experiments/relin_coverage.py", "experiments/transport_instantiation.py"))}
    if args.protocol:
        manifest["protocol_sha256"] = hashlib.sha256(args.protocol.read_bytes()).hexdigest()
    write_manifest(args.output, manifest)
    seeds = [0] if args.phase == "deterministic" else parse_seeds(args.seeds)
    todo = [s for s in seeds if not resume_done(args.output / f"seed_{s}", {
        "seed": s, "model": asdict(model), "teacher": args.teacher, "phase": args.phase})]
    jobs = [(s, model, args.teacher, args.output, args.phase, args.phase == "deterministic") for s in todo]
    start = time.perf_counter()
    with Pool(args.workers) as pool:
        for seed, tb in pool.imap_unordered(_job, jobs):
            print(f"seed {seed}: {'CRASH' if tb else 'ok'}", flush=True)
    print(f"{len(todo)} seeds in {time.perf_counter() - start:.1f}s wall", flush=True)


if __name__ == "__main__":
    main()
