"""Generate deterministic TeX tables and PGFPlots inputs from the full study.

The generator accepts only a provenance-validated, complete 50-seed full
aggregate.  It deliberately emits TeX and CSV rather than depending on an
unmanaged plotting runtime.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from .aggregate_transport_instantiation import (
    AGGREGATE_EVENT,
    METHODS,
)
from .artifact_utils import (
    atomic_write_text,
    input_set_sha256,
    sha256_file,
    validate_aggregate_provenance_sidecar,
    write_json_artifact,
    write_sha256_sidecar,
)
from .config import config_digest, get_seed_set, load_config
from .logging_utils import canonical_json


METHOD_LABELS = {
    "transport_hessian": "transport Hessian",
    "transport_endpoint": "transport endpoint (dense oracle)",
    "frozen_reference": "frozen reference",
    "naive_current": "naive current (uncertified)",
}
METHOD_COLORS = {
    "transport_hessian": "blue!75!black",
    "transport_endpoint": "green!55!black",
    "frozen_reference": "orange!90!black",
    "naive_current": "red!70!black",
}


class TransportArtifactError(ValueError):
    """Raised when publication artifacts cannot be generated safely."""


DEFAULT_CONFIG = Path("experiments/configs/transport_instantiation.yaml")
PLOT_RATIO_TOLERANCE = 1e-12
MAX_CURVE_PLOT_ROUNDS = 101


def escape_tex(value: str) -> str:
    """Escape plain text for a LaTeX table cell."""

    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(character, character) for character in str(value))


def _load_full_aggregate(path: Path) -> dict[str, Any]:
    try:
        validate_aggregate_provenance_sidecar(path)
    except (OSError, ValueError) as error:
        raise TransportArtifactError(f"invalid aggregate provenance: {error}") from error
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise TransportArtifactError(f"cannot parse aggregate {path}: {error}") from error
    if not isinstance(value, dict):
        raise TransportArtifactError("aggregate must be an object")
    expected = {
        "schema_version": 1,
        "event": AGGREGATE_EVENT,
        "experiment": "transport_instantiation",
        "profile": "full",
        "publication_ready": True,
        "full_grid_complete": True,
        "all_deterministic_audits_pass": True,
        "stochastic_confidence_failures_retained": True,
        "completed_run_count": 2400,
        "expected_run_count": 2400,
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise TransportArtifactError(f"aggregate is not publication-ready: {key}")
    seeds = value.get("evaluation_seeds")
    if not isinstance(seeds, list) or len(seeds) != 50 or len(set(seeds)) != 50:
        raise TransportArtifactError("publication aggregate must contain 50 unique seeds")
    if tuple(value.get("methods", ())) != METHODS:
        raise TransportArtifactError("aggregate method set/order is not frozen")
    canonical_config = load_config(DEFAULT_CONFIG, profile="full")
    if value.get("config_digest") != config_digest(canonical_config):
        raise TransportArtifactError("aggregate is not bound to the frozen full config")
    if value.get("horizons") != [250, 500, 1000] or value.get("horizons") != canonical_config.get(
        "horizons"
    ):
        raise TransportArtifactError("aggregate horizons are not the frozen grid")
    if value.get("target_D") != [0.25, 0.5, 1.0, 2.0] or value.get(
        "target_D"
    ) != canonical_config.get("target_D"):
        raise TransportArtifactError("aggregate target-D values are not the frozen grid")
    canonical_seeds = list(get_seed_set(canonical_config, "evaluation"))
    if seeds != list(range(100, 150)) or seeds != canonical_seeds:
        raise TransportArtifactError("aggregate evaluation seeds are not the frozen split")
    selection = value.get("selected_optimizer")
    if not isinstance(selection, Mapping):
        raise TransportArtifactError("aggregate is missing the selected optimizer")
    return value


def _target_label(value: float) -> str:
    return format(float(value), ".3g")


def _target_file_token(value: float) -> str:
    return format(float(value), ".12g").replace("-", "m").replace(".", "p")


def _coverage_text(record: Mapping[str, Any]) -> str:
    estimate = 100.0 * float(record["estimate"])
    low = 100.0 * float(record["ci_low"])
    high = 100.0 * float(record["ci_high"])
    return rf"{estimate:.1f}\% [{low:.1f}, {high:.1f}]"


def _median(record: Mapping[str, Any] | None) -> str:
    return "--" if record is None else f"{float(record['median']):.3g}"


def _ratio_with_zero_count(
    record: Mapping[str, Any], ratio_name: str, zero_count_name: str
) -> str:
    return (
        f"{_median(record.get(ratio_name))} "
        rf"($n_0={int(record[zero_count_name])}$)"
    )


def _interval(record: Mapping[str, Any]) -> str:
    interval = record["bootstrap_mean_interval"]
    return (
        f"{float(record['mean']):.3g} "
        rf"[{float(interval['ci_low']):.3g}, {float(interval['ci_high']):.3g}]"
    )


def make_validity_table(aggregate: Mapping[str, Any]) -> str:
    lines = [
        "% Auto-generated by experiments.make_transport_instantiation_artifacts; do not edit.",
        r"\begin{tabular}{@{}rrrrrrrrrrr@{}}",
        r"\toprule",
        r"$D_{\rm target}$ & $T$ & $n$ & Ref. coverage (95\% CI) & "
        r"Optimism (95\% CI) & Det. fail. & Event viol. & med. $\max D_Q$ & "
        r"med. $\max d_{\rm Th}$ & med. sharp RHS & med. regret \\",
        r"\midrule",
    ]
    records = sorted(
        aggregate["validity"], key=lambda item: (float(item["target_D"]), int(item["horizon"]))
    )
    for record in records:
        lines.append(
            f"{_target_label(record['target_D'])} & {int(record['horizon'])} & "
            f"{int(record['run_count'])} & "
            f"{_coverage_text(record['reference_confidence_coverage'])} & "
            f"{_coverage_text(record['transport_optimism_coverage'])} & "
            f"{int(record['deterministic_audit_failures'])} & "
            f"{int(record['bound_violations_on_joint_event'])} & "
            f"{float(record['max_realized_D_Q']['median']):.3g} & "
            f"{float(record['max_endpoint_Thompson_distance']['median']):.3g} & "
            f"{float(record['sharp_theorem_rhs']['median']):.3g} & "
            f"{float(record['cumulative_pseudo_regret']['median']):.3g} \\\\"
        )
    lines.extend((r"\bottomrule", r"\end{tabular}", ""))
    return "\n".join(lines)


def make_performance_table(aggregate: Mapping[str, Any]) -> str:
    lines = [
        "% Auto-generated by experiments.make_transport_instantiation_artifacts; do not edit.",
        r"\begin{tabular}{@{}rllrrrr@{}}",
        r"\toprule",
        r"$D_{\rm target}$ & Method & Mean regret (bootstrap 95\% CI) & Median & IQR & "
        r"Paired $\Delta$ from Hessian (95\% CI) & Optimism (95\% CI) \\",
        r"\midrule",
    ]
    order = {method: index for index, method in enumerate(METHODS)}
    records = sorted(
        aggregate["policy_outcomes"],
        key=lambda item: (float(item["target_D"]), order[str(item["method"])]),
    )
    previous: float | None = None
    for record in records:
        target = float(record["target_D"])
        if previous is not None and target != previous:
            lines.append(r"\addlinespace")
        regret = record["cumulative_pseudo_regret"]
        difference = record["paired_difference_from_transport_hessian"]
        lines.append(
            f"{_target_label(target)} & {escape_tex(METHOD_LABELS[str(record['method'])])} & "
            f"{_interval(regret)} & {float(regret['median']):.3g} & "
            f"{float(regret['iqr']):.3g} & {_interval(difference)} & "
            f"{_coverage_text(record['simultaneous_optimism_coverage'])} \\\\"
        )
        previous = target
    lines.extend(
        (
            r"\bottomrule",
            r"\end{tabular}",
            r"% transport endpoint is a dense diagnostic oracle; naive current is uncertified.",
            "",
        )
    )
    return "\n".join(lines)


def make_tightness_table(aggregate: Mapping[str, Any]) -> str:
    lines = [
        "% Auto-generated by experiments.make_transport_instantiation_artifacts; do not edit.",
        r"\begin{tabular}{@{}rrrrrrrrrr@{}}",
        r"\toprule",
        r"$D_{\rm target}$ & $T$ & $D_Q/d_{\rm Th}$ & $D_Q/\mathcal D_{\rm quad}$ & "
        r"$\mathcal D_{\rm quad}/d_{\rm Th}$ & $e^{D_Q/2}$ & Hist. radius & Current bias & "
        r"Width/potential & Sharp/simple \\",
        r"\midrule",
    ]
    records = sorted(
        aggregate["certificate_tightness"],
        key=lambda item: (float(item["target_D"]), int(item["horizon"])),
    )
    for record in records:
        lines.append(
            f"{_target_label(record['target_D'])} & {int(record['horizon'])} & "
            f"{_ratio_with_zero_count(record, 'D_Q_over_d_Th', 'd_Th_at_or_below_ratio_tolerance_count')} & "
            f"{_ratio_with_zero_count(record, 'D_Q_over_D_path_quad', 'D_path_quad_at_or_below_ratio_tolerance_count')} & "
            f"{_ratio_with_zero_count(record, 'D_path_quad_over_d_Th', 'd_Th_at_or_below_tolerance_with_path_count')} & "
            f"{_median(record['exp_D_Q_over_2'])} & "
            f"{_median(record['historical_confidence_radius_contribution'])} & "
            f"{_median(record['current_additive_bias'])} & "
            f"{_median(record['frozen_width_sum_over_potential_upper'])} & "
            f"{_median(record['sharp_rhs_over_simple_rhs'])} \\\\"
        )
    lines.extend((r"\bottomrule", r"\end{tabular}", ""))
    return "\n".join(lines)


def _csv_text(fieldnames: Sequence[str], records: Sequence[Mapping[str, Any]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for record in records:
        row: dict[str, str] = {}
        for name in fieldnames:
            value = record[name]
            if value is None:
                row[name] = ""
            elif isinstance(value, float):
                if not math.isfinite(value):
                    raise TransportArtifactError(f"non-finite CSV value for {name}")
                row[name] = format(value, ".17g")
            else:
                row[name] = str(value)
        writer.writerow(row)
    return stream.getvalue()


def _curve_plot_rounds(
    horizon: int, *, maximum: int = MAX_CURVE_PLOT_ROUNDS
) -> tuple[int, ...]:
    """Return a deterministic endpoint-preserving round schedule."""

    if horizon < 1:
        raise TransportArtifactError("curve horizon must be positive")
    if maximum < 2:
        raise TransportArtifactError("curve plot limit must be at least two")
    if horizon <= maximum:
        return tuple(range(1, horizon + 1))
    rounds = tuple(
        1 + index * (horizon - 1) // (maximum - 1)
        for index in range(maximum)
    )
    if len(set(rounds)) != maximum or rounds[0] != 1 or rounds[-1] != horizon:
        raise TransportArtifactError("curve downsampling did not preserve endpoints")
    return rounds


def _downsample_curve_records(
    records: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Retain at most 101 exact aggregate rows per curve horizon."""

    schedules = {
        int(record["horizon"]): set(_curve_plot_rounds(int(record["horizon"])))
        for record in records
    }
    return [
        record
        for record in records
        if int(record["round"]) in schedules[int(record["horizon"])]
    ]


