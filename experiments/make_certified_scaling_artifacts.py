"""Aggregate certified-scaling records into provenance-bound paper artifacts."""

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
from .run_certified_scaling import Cell, validate_scaling_config


FloatArray = NDArray[np.float64]

METHOD_LABELS = {
    "exact_current": "Exact current",
    "full_cg": "Full CG",
    "window_q_1_2": r"Window $q=1/2$",
    "window_q_2_3": r"Window $q=2/3$",
    "window_q_1": r"Window $q=1$",
    "frozen": "Frozen",
    "diagonal": "Diagonal",
    "greedy": "Greedy",
}
METHOD_COLORS = {
    "exact_current": "#111111",
    "full_cg": "#2474B5",
    "window_q_1_2": "#2E8B57",
    "window_q_2_3": "#7A9E2A",
    "window_q_1": "#00A6A6",
    "frozen": "#6B4C9A",
    "diagonal": "#D9822B",
    "greedy": "#777777",
}
THEOREM_METHODS = {
    "exact_current",
    "full_cg",
    "window_q_1_2",
    "window_q_2_3",
    "window_q_1",
    "frozen",
}


class CertifiedScalingArtifactError(ValueError):
    """Raised when the raw grid is incomplete or inconsistent."""


def _cells(config: Mapping[str, Any]) -> tuple[Cell, ...]:
    return tuple(
        Cell(int(dimension), int(rank), int(condition))
        for dimension in config["dimensions"]
        for rank in config["effective_ranks"]
        for condition in config["condition_numbers"]
    )


def _run_directory(
    root: Path, profile: str, cell: Cell, method: str, seed: int
) -> Path:
    return root / profile / "evaluation" / cell.token / method / f"seed-{seed}"


def _load_json(path: Path) -> dict[str, Any]:
    validate_sha256_sidecar(path)
    try:
        value = json.loads(path.read_text(encoding="ascii"))
    except (OSError, json.JSONDecodeError) as error:
        raise CertifiedScalingArtifactError(f"cannot parse {path}: {error}") from error
    if not isinstance(value, dict):
        raise CertifiedScalingArtifactError(f"{path} is not a JSON object")
    return value


def _load_run(
    directory: Path,
    *,
    config: Mapping[str, Any],
    profile: str,
    seed: int,
    cell: Cell,
    method: str,
) -> tuple[dict[str, Any], dict[str, NDArray[np.generic]], list[dict[str, str]]]:
    manifest_path = directory / "manifest.json"
    summary_path = directory / "summary.json"
    rounds_path = directory / "rounds.npz"
    for path in (manifest_path, summary_path, rounds_path):
        if not path.is_file():
            raise CertifiedScalingArtifactError(f"missing raw record {path}")
        validate_sha256_sidecar(path)
    manifest = _load_json(manifest_path)
    summary = _load_json(summary_path)
    expected_cell = {
        "dimension": cell.dimension,
        "effective_rank": cell.rank,
        "condition_number": cell.condition_number,
    }
    if (
        manifest.get("experiment") != "certified_scaling"
        or manifest.get("profile") != profile
        or manifest.get("phase") != "evaluation"
        or manifest.get("seed") != seed
        or manifest.get("method") != method
        or manifest.get("config_digest") != config_digest(config)
        or manifest.get("evaluation_data_used_for_selection") is not False
        or manifest.get("rounds_sha256") != sha256_file(rounds_path)
        or manifest.get("summary_sha256") != sha256_file(summary_path)
        or summary.get("experiment") != "certified_scaling"
        or summary.get("method") != method
        or summary.get("cell") != expected_cell
    ):
        raise CertifiedScalingArtifactError(f"raw identity mismatch in {directory}")
    with np.load(rounds_path, allow_pickle=False) as archive:
        arrays = {name: np.asarray(archive[name]) for name in archive.files}
    rounds = int(config["rounds"])
    one_dimensional = {
        "cumulative_pseudo_regret",
        "Lambda_C",
        "gamma",
        "rank_information_bound",
        "H_T",
        "E_T",
        "bar_chi_t",
        "optimizer_residual",
        "excitation_required",
        "excitation_pass",
        "cumulative_sample_cvps",
        "premise_pass",
    }
    if set(arrays) < one_dimensional or any(
        arrays[name].shape != (rounds,) for name in one_dimensional
    ):
        raise CertifiedScalingArtifactError(f"round coverage is invalid in {directory}")
    if arrays.get("cg_iterations", np.empty(0)).shape != (rounds, 2):
        raise CertifiedScalingArtifactError(f"CG coverage is invalid in {directory}")
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


