"""Build validated spectral-tail aggregates, figures, and a LaTeX table."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .artifact_utils import (
    input_set_sha256,
    sha256_file,
    validate_sha256_sidecar,
    write_json_artifact,
    write_sha256_sidecar,
)
from .config import config_digest, get_seed_set, load_config
from .logging_utils import canonical_json, derive_seed
from .run_spectral_tail_study import Cell, validate_study_config


FloatArray = NDArray[np.float64]

METHOD_LABELS = {
    "exact_dense_full": "Exact dense full",
    "full_cg": "Residual-checked full CG",
    "rank_truncation": "Rank truncation",
    "diagonal": "Diagonal",
    "block_diagonal": "Block diagonal",
    "frequent_directions": "Frequent Directions",
    "greedy": "Greedy",
}
METHOD_COLORS = {
    "exact_dense_full": "#111111",
    "full_cg": "#2474B5",
    "rank_truncation": "#C43C39",
    "diagonal": "#D9822B",
    "block_diagonal": "#6B4C9A",
    "frequent_directions": "#2E8B57",
    "greedy": "#777777",
}


class SpectralTailArtifactError(ValueError):
    """Raised when raw records cannot support the requested artifacts."""


def _cells(config: Mapping[str, Any]) -> tuple[Cell, ...]:
    return tuple(
        Cell(int(rank), int(power), str(alignment))
        for rank in config["target_ranks"]
        for power in config["spectral_powers"]
        for alignment in config["gap_alignments"]
    )


def _bonus_token(bonus: float) -> str:
    return f"{bonus:.8g}".replace(".", "p")


def _run_directory(
    root: Path,
    profile: str,
    seed: int,
    cell: Cell,
    method: str,
    bonus: float,
) -> Path:
    return (
        root
        / profile
        / "evaluation"
        / f"seed-{seed}"
        / cell.token
        / method
        / f"bonus-{_bonus_token(bonus)}"
    )


def _load_json(path: Path) -> dict[str, Any]:
    validate_sha256_sidecar(path)
    try:
        value = json.loads(path.read_text(encoding="ascii"))
    except (OSError, json.JSONDecodeError) as error:
        raise SpectralTailArtifactError(f"cannot parse {path}: {error}") from error
    if not isinstance(value, dict):
        raise SpectralTailArtifactError(f"{path} is not a JSON object")
    return value


def _load_selection(
    path: Path, config: Mapping[str, Any], profile: str
) -> tuple[dict[str, float], list[dict[str, str]]]:
    value = _load_json(path)
    if (
        value.get("experiment") != "spectral_tail_study"
        or value.get("profile") != profile
        or value.get("config_digest") != config_digest(config)
        or value.get("evaluation_data_accessed") is not False
        or value.get("tuning_seeds") != list(get_seed_set(config, "tuning"))
        or value.get("evaluation_seeds") != list(get_seed_set(config, "evaluation"))
    ):
        raise SpectralTailArtifactError("selection artifact does not match the protocol")
    selected = value.get("selected_bonus")
    methods = tuple(str(method) for method in config["methods"])
    if not isinstance(selected, Mapping) or set(selected) != set(methods):
        raise SpectralTailArtifactError("selection does not cover every method")
    sidecar = path.with_name(path.name + ".sha256")
    inputs = [
        {"path": path.as_posix(), "sha256": sha256_file(path)},
        {"path": sidecar.as_posix(), "sha256": sha256_file(sidecar)},
    ]
    return {method: float(selected[method]) for method in methods}, inputs


def _load_run(
    directory: Path,
    *,
    config: Mapping[str, Any],
    profile: str,
    seed: int,
    cell: Cell,
    method: str,
    bonus: float,
) -> tuple[dict[str, Any], dict[str, FloatArray], list[dict[str, str]]]:
    manifest_path = directory / "manifest.json"
    summary_path = directory / "summary.json"
    rounds_path = directory / "rounds.npz"
    for path in (manifest_path, summary_path, rounds_path):
        if not path.is_file():
            raise SpectralTailArtifactError(f"missing raw artifact {path}")
        validate_sha256_sidecar(path)
    manifest = _load_json(manifest_path)
    summary = _load_json(summary_path)
    if (
        manifest.get("experiment") != "spectral_tail_study"
        or manifest.get("profile") != profile
        or manifest.get("phase") != "evaluation"
        or manifest.get("seed") != seed
        or manifest.get("config_digest") != config_digest(config)
        or manifest.get("rounds_sha256") != sha256_file(rounds_path)
        or manifest.get("summary_sha256") != sha256_file(summary_path)
        or summary.get("method") != method
        or summary.get("bonus") != bonus
        or summary.get("cell")
        != {
            "rank": cell.rank,
            "spectral_power": cell.spectral_power,
            "alignment": cell.alignment,
        }
    ):
        raise SpectralTailArtifactError(f"raw identity mismatch in {directory}")
    with np.load(rounds_path, allow_pickle=False) as archive:
        arrays = {name: np.asarray(archive[name]) for name in archive.files}
    rounds = int(config["rounds"])
    required = {
        "cumulative_pseudo_regret",
        "gamma",
        "spectral_tail",
        "gamma_tail",
        "relative_width_error",
        "action_disagreement",
        "tail_alignment",
        "cg_iterations",
        "cg_relative_residual",
        "cumulative_sample_cvps",
    }
    if set(arrays) < required or any(
        arrays[name].shape != (rounds,) for name in required
    ):
        raise SpectralTailArtifactError(f"round array coverage is invalid in {directory}")
    inputs = []
    for path in (manifest_path, summary_path, rounds_path):
        sidecar = path.with_name(path.name + ".sha256")
        inputs.extend(
            (
                {"path": path.as_posix(), "sha256": sha256_file(path)},
                {"path": sidecar.as_posix(), "sha256": sha256_file(sidecar)},
            )
        )
    return summary, arrays, inputs


def _percentile_interval(
    values: FloatArray, *, resamples: int, seed_parts: Sequence[object]
) -> dict[str, float | int]:
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise SpectralTailArtifactError("interval input must be a finite nonempty vector")
    rng = np.random.Generator(np.random.PCG64(derive_seed(0, *seed_parts)))
    indices = rng.integers(0, values.size, size=(resamples, values.size))
    means = np.mean(values[indices], axis=1)
    low, high = np.quantile(means, (0.025, 0.975))
    return {
        "mean": float(np.mean(values)),
        "ci95_low": float(low),
        "ci95_high": float(high),
        "n": int(values.size),
    }


def _stats_by_horizon(
    matrix: FloatArray,
    horizons: Sequence[int],
    *,
    resamples: int,
    seed_parts: Sequence[object],
) -> list[dict[str, Any]]:
    return [
        {
            "horizon": int(horizon),
            "interval": _percentile_interval(
                matrix[:, horizon - 1],
                resamples=resamples,
                seed_parts=(*seed_parts, horizon),
            ),
        }
        for horizon in horizons
    ]


def build_aggregate(
    config: dict[str, Any],
    *,
    profile: str,
    raw_root: Path,
    selection_path: Path,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    validate_study_config(config)
    selected, inputs = _load_selection(selection_path, config, profile)
    seeds = get_seed_set(config, "evaluation")
    horizons = tuple(int(horizon) for horizon in config["horizons"])
    resamples = int(config["bootstrap_resamples"])
    methods = tuple(str(method) for method in config["methods"])
    groups: list[dict[str, Any]] = []
    raw: dict[
        tuple[Cell, str], list[tuple[dict[str, Any], dict[str, FloatArray]]]
    ] = {}

    for cell in _cells(config):
        for method in methods:
            runs = []
            bonus = selected[method]
            for seed in seeds:
                directory = _run_directory(
                    raw_root, profile, seed, cell, method, bonus
                )
                summary, arrays, run_inputs = _load_run(
                    directory,
                    config=config,
                    profile=profile,
                    seed=seed,
                    cell=cell,
                    method=method,
                    bonus=bonus,
                )
                runs.append((summary, arrays))
                inputs.extend(run_inputs)
            raw[(cell, method)] = runs
            record: dict[str, Any] = {
                "cell": {
                    "rank": cell.rank,
                    "spectral_power": cell.spectral_power,
                    "alignment": cell.alignment,
                },
                "method": method,
                "selected_bonus": bonus,
                "run_count": len(runs),
                "regret": _stats_by_horizon(
                    np.stack(
                        [arrays["cumulative_pseudo_regret"] for _, arrays in runs]
                    ),
                    horizons,
                    resamples=resamples,
                    seed_parts=(profile, cell.token, method, "regret"),
                ),
            }
            for field, array_name in (
                ("gamma", "gamma"),
                ("spectral_tail", "spectral_tail"),
                ("gamma_tail", "gamma_tail"),
                ("width_error", "relative_width_error"),
                ("action_disagreement", "action_disagreement"),
                ("tail_alignment", "tail_alignment"),
                ("cg_iterations", "cg_iterations"),
                ("sample_cvps", "cumulative_sample_cvps"),
            ):
                values = np.asarray(
                    [float(arrays[array_name][-1]) for _, arrays in runs],
                    dtype=np.float64,
                )
                record[field] = _percentile_interval(
                    values,
                    resamples=resamples,
                    seed_parts=(profile, cell.token, method, field),
                )
            ratios = np.asarray(
                [
                    float(arrays["gamma_tail"][-1])
                    / max(float(arrays["gamma"][-1]), 1e-15)
                    for _, arrays in runs
                ],
                dtype=np.float64,
            )
            record["gamma_tail_ratio"] = _percentile_interval(
                ratios,
                resamples=resamples,
                seed_parts=(profile, cell.token, method, "gamma_tail_ratio"),
            )
            groups.append(record)

    paired: list[dict[str, Any]] = []
    for cell in _cells(config):
        exact = raw[(cell, "exact_dense_full")]
        for method in methods:
            if method == "exact_dense_full":
                continue
            candidate = raw[(cell, method)]
            regret_difference = np.asarray(
                [
                    float(candidate[index][1]["cumulative_pseudo_regret"][-1])
                    - float(exact[index][1]["cumulative_pseudo_regret"][-1])
                    for index in range(len(seeds))
                ],
                dtype=np.float64,
            )
            paired.append(
                {
                    "cell": {
                        "rank": cell.rank,
                        "spectral_power": cell.spectral_power,
                        "alignment": cell.alignment,
                    },
                    "method": method,
                    "terminal_regret_minus_exact": _percentile_interval(
                        regret_difference,
                        resamples=resamples,
                        seed_parts=(profile, cell.token, method, "paired_regret"),
                    ),
                }
            )

    normalized_inputs = sorted(inputs, key=lambda item: item["path"])
    aggregate = {
        "schema_version": 1,
        "experiment": "spectral_tail_study_aggregate",
        "profile": profile,
        "config_digest": config_digest(config),
        "config": config,
        "selection": selected,
        "evaluation_seeds": list(seeds),
        "evaluation_seed_count": len(seeds),
        "interval": (
            "trajectory-level percentile bootstrap over evaluation seeds; "
            "evaluation data were not used for configuration selection"
        ),
        "groups": groups,
        "paired_terminal": paired,
        "raw_inputs": normalized_inputs,
        "input_set_sha256": input_set_sha256(normalized_inputs),
    }
    return aggregate, normalized_inputs


def _group_index(
    report: Mapping[str, Any],
) -> dict[tuple[int, int, str, str], Mapping[str, Any]]:
    result = {}
    for group in report["groups"]:
        cell = group["cell"]
        key = (
            int(cell["rank"]),
            int(cell["spectral_power"]),
            str(cell["alignment"]),
            str(group["method"]),
        )
        if key in result:
            raise SpectralTailArtifactError(f"duplicate aggregate group {key}")
        result[key] = group
    return result


def _interval_arrays(
    records: Sequence[Mapping[str, Any]],
) -> tuple[FloatArray, FloatArray, FloatArray]:
    means = np.asarray([record["interval"]["mean"] for record in records])
    lows = np.asarray([record["interval"]["ci95_low"] for record in records])
    highs = np.asarray([record["interval"]["ci95_high"] for record in records])
    return means, lows, highs


def make_regret_figure(report: Mapping[str, Any], output: Path) -> None:
    import matplotlib.pyplot as plt

    config = report["config"]
    rank = int(config["figure_rank"])
    methods = tuple(str(method) for method in config["figure_methods"])
    powers = tuple(int(power) for power in config["spectral_powers"])
    alignments = tuple(str(alignment) for alignment in config["gap_alignments"])
    horizons = np.asarray(config["horizons"], dtype=np.float64)
    groups = _group_index(report)
    figure, axes = plt.subplots(
        len(alignments),
        len(powers),
        figsize=(10.2, 5.4),
        sharex=True,
        sharey=True,
    )
    axes_array = np.atleast_2d(axes)
    for row, alignment in enumerate(alignments):
        for column, power in enumerate(powers):
            axis = axes_array[row, column]
            for method in methods:
                group = groups[(rank, power, alignment, method)]
                means, lows, highs = _interval_arrays(group["regret"])
                axis.plot(
                    horizons,
                    means,
                    color=METHOD_COLORS[method],
                    linewidth=1.6,
                    label=METHOD_LABELS[method],
                )
                axis.fill_between(
                    horizons,
                    lows,
                    highs,
                    color=METHOD_COLORS[method],
                    alpha=0.12,
                    linewidth=0,
                )
            axis.set_xscale("log", base=2)
            axis.set_yscale("symlog", linthresh=0.05)
            axis.grid(alpha=0.2, linewidth=0.5)
            axis.set_title(f"$p={power}$, {alignment}-aligned", fontsize=9)
            if column == 0:
                axis.set_ylabel("Cumulative pseudo-regret")
            if row == len(alignments) - 1:
                axis.set_xlabel("Horizon")
    handles, labels = axes_array[0, 0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="upper center",
        ncol=4,
        frameon=False,
        fontsize=8,
    )
    figure.suptitle(f"Spectral-tail study ($r={rank}$)", y=0.995, fontsize=10)
    figure.tight_layout(rect=(0, 0, 1, 0.91))
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, bbox_inches="tight", metadata={"CreationDate": None})
    plt.close(figure)
    write_sha256_sidecar(output)


def make_complexity_figure(report: Mapping[str, Any], output: Path) -> None:
    import matplotlib.pyplot as plt

    config = report["config"]
    rank = int(config["figure_rank"])
    groups = _group_index(report)
    figure, axes = plt.subplots(1, 2, figsize=(7.0, 3.0))
    markers = {"head": "o", "tail": "s"}
    colors = {0: "#777777", 1: "#2474B5", 2: "#C43C39"}
    for power in config["spectral_powers"]:
        for alignment in config["gap_alignments"]:
            group = groups[(rank, int(power), str(alignment), "exact_dense_full")]
            gamma = float(group["gamma"]["mean"])
            gamma_tail = float(group["gamma_tail"]["mean"])
            tail = float(group["spectral_tail"]["mean"])
            axes[0].scatter(
                gamma,
                gamma_tail,
                marker=markers[str(alignment)],
                color=colors[int(power)],
                s=38,
                label=f"p={power}, {alignment}",
            )
            axes[1].scatter(
                tail,
                gamma_tail / max(gamma, 1e-15),
                marker=markers[str(alignment)],
                color=colors[int(power)],
                s=38,
            )
    maximum = max(axes[0].get_xlim()[1], axes[0].get_ylim()[1])
    axes[0].plot(
        [0, maximum],
        [0, maximum],
        color="#222222",
        linestyle="--",
        linewidth=0.8,
    )
    axes[0].set_xlabel(r"Realized $\gamma_T$")
    axes[0].set_ylabel(r"Tail bound $\Gamma_{\rm tail}$")
    axes[1].set_xlabel(r"Tail mass $\Delta_{T,r}$")
    axes[1].set_ylabel(r"$\Gamma_{\rm tail}/\gamma_T$")
    for axis in axes:
        axis.grid(alpha=0.2, linewidth=0.5)
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="upper center",
        ncol=3,
        frameon=False,
        fontsize=8,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.86))
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, bbox_inches="tight", metadata={"CreationDate": None})
    plt.close(figure)
    write_sha256_sidecar(output)


def make_decision_figure(report: Mapping[str, Any], output: Path) -> None:
    import matplotlib.pyplot as plt

    groups = _group_index(report)
    paired = {
        (
            int(item["cell"]["rank"]),
            int(item["cell"]["spectral_power"]),
            str(item["cell"]["alignment"]),
            str(item["method"]),
        ): item
        for item in report["paired_terminal"]
    }
    figure, axes = plt.subplots(1, 2, figsize=(7.0, 3.0))
    for rank in report["config"]["target_ranks"]:
        for power in report["config"]["spectral_powers"]:
            for alignment in report["config"]["gap_alignments"]:
                key = (int(rank), int(power), str(alignment), "rank_truncation")
                group = groups[key]
                difference = paired[key]
                x = float(group["tail_alignment"]["mean"])
                axes[0].scatter(
                    x,
                    float(group["action_disagreement"]["mean"]),
                    color=METHOD_COLORS["rank_truncation"],
                    alpha=0.75,
                    s=24,
                )
                axes[1].scatter(
                    x,
                    float(difference["terminal_regret_minus_exact"]["mean"]),
                    color=METHOD_COLORS["rank_truncation"],
                    alpha=0.75,
                    s=24,
                )
    axes[0].set_xlabel("Decision-margin tail alignment")
    axes[0].set_ylabel("Top-action disagreement")
    axes[1].set_xlabel("Decision-margin tail alignment")
    axes[1].set_ylabel("Rank truncation regret minus full")
    axes[1].axhline(0.0, color="#222222", linewidth=0.8, linestyle="--")
    for axis in axes:
        axis.grid(alpha=0.2, linewidth=0.5)
    figure.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, bbox_inches="tight", metadata={"CreationDate": None})
    plt.close(figure)
    write_sha256_sidecar(output)


def make_table(report: Mapping[str, Any], output: Path) -> None:
    groups = _group_index(report)
    rank = int(report["config"]["figure_rank"])
    methods = tuple(str(method) for method in report["config"]["figure_methods"])
    lines = [
        r"\begin{tabular}{llrrrr}",
        r"\toprule",
        r"Regime & Method & Regret & $\gamma_T$ & $\Gamma_{\rm tail}$ & Disagree \\",
        r"\midrule",
    ]
    for power in report["config"]["spectral_powers"]:
        for alignment in report["config"]["gap_alignments"]:
            for method in methods:
                group = groups[(rank, int(power), str(alignment), method)]
                regret = group["regret"][-1]["interval"]
                lines.append(
                    f"$p={power}$, {alignment} & {METHOD_LABELS[method]} & "
                    f"{regret['mean']:.3f} & {group['gamma']['mean']:.2f} & "
                    f"{group['gamma_tail']['mean']:.2f} & "
                    f"{group['action_disagreement']['mean']:.3f} \\\\"
                )
            lines.append(r"\addlinespace")
    lines.extend((r"\bottomrule", r"\end{tabular}"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="ascii")
    write_sha256_sidecar(output)


def _write_provenance(
    artifact: Path,
    *,
    inputs: Sequence[Mapping[str, str]],
    config: Mapping[str, Any],
) -> None:
    sidecar = artifact.with_name(artifact.name + ".provenance.json")
    write_json_artifact(
        sidecar,
        {
            "schema_version": 1,
            "artifact": artifact.as_posix(),
            "artifact_sha256": sha256_file(artifact),
            "input_set_sha256": input_set_sha256(inputs),
            "inputs": list(inputs),
            "generation_parameters": {
                "experiment": "spectral_tail_study",
                "config_digest": config_digest(config),
            },
        },
    )


def make_artifacts(
    config: dict[str, Any],
    *,
    profile: str,
    raw_root: Path,
    selection_path: Path,
    aggregate_path: Path,
    regret_figure: Path,
    complexity_figure: Path,
    decision_figure: Path,
    table_path: Path,
) -> dict[str, Any]:
    aggregate, inputs = build_aggregate(
        config,
        profile=profile,
        raw_root=raw_root,
        selection_path=selection_path,
    )
    write_json_artifact(aggregate_path, aggregate)
    aggregate_sidecar = aggregate_path.with_name(aggregate_path.name + ".sha256")
    aggregate_inputs = [
        {"path": aggregate_path.as_posix(), "sha256": sha256_file(aggregate_path)},
        {"path": aggregate_sidecar.as_posix(), "sha256": sha256_file(aggregate_sidecar)},
    ]
    make_regret_figure(aggregate, regret_figure)
    make_complexity_figure(aggregate, complexity_figure)
    make_decision_figure(aggregate, decision_figure)
    make_table(aggregate, table_path)
    for artifact in (regret_figure, complexity_figure, decision_figure, table_path):
        _write_provenance(artifact, inputs=aggregate_inputs, config=config)
    return {
        "profile": profile,
        "aggregate": aggregate_path.as_posix(),
        "input_set_sha256": aggregate["input_set_sha256"],
        "artifacts": [
            regret_figure.as_posix(),
            complexity_figure.as_posix(),
            decision_figure.as_posix(),
            table_path.as_posix(),
        ],
        "raw_input_count": len(inputs),
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--profile", choices=("smoke", "full"), required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--regret-figure", type=Path, required=True)
    parser.add_argument("--complexity-figure", type=Path, required=True)
    parser.add_argument("--decision-figure", type=Path, required=True)
    parser.add_argument("--table", type=Path, required=True)
    args = parser.parse_args()
    config = load_config(args.config, profile=args.profile)
    result = make_artifacts(
        config,
        profile=args.profile,
        raw_root=args.raw_root,
        selection_path=args.selection,
        aggregate_path=args.aggregate,
        regret_figure=args.regret_figure,
        complexity_figure=args.complexity_figure,
        decision_figure=args.decision_figure,
        table_path=args.table,
    )
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())


__all__ = ["build_aggregate", "make_artifacts"]