def _path_plot_records(
    aggregate: Mapping[str, Any], *, bin_count: int = 40
) -> list[dict[str, Any]]:
    """Bin all-round endpoint points and retain checkpoint path diagnostics."""

    source = aggregate["path_points"]
    records: list[dict[str, Any]] = []
    for target in sorted(float(value) for value in aggregate["target_D"]):
        points = [item for item in source if float(item["target_D"]) == target]
        if not points:
            raise TransportArtifactError(f"no path points for target_D={target}")
        endpoint_pairs = [
            (float(item["d_Th"]), float(item["D_Q"]))
            for item in points
            if float(item["d_Th"]) > PLOT_RATIO_TOLERANCE
            and float(item["D_Q"]) > PLOT_RATIO_TOLERANCE
        ]
        if not endpoint_pairs:
            raise TransportArtifactError(
                f"no positive path-plot points for target_D={target}"
            )
        endpoint_x = np.asarray([pair[0] for pair in endpoint_pairs])
        endpoint_y = np.asarray([pair[1] for pair in endpoint_pairs])
        path_values = [
            float(item["D_path_quad"])
            for item in points
            if item.get("D_path_quad") is not None
        ]
        positive_values = [
            float(np.min(endpoint_x)),
            float(np.max(endpoint_x)),
            float(np.min(endpoint_y)),
            float(np.max(endpoint_y)),
        ]
        positive_values.extend(value for value in path_values if value > 0.0)
        lower = 10.0 ** math.floor(math.log10(min(positive_values)))
        upper = 10.0 ** math.ceil(math.log10(max(positive_values)))
        if upper <= lower:
            upper = lower * 10.0
        edges = np.geomspace(lower, upper, bin_count + 1)
        histogram, x_edges, y_edges = np.histogram2d(
            endpoint_x,
            endpoint_y,
            bins=(edges, edges),
        )
        for x_index, y_index in np.argwhere(histogram > 0.0):
            count = int(histogram[x_index, y_index])
            records.append(
                {
                    "target_D": target,
                    "series_code": 0,
                    "x": float(
                        math.sqrt(x_edges[x_index] * x_edges[x_index + 1])
                    ),
                    "y": float(
                        math.sqrt(y_edges[y_index] * y_edges[y_index + 1])
                    ),
                    "count": count,
                    "marker_size": min(2.5, 0.25 + 0.18 * math.sqrt(count)),
                }
            )
        path_pairs = [
            (float(item["d_Th"]), float(item["D_path_quad"]))
            for item in points
            if item.get("D_path_quad") is not None
            and float(item["d_Th"]) > PLOT_RATIO_TOLERANCE
            and float(item["D_path_quad"]) > PLOT_RATIO_TOLERANCE
        ]
        path_histogram, path_x_edges, path_y_edges = np.histogram2d(
            np.asarray([pair[0] for pair in path_pairs]),
            np.asarray([pair[1] for pair in path_pairs]),
            bins=(edges, edges),
        )
        for x_index, y_index in np.argwhere(path_histogram > 0.0):
            count = int(path_histogram[x_index, y_index])
            records.append(
                {
                    "target_D": target,
                    "series_code": 1,
                    "x": float(
                        math.sqrt(
                            path_x_edges[x_index] * path_x_edges[x_index + 1]
                        )
                    ),
                    "y": float(
                        math.sqrt(
                            path_y_edges[y_index] * path_y_edges[y_index + 1]
                        )
                    ),
                    "count": count,
                    "marker_size": min(2.5, 0.25 + 0.18 * math.sqrt(count)),
                }
            )
    return records