def _interval(
    values: FloatArray, *, resamples: int, seed_parts: Sequence[object]
) -> dict[str, float | int]:
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise CertifiedScalingArtifactError("interval input is not a finite vector")
    rng = np.random.Generator(np.random.PCG64(derive_seed(0, *seed_parts)))
    indices = rng.integers(0, values.size, size=(resamples, values.size))
    bootstrap = np.mean(values[indices], axis=1)
    low, high = np.quantile(bootstrap, (0.025, 0.975))
    return {
        "mean": float(np.mean(values)),
        "ci95_low": float(low),
        "ci95_high": float(high),
        "n": int(values.size),
    }


def _slope(values: FloatArray, horizons: FloatArray) -> float:
    design = np.stack((np.ones(horizons.size), np.log(horizons)), axis=1)
    coefficients = np.linalg.lstsq(design, np.log1p(values), rcond=None)[0]
    return float(coefficients[1])


def build_aggregate(
    config: dict[str, Any], *, profile: str, raw_root: Path
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    validate_scaling_config(config)
    methods = tuple(str(value) for value in config["methods"])
    seeds = get_seed_set(config, "evaluation")
    horizons = np.asarray(config["horizons"], dtype=np.int64)
    resamples = int(config["bootstrap_resamples"])
    groups: list[dict[str, Any]] = []
    inputs: list[dict[str, str]] = []
    stream_digests: dict[tuple[Cell, int], str] = {}

    for cell in _cells(config):
        for method in methods:
            summaries = []
            runs = []
            for seed in seeds:
                directory = _run_directory(raw_root, profile, cell, method, seed)
                summary, arrays, run_inputs = _load_run(
                    directory,
                    config=config,
                    profile=profile,
                    seed=seed,
                    cell=cell,
                    method=method,
                )
                manifest = _load_json(directory / "manifest.json")
                digest_key = (cell, seed)
                stream_digest = str(manifest["stream_sha256"])
                if digest_key in stream_digests and stream_digests[digest_key] != stream_digest:
                    raise CertifiedScalingArtifactError(
                        f"methods used different streams for {cell.token}/seed-{seed}"
                    )
                stream_digests[digest_key] = stream_digest
                summaries.append(summary)
                runs.append(arrays)
                inputs.extend(run_inputs)

            regret_matrix = np.stack(
                [run["cumulative_pseudo_regret"] for run in runs]
            )
            work_matrix = np.stack([run["cumulative_sample_cvps"] for run in runs])
            regret_prefix = regret_matrix[:, horizons - 1]
            work_prefix = work_matrix[:, horizons - 1]
            regret_slopes = np.asarray(
                [
                    _slope(regret_prefix[index], horizons.astype(np.float64))
                    for index in range(len(seeds))
                ],
                dtype=np.float64,
            )
            work_slopes = np.asarray(
                [
                    _slope(work_prefix[index], horizons.astype(np.float64))
                    for index in range(len(seeds))
                ],
                dtype=np.float64,
            )
            groups.append(
                {
                    "cell": {
                        "dimension": cell.dimension,
                        "effective_rank": cell.rank,
                        "condition_number": cell.condition_number,
                    },
                    "method": method,
                    "run_count": len(runs),
                    "all_required_premises_pass": bool(
                        all(item["all_required_premises_pass"] for item in summaries)
                    ),
                    "premise_failure_count": int(
                        sum(
                            not bool(value)
                            for run in runs
                            for value in run["premise_pass"]
                        )
                    ),
                    "regret": [
                        {
                            "horizon": int(horizon),
                            "interval": _interval(
                                regret_matrix[:, horizon - 1],
                                resamples=resamples,
                                seed_parts=(profile, cell.token, method, "regret", horizon),
                            ),
                        }
                        for horizon in horizons
                    ],
                    "sample_cvps": [
                        {
                            "horizon": int(horizon),
                            "interval": _interval(
                                work_matrix[:, horizon - 1].astype(np.float64),
                                resamples=resamples,
                                seed_parts=(profile, cell.token, method, "work", horizon),
                            ),
                        }
                        for horizon in horizons
                    ],
                    "regret_slope_log1p": _interval(
                        regret_slopes,
                        resamples=resamples,
                        seed_parts=(profile, cell.token, method, "regret_slope"),
                    ),
                    "work_slope_log1p": _interval(
                        work_slopes,
                        resamples=resamples,
                        seed_parts=(profile, cell.token, method, "work_slope"),
                    ),
                    "terminal_Lambda_C": _interval(
                        np.asarray([run["Lambda_C"][-1] for run in runs]),
                        resamples=resamples,
                        seed_parts=(profile, cell.token, method, "Lambda_C"),
                    ),
                    "terminal_gamma": _interval(
                        np.asarray([run["gamma"][-1] for run in runs]),
                        resamples=resamples,
                        seed_parts=(profile, cell.token, method, "gamma"),
                    ),
                    "terminal_H_T": _interval(
                        np.asarray([run["H_T"][-1] for run in runs]),
                        resamples=resamples,
                        seed_parts=(profile, cell.token, method, "H_T"),
                    ),
                    "maximum_E_T": float(
                        max(float(np.max(run["E_T"])) for run in runs)
                    ),
                    "maximum_bar_chi_t": float(
                        max(float(np.max(run["bar_chi_t"])) for run in runs)
                    ),
                    "maximum_optimizer_residual": float(
                        max(float(np.max(run["optimizer_residual"])) for run in runs)
                    ),
                    "maximum_cg_energy_error": float(
                        max(float(item["maximum_cg_energy_error"]) for item in summaries)
                    ),
                    "multi_iteration_round_fraction": _interval(
                        np.asarray(
                            [item["multi_iteration_round_fraction"] for item in summaries]
                        ),
                        resamples=resamples,
                        seed_parts=(profile, cell.token, method, "multi_iteration"),
                    ),
                    "excitation_checked_rounds": int(
                        min(item["excitation_checked_rounds"] for item in summaries)
                    ),
                    "post_burnin_excitation_pass": bool(
                        all(item["post_burnin_excitation_pass"] for item in summaries)
                    ),
                }
            )

    normalized_inputs = sorted(inputs, key=lambda item: item["path"])
    report = {
        "schema_version": 1,
        "experiment": "certified_scaling_aggregate",
        "profile": profile,
        "config": config,
        "config_digest": config_digest(config),
        "evaluation_seeds": list(seeds),
        "evaluation_seed_count": len(seeds),
        "selection_protocol": config["selection_protocol"],
        "interval": "whole-trajectory percentile bootstrap over evaluation seeds",
        "slope_diagnostic": (
            "five-or-six-point OLS slope of log(1+metric) on log horizon; "
            "finite-grid diagnostic, not asymptotic rate evidence"
        ),
        "groups": groups,
        "raw_inputs": normalized_inputs,
        "input_set_sha256": input_set_sha256(normalized_inputs),
    }
    return report, normalized_inputs


def _index(
    report: Mapping[str, Any],
) -> dict[tuple[int, int, int, str], Mapping[str, Any]]:
    result = {}
    for group in report["groups"]:
        cell = group["cell"]
        key = (
            int(cell["dimension"]),
            int(cell["effective_rank"]),
            int(cell["condition_number"]),
            str(group["method"]),
        )
        result[key] = group
    return result


def _curve(records: Sequence[Mapping[str, Any]]) -> tuple[FloatArray, FloatArray, FloatArray]:
    means = np.asarray([record["interval"]["mean"] for record in records])
    lows = np.asarray([record["interval"]["ci95_low"] for record in records])
    highs = np.asarray([record["interval"]["ci95_high"] for record in records])
    return means, lows, highs


def make_figure(report: Mapping[str, Any], output: Path) -> None:
    import matplotlib.pyplot as plt

    config = report["config"]
    dimension = int(config["figure_dimension"])
    condition = int(config["figure_condition_number"])
    ranks = tuple(int(value) for value in config["effective_ranks"])
    methods = tuple(str(value) for value in config["methods"])
    horizons = np.asarray(config["horizons"], dtype=np.float64)
    groups = _index(report)
    figure, axes = plt.subplots(len(ranks), 2, figsize=(8.0, 2.35 * len(ranks)))
    axes_array = np.atleast_2d(axes)
    for row, rank in enumerate(ranks):
        status = all(
            groups[(dimension, rank, condition, method)]["all_required_premises_pass"]
            for method in methods
            if method in THEOREM_METHODS
        )
        for method in methods:
            group = groups[(dimension, rank, condition, method)]
            means, lows, highs = _curve(group["regret"])
            axes_array[row, 0].plot(
                horizons,
                means,
                color=METHOD_COLORS[method],
                linewidth=1.5,
                label=METHOD_LABELS[method],
            )
            axes_array[row, 0].fill_between(
                horizons,
                lows,
                highs,
                color=METHOD_COLORS[method],
                alpha=0.10,
                linewidth=0,
            )
            work_means, _, _ = _curve(group["sample_cvps"])
            if np.any(work_means > 0.0):
                axes_array[row, 1].plot(
                    horizons,
                    work_means,
                    color=METHOD_COLORS[method],
                    linewidth=1.5,
                    label=METHOD_LABELS[method],
                )
        axes_array[row, 0].text(
            0.02,
            0.95,
            "THEOREM PREMISES PASS" if status else "THEOREM PREMISES FAIL",
            transform=axes_array[row, 0].transAxes,
            va="top",
            fontsize=7,
            color="#176B3A" if status else "#A12A2A",
        )
        axes_array[row, 0].set_ylabel(f"$r={rank}$\nPseudo-regret")
        axes_array[row, 1].set_ylabel("Sample-CVPs")
        for axis in axes_array[row]:
            axis.set_xscale("log", base=2)
            axis.set_yscale("symlog", linthresh=1.0)
            axis.grid(alpha=0.2, linewidth=0.5)
        if row == len(ranks) - 1:
            axes_array[row, 0].set_xlabel("Horizon")
            axes_array[row, 1].set_xlabel("Horizon")
    axes_array[0, 0].set_title("Executed-policy regret", fontsize=9)
    axes_array[0, 1].set_title("Width-solve work", fontsize=9)
    handles, labels = axes_array[0, 0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper center", ncol=4, frameon=False, fontsize=8)
    figure.suptitle(
        f"Rotated cyclic scaling ($d={dimension}$, $\\kappa={condition}$)",
        y=0.995,
        fontsize=10,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.92))
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, bbox_inches="tight", metadata={"CreationDate": None})
    plt.close(figure)
    write_sha256_sidecar(output)


