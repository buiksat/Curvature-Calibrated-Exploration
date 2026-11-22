"""Figures for the relinearization coverage study, from the analysis CSV/JSON outputs only.

  ~/.cce-fig-venv/bin/python experiments/plot_relin_coverage.py ANALYSIS_DIR

Needs matplotlib, which is outside the experiment lock; it reads no run records.
"""

import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


def _rows(path: Path) -> list[dict]:
    with path.open() as f:
        return list(csv.DictReader(f))


def primary_figure(analysis: Path) -> None:
    rows = _rows(analysis / "primary_seed_level.csv")
    seeds = np.arange(len(rows))
    err = np.array([float(r["center_error_T_max"]) for r in rows])
    order = np.argsort(err)
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.4), sharey=False)
    for ax, env, title in zip(axes, ("sharp", "original"), ("New certified envelope", "Manuscript's original envelope")):
        frozen = np.array([float(r[f"{env}_frozen_halfwidth_T"]) for r in rows])[order]
        endpoint = np.array([float(r[f"{env}_endpoint_halfwidth_T"]) for r in rows])[order]
        naive = np.array([float(r[f"{env}_naive_halfwidth_T"]) for r in rows])[order]
        ax.plot(seeds, frozen, color="tab:blue", lw=2.2, label="frozen reference half-width")
        ax.plot(seeds, endpoint, color="tab:green", ls="--", lw=1.2, label="endpoint transport half-width")
        ax.plot(seeds, naive, color="tab:red", ls=":", lw=1.8, label="naive current half-width")
        ax.plot(seeds, err[order], "k.", ms=2.5, label=r"$|\mu^\star-m|$ at round $n+1$")
        half_span = 0.5 * float(rows[0]["feasible_span"])
        ax.axhline(half_span, color="0.5", ls="-.", lw=0.9, label="half-width giving length = feasible span")
        ax.set_ylim(0, 1.08 * max(half_span, frozen.max()))
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("seed (sorted by center error)")
    axes[0].set_ylabel("reward units, round $n+1$")
    axes[1].legend(fontsize=7, loc="center right")
    fig.suptitle("Post-update query: center error against half-widths on identical histories "
                 "(endpoint coincides with frozen)", fontsize=9)
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(analysis / f"primary_halfwidths.{ext}", dpi=200)
    plt.close(fig)


def secondary_figure(analysis: Path) -> None:
    summary = json.loads((analysis / "secondary_summary.json").read_text())
    rows = _rows(analysis / "secondary_run_level.csv")
    for W, cell in summary["by_width"].items():
        frozen = {r["seed"]: float(r["regret"]) for r in rows if r["W"] == str(float(W)) and r["method"] == "frozen_reference"}
        fig, ax = plt.subplots(figsize=(5.0, 3.2))
        for i, (m, label) in enumerate((("naive_current", "naive current"), ("transport_endpoint", "endpoint transport"))):
            d = np.array([float(r["regret"]) - frozen[r["seed"]] for r in rows
                          if r["W"] == str(float(W)) and r["method"] == m and r["seed"] in frozen])
            jitter = np.random.default_rng(i).uniform(-0.12, 0.12, d.size)
            ax.plot(i + jitter, d, ".", ms=3, alpha=0.6, color="0.4")
            stats = cell["paired_minus_frozen"][m]
            lo, hi = stats["bootstrap95"]
            ax.errorbar(i, stats["mean"], yerr=[[stats["mean"] - lo], [hi - stats["mean"]]], fmt="o", color="tab:red",
                        capsize=4, label="mean, 95% seed bootstrap" if i == 0 else None)
        ax.axhline(0.0, color="k", lw=0.8)
        ax.set_xticks([0, 1], ["naive current", "endpoint transport"])
        ax.set_ylabel("regret minus frozen (same seed)")
        ax.set_title(f"Own-history policies, W = {W}, T = 20,000 (descriptive)", fontsize=9)
        ax.legend(fontsize=7)
        fig.tight_layout()
        for ext in ("pdf", "png"):
            fig.savefig(analysis / f"secondary_paired_W{W}.{ext}", dpi=200)
        plt.close(fig)


if __name__ == "__main__":
    target = Path(sys.argv[1])
    if (target / "primary_seed_level.csv").exists():
        primary_figure(target)
    if (target / "secondary_summary.json").exists():
        secondary_figure(target)