def _figure_header() -> list[str]:
    return [
        "% Auto-generated by experiments.make_transport_instantiation_artifacts; do not edit.",
        "% Requires \\usepackage{pgfplots}, \\usepgfplotslibrary{groupplots,fillbetween}.",
        r"\begin{tikzpicture}",
    ]


def make_regret_figure_tex(
    aggregate: Mapping[str, Any], csv_names: Mapping[float, str]
) -> str:
    targets = sorted(float(value) for value in aggregate["target_D"])
    if len(targets) != 4:
        raise TransportArtifactError("regret figure expects four target-D conditions")
    lines = _figure_header()
    lines.append(
        r"\begin{groupplot}[group style={group size=2 by 2,horizontal sep=1.1cm,vertical sep=1.0cm},"
        r"width=0.47\linewidth,height=0.32\linewidth,ylabel={Cumulative pseudo-regret},"
        r"grid=major,legend style={font=\scriptsize},tick label style={font=\scriptsize},"
        r"label style={font=\small}]"
    )
    for panel, target in enumerate(targets):
        csv_name = csv_names[target]
        xlabel = r",xlabel={Round}" if panel >= 2 else ""
        lines.append(
            rf"\nextgroupplot[title={{${{D_{{\rm target}}}}={_target_label(target)}$}}{xlabel}]"
        )
        for method in METHODS:
            token = f"p{panel}_{method}"
            color = METHOD_COLORS[method]
            method_restriction = (
                rf"restrict expr to domain={{\thisrow{{method_index}}}}{{{METHODS.index(method)}:{METHODS.index(method)}}}"
            )
            lines.extend(
                (
                    rf"\addplot[name path={token}_lo,draw=none,forget plot] table[x=round,y=ci_low,col sep=comma,{method_restriction}]{{figures/{csv_name}}};",
                    rf"\addplot[name path={token}_hi,draw=none,forget plot] table[x=round,y=ci_high,col sep=comma,{method_restriction}]{{figures/{csv_name}}};",
                    rf"\addplot[draw=none,fill={color},fill opacity=0.10,forget plot] fill between[of={token}_lo and {token}_hi];",
                    rf"\addplot[{color},thick] table[x=round,y=mean,col sep=comma,{method_restriction}]{{figures/{csv_name}}};",
                )
            )
            if panel == 0:
                lines.append(rf"\addlegendentry{{{escape_tex(METHOD_LABELS[method])}}}")
    lines.extend((r"\end{groupplot}", r"\end{tikzpicture}", ""))
    return "\n".join(lines)