def make_premise_table(report: Mapping[str, Any], output: Path) -> None:
    groups = _index(report)
    methods = tuple(str(value) for value in report["config"]["methods"])
    lines = [
        r"\begin{tabular}{rrr" + "c" * len(methods) + "}",
        r"\toprule",
        "$d$ & $r$ & $\\kappa$ & "
        + " & ".join(METHOD_LABELS[method] for method in methods)
        + r" \\",
        r"\midrule",
    ]
    for cell in _cells(report["config"]):
        states = []
        for method in methods:
            group = groups[(cell.dimension, cell.rank, cell.condition_number, method)]
            if method in THEOREM_METHODS:
                states.append("PASS" if group["all_required_premises_pass"] else "FAIL")
            else:
                states.append("control")
        lines.append(
            f"{cell.dimension} & {cell.rank} & {cell.condition_number} & "
            + " & ".join(states)
            + r" \\"
        )
    lines.extend((r"\bottomrule", r"\end{tabular}"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="ascii")
    write_sha256_sidecar(output)


def make_fits_table(report: Mapping[str, Any], output: Path) -> None:
    lines: list[str] = []
    dimensions = tuple(int(value) for value in report["config"]["dimensions"])
    ranks = tuple(int(value) for value in report["config"]["effective_ranks"])
    table_index = 0
    for dimension in dimensions:
        for rank in ranks:
            table_index += 1
            lines.extend(
                (
                    r"\begin{table*}[p]",
                    r"\centering\scriptsize",
                    r"\begin{tabular}{rllrr}",
                    r"\toprule",
                    r"$\kappa$ & Method & Status & Regret slope & Work slope \\",
                    r"\midrule",
                )
            )
            for group in report["groups"]:
                cell = group["cell"]
                if (
                    int(cell["dimension"]) != dimension
                    or int(cell["effective_rank"]) != rank
                ):
                    continue
                regret = group["regret_slope_log1p"]
                work = group["work_slope_log1p"]
                status = (
                    "PASS" if group["all_required_premises_pass"] else "FAIL"
                ) if group["method"] in THEOREM_METHODS else "control"
                lines.append(
                    f"{cell['condition_number']} & {METHOD_LABELS[group['method']]} & "
                    f"{status} & {regret['mean']:.3f} & {work['mean']:.3f} \\\\"
                )
            label = (
                "tab:certified-scaling-fits"
                if table_index == 1
                else f"tab:certified-scaling-fits-{table_index}"
            )
            lines.extend(
                (
                    r"\bottomrule",
                    r"\end{tabular}",
                    (
                        f"\\caption{{Finite-grid log--log slope diagnostics for "
                        f"$d={dimension},r={rank}$.  Fits use the six prespecified "
                        "nested horizons and are not asymptotic-rate estimates.}"
                    ),
                    f"\\label{{{label}}}",
                    r"\end{table*}",
                    "",
                )
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="ascii")
    write_sha256_sidecar(output)


def _write_provenance(
    artifact: Path, aggregate_path: Path, config: Mapping[str, Any]
) -> None:
    aggregate_sidecar = aggregate_path.with_name(aggregate_path.name + ".sha256")
    inputs = [
        {"path": aggregate_path.as_posix(), "sha256": sha256_file(aggregate_path)},
        {"path": aggregate_sidecar.as_posix(), "sha256": sha256_file(aggregate_sidecar)},
    ]
    write_json_artifact(
        artifact.with_name(artifact.name + ".provenance.json"),
        {
            "schema_version": 1,
            "artifact": artifact.as_posix(),
            "artifact_sha256": sha256_file(artifact),
            "inputs": inputs,
            "input_set_sha256": input_set_sha256(inputs),
            "generation_parameters": {
                "experiment": "certified_scaling",
                "config_digest": config_digest(config),
            },
        },
    )


def make_artifacts(
    config: dict[str, Any],
    *,
    profile: str,
    raw_root: Path,
    aggregate_path: Path,
    figure_path: Path,
    premise_table_path: Path,
    fits_table_path: Path,
) -> dict[str, Any]:
    report, inputs = build_aggregate(config, profile=profile, raw_root=raw_root)
    write_json_artifact(aggregate_path, report)
    make_figure(report, figure_path)
    make_premise_table(report, premise_table_path)
    make_fits_table(report, fits_table_path)
    for artifact in (figure_path, premise_table_path, fits_table_path):
        _write_provenance(artifact, aggregate_path, config)
    return {
        "profile": profile,
        "aggregate": aggregate_path.as_posix(),
        "input_set_sha256": report["input_set_sha256"],
        "raw_input_count": len(inputs),
        "artifacts": [
            figure_path.as_posix(),
            premise_table_path.as_posix(),
            fits_table_path.as_posix(),
        ],
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--profile", choices=("smoke", "full"), required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--figure", type=Path, required=True)
    parser.add_argument("--premise-table", type=Path, required=True)
    parser.add_argument("--fits-table", type=Path, required=True)
    args = parser.parse_args()
    config = load_config(args.config, profile=args.profile)
    result = make_artifacts(
        config,
        profile=args.profile,
        raw_root=args.raw_root,
        aggregate_path=args.aggregate,
        figure_path=args.figure,
        premise_table_path=args.premise_table,
        fits_table_path=args.fits_table,
    )
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())


__all__ = ["build_aggregate", "make_artifacts"]