def make_path_figure_tex(
    aggregate: Mapping[str, Any], csv_names: Mapping[float, str]
) -> str:
    targets = sorted(float(value) for value in aggregate["target_D"])
    lines = _figure_header()
    lines.append(
        "% Log axes omit values at or below 1e-12, including the exact t=1 zeros."
    )
    lines.append(
        r"\begin{groupplot}[group style={group size=2 by 2,horizontal sep=1.1cm,vertical sep=1.0cm},"
        r"width=0.47\linewidth,height=0.32\linewidth,xmode=log,ymode=log,"
        r"log basis x=10,log basis y=10,"
        r"ylabel={Path quantity},"
        r"grid=major,unbounded coords=discard,tick label style={font=\scriptsize},label style={font=\small}]"
    )
    for panel, target in enumerate(targets):
        csv_name = csv_names[target]
        xlabel = r",xlabel={$d_{\rm Th}$}" if panel >= 2 else ""
        positive_values = [
            float(value)
            for item in aggregate["path_points"]
            if float(item["target_D"]) == target
            for value in (item["d_Th"], item["D_Q"], item.get("D_path_quad"))
            if value is not None and float(value) > PLOT_RATIO_TOLERANCE
        ]
        lower = 10.0 ** math.floor(math.log10(min(positive_values)))
        upper = 10.0 ** math.ceil(math.log10(max(positive_values)))
        if upper <= lower:
            upper = lower * 10.0
        lines.extend(
            (
                rf"\nextgroupplot[title={{${{D_{{\rm target}}}}={_target_label(target)}$}},xmin={lower:.17g},xmax={upper:.17g},ymin={lower:.17g},ymax={upper:.17g}{xlabel}]",
                rf"\addplot[scatter,only marks,mark=*,opacity=0.35,scatter/use mapped color={{draw=blue!75!black,fill=blue!75!black}},visualization depends on={{\thisrow{{marker_size}}\as\perpointmarksize}},scatter/@pre marker code/.append style={{/tikz/mark size=\perpointmarksize}},forget plot] table[x=x,y=y,meta=count,col sep=comma,restrict expr to domain={{\thisrow{{series_code}}}}{{0:0}}]{{figures/{csv_name}}};",
                rf"\addplot[scatter,only marks,mark=triangle*,opacity=0.35,scatter/use mapped color={{draw=orange!90!black,fill=orange!90!black}},visualization depends on={{\thisrow{{marker_size}}\as\perpointmarksize}},scatter/@pre marker code/.append style={{/tikz/mark size=\perpointmarksize}},forget plot] table[x=x,y=y,meta=count,col sep=comma,restrict expr to domain={{\thisrow{{series_code}}}}{{1:1}}]{{figures/{csv_name}}};",
                rf"\addplot[black,dashed,domain={lower:.17g}:{upper:.17g},samples=2] {{x}};",
            )
        )
    lines.extend((r"\end{groupplot}", r"\end{tikzpicture}", ""))
    return "\n".join(lines)


def make_bound_figure_tex(
    aggregate: Mapping[str, Any], csv_names: Mapping[float, str]
) -> str:
    targets = sorted(float(value) for value in aggregate["target_D"])
    series = (
        ("statistical_bound_component", "blue!75!black", "statistical"),
        ("historical_bound_component", "green!50!black", "historical linearization"),
        ("path_inflation_component", "orange!90!black", "path inflation"),
        ("current_bias_cumulative", "purple!70!black", "current bias"),
        ("cumulative_pseudo_regret", "black", "realized regret"),
        ("sharp_theorem_rhs", "red!70!black", "sharp RHS"),
    )
    lines = _figure_header()
    lines.append(
        r"\begin{groupplot}[group style={group size=2 by 2,horizontal sep=1.1cm,vertical sep=1.0cm},"
        r"width=0.47\linewidth,height=0.32\linewidth,ylabel={Cumulative value},"
        r"grid=major,legend style={font=\scriptsize},tick label style={font=\scriptsize},"
        r"label style={font=\small}]"
    )
    for panel, target in enumerate(targets):
        csv_name = csv_names[target]
        xlabel = r",xlabel={Round}" if panel >= 2 else ""
        lines.append(
            rf"\nextgroupplot[title={{${{D_{{\rm target}}}}={_target_label(target)}$}}{xlabel}]"
        )
        for field, color, label in series:
            style = "very thick" if field in {"cumulative_pseudo_regret", "sharp_theorem_rhs"} else "thick"
            lines.append(
                rf"\addplot[{color},{style}] table[x=round,y={field},col sep=comma]{{figures/{csv_name}}};"
            )
            if panel == 0:
                lines.append(rf"\addlegendentry{{{escape_tex(label)}}}")
    lines.extend((r"\end{groupplot}", r"\end{tikzpicture}", ""))
    return "\n".join(lines)


def _write_artifact(
    path: Path,
    text: str,
    *,
    aggregate_path: Path,
    aggregate_provenance: Path,
) -> dict[str, str]:
    atomic_write_text(path, text, encoding="ascii")
    sha_path = write_sha256_sidecar(path)
    inputs = [
        {"path": str(aggregate_path), "sha256": sha256_file(aggregate_path)},
        {
            "path": str(aggregate_provenance),
            "sha256": sha256_file(aggregate_provenance),
        },
    ]
    provenance_path = path.with_name(path.name + ".provenance.json")
    write_json_artifact(
        provenance_path,
        {
            "schema_version": 1,
            "artifact": str(path),
            "artifact_sha256": sha256_file(path),
            "inputs": inputs,
            "input_set_sha256": input_set_sha256(inputs),
            "generator": "experiments.make_transport_instantiation_artifacts",
        },
    )
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "sha256_sidecar": str(sha_path),
        "provenance": str(provenance_path),
    }


def make_artifacts(
    aggregate_path: Path,
    *,
    validity_table: Path,
    performance_table: Path,
    tightness_table: Path,
    figure_directory: Path = Path("paper/figures"),
) -> dict[str, Any]:
    aggregate = _load_full_aggregate(aggregate_path)
    aggregate_sha256 = sha256_file(aggregate_path)
    aggregate_provenance = aggregate_path.with_suffix(
        aggregate_path.suffix + ".provenance.json"
    )
    figure_directory.mkdir(parents=True, exist_ok=True)
    regret_csv = figure_directory / "transport_instantiation_regret.csv"
    path_csv = figure_directory / "transport_instantiation_tightness.csv"
    bound_csv = figure_directory / "transport_instantiation_bound.csv"
    regret_tex = figure_directory / "transport_instantiation_regret.tex"
    path_tex = figure_directory / "transport_instantiation_tightness.tex"
    bound_tex = figure_directory / "transport_instantiation_bound.tex"
    targets = sorted(float(value) for value in aggregate["target_D"])
    regret_panel_csv = {
        target: figure_directory
        / f"transport_instantiation_regret_D-{_target_file_token(target)}.csv"
        for target in targets
    }
    path_panel_csv = {
        target: figure_directory
        / f"transport_instantiation_tightness_D-{_target_file_token(target)}.csv"
        for target in targets
    }
    bound_panel_csv = {
        target: figure_directory
        / f"transport_instantiation_bound_D-{_target_file_token(target)}.csv"
        for target in targets
    }

    regret_records = sorted(
        _downsample_curve_records(aggregate["regret_curves"]),
        key=lambda item: (float(item["target_D"]), METHODS.index(str(item["method"])), int(item["round"])),
    )
    path_records = sorted(
        aggregate["path_points"],
        key=lambda item: (
            float(item["target_D"]),
            int(item["horizon"]),
            int(item["seed"]),
            int(item["round"]),
        ),
    )
    bound_records = sorted(
        _downsample_curve_records(aggregate["bound_decomposition"]),
        key=lambda item: (float(item["target_D"]), int(item["round"])),
    )
    if not regret_records or not path_records or not bound_records:
        raise TransportArtifactError("aggregate is missing required figure data")
    regret_csv_records = [
        {
            **record,
            "method_index": METHODS.index(str(record["method"])),
            "aggregate_sha256": aggregate_sha256,
        }
        for record in regret_records
    ]
    path_csv_records = [
        {**record, "aggregate_sha256": aggregate_sha256}
        for record in _path_plot_records(aggregate)
    ]
    bound_csv_records = [
        {**record, "aggregate_sha256": aggregate_sha256} for record in bound_records
    ]
    source_comment = f"% Source aggregate SHA-256: {aggregate_sha256}\n"

    artifacts = [
        _write_artifact(
            validity_table,
            source_comment + make_validity_table(aggregate),
            aggregate_path=aggregate_path,
            aggregate_provenance=aggregate_provenance,
        ),
        _write_artifact(
            performance_table,
            source_comment + make_performance_table(aggregate),
            aggregate_path=aggregate_path,
            aggregate_provenance=aggregate_provenance,
        ),
        _write_artifact(
            tightness_table,
            source_comment + make_tightness_table(aggregate),
            aggregate_path=aggregate_path,
            aggregate_provenance=aggregate_provenance,
        ),
        _write_artifact(
            regret_csv,
            _csv_text(
                (
                    "target_D",
                    "horizon",
                    "method",
                    "method_index",
                    "round",
                    "mean",
                    "ci_low",
                    "ci_high",
                    "aggregate_sha256",
                ),
                regret_csv_records,
            ),
            aggregate_path=aggregate_path,
            aggregate_provenance=aggregate_provenance,
        ),
        _write_artifact(
            path_csv,
            _csv_text(
                (
                    "target_D",
                    "series_code",
                    "x",
                    "y",
                    "count",
                    "marker_size",
                    "aggregate_sha256",
                ),
                path_csv_records,
            ),
            aggregate_path=aggregate_path,
            aggregate_provenance=aggregate_provenance,
        ),
        _write_artifact(
            bound_csv,
            _csv_text(
                (
                    "target_D",
                    "horizon",
                    "round",
                    "statistical_bound_component",
                    "historical_bound_component",
                    "path_inflation_component",
                    "current_bias_cumulative",
                    "cumulative_pseudo_regret",
                    "sharp_theorem_rhs",
                    "aggregate_sha256",
                ),
                bound_csv_records,
            ),
            aggregate_path=aggregate_path,
            aggregate_provenance=aggregate_provenance,
        ),
    ]
    for target in targets:
        artifacts.append(
            _write_artifact(
                regret_panel_csv[target],
                _csv_text(
                    (
                        "target_D",
                        "horizon",
                        "method",
                        "method_index",
                        "round",
                        "mean",
                        "ci_low",
                        "ci_high",
                        "aggregate_sha256",
                    ),
                    [
                        record
                        for record in regret_csv_records
                        if float(record["target_D"]) == target
                    ],
                ),
                aggregate_path=aggregate_path,
                aggregate_provenance=aggregate_provenance,
            )
        )
        artifacts.append(
            _write_artifact(
                path_panel_csv[target],
                _csv_text(
                    (
                        "target_D",
                        "series_code",
                        "x",
                        "y",
                        "count",
                        "marker_size",
                        "aggregate_sha256",
                    ),
                    [
                        record
                        for record in path_csv_records
                        if float(record["target_D"]) == target
                    ],
                ),
                aggregate_path=aggregate_path,
                aggregate_provenance=aggregate_provenance,
            )
        )
        artifacts.append(
            _write_artifact(
                bound_panel_csv[target],
                _csv_text(
                    (
                        "target_D",
                        "horizon",
                        "round",
                        "statistical_bound_component",
                        "historical_bound_component",
                        "path_inflation_component",
                        "current_bias_cumulative",
                        "cumulative_pseudo_regret",
                        "sharp_theorem_rhs",
                        "aggregate_sha256",
                    ),
                    [
                        record
                        for record in bound_csv_records
                        if float(record["target_D"]) == target
                    ],
                ),
                aggregate_path=aggregate_path,
                aggregate_provenance=aggregate_provenance,
            )
        )
    artifacts.extend(
        [
            _write_artifact(
                regret_tex,
                source_comment
                + make_regret_figure_tex(
                    aggregate,
                    {target: path.name for target, path in regret_panel_csv.items()},
                ),
                aggregate_path=aggregate_path,
                aggregate_provenance=aggregate_provenance,
            ),
            _write_artifact(
                path_tex,
                source_comment
                + make_path_figure_tex(
                    aggregate,
                    {target: path.name for target, path in path_panel_csv.items()},
                ),
                aggregate_path=aggregate_path,
                aggregate_provenance=aggregate_provenance,
            ),
            _write_artifact(
                bound_tex,
                source_comment
                + make_bound_figure_tex(
                    aggregate,
                    {target: path.name for target, path in bound_panel_csv.items()},
                ),
                aggregate_path=aggregate_path,
                aggregate_provenance=aggregate_provenance,
            ),
        ]
    )
    return {
        "schema_version": 1,
        "event": "transport_instantiation_artifacts",
        "aggregate": str(aggregate_path),
        "aggregate_sha256": aggregate_sha256,
        "profile": "full",
        "evaluation_seed_count": 50,
        "artifacts": artifacts,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--table-validity", type=Path, required=True)
    parser.add_argument("--table-performance", type=Path, required=True)
    parser.add_argument("--table-tightness", type=Path, required=True)
    parser.add_argument("--figure-directory", type=Path, default=Path("paper/figures"))
    args = parser.parse_args(argv)
    result = make_artifacts(
        args.aggregate,
        validity_table=args.table_validity,
        performance_table=args.table_performance,
        tightness_table=args.table_tightness,
        figure_directory=args.figure_directory,
    )
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "METHOD_COLORS",
    "METHOD_LABELS",
    "TransportArtifactError",
    "escape_tex",
    "main",
    "make_artifacts",
    "make_bound_figure_tex",
    "make_path_figure_tex",
    "make_performance_table",
    "make_regret_figure_tex",
    "make_tightness_table",
    "make_validity_table",
]
