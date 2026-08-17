"""Benchmark real torch.func GGN operators in a fetched Conda PyTorch runtime."""

from __future__ import annotations

import argparse
import datetime as dt
import math
import resource
import statistics
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .artifact_utils import write_json_artifact
from .config import config_digest, get_seed_set, load_config
from .logging_utils import canonical_json, collect_run_metadata, seed_everything
from .autodiff_ggn import (
    AutodiffGGN,
    batched_cg,
    candidate_gradients,
    exact_sample_space_reference,
    mlp_forward,
    mlp_parameter_count,
    scalar_cg,
    select_device,
    synchronize_device,
    torch_capability,
)


METHODS = (
    "separate_cg",
    "batched_cg",
    "jacobi_pcg",
    "diagonal",
    "last_layer",
    "explicit_dense_reference",
)


def validate_benchmark_config(config: Mapping[str, Any]) -> None:
    models = config.get("models")
    if not isinstance(models, Sequence) or isinstance(models, (str, bytes)) or not models:
        raise ValueError("models must be a nonempty list")
    names = []
    for model in models:
        if not isinstance(model, Mapping):
            raise ValueError("each model must be an object")
        name = str(model.get("name", ""))
        architecture = model.get("architecture")
        if not name or not isinstance(architecture, Sequence):
            raise ValueError("each model needs a name and architecture")
        if architecture[-1] != 1 or any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in architecture
        ):
            raise ValueError("architectures must have positive integers and scalar output")
        if not isinstance(model.get("dense_reference"), bool):
            raise ValueError("dense_reference must be boolean")
        names.append(name)
    if len(set(names)) != len(names):
        raise ValueError("model names must be unique")
    for key in ("buffer_sizes", "action_counts"):
        values = config.get(key)
        if not isinstance(values, Sequence) or not values or any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in values
        ):
            raise ValueError(f"{key} must contain positive integers")
    targets = tuple(float(value) for value in config["cg_targets"])
    if not targets or any(value <= 0.0 or value >= 1.0 for value in targets):
        raise ValueError("cg_targets must lie in (0, 1)")
    if tuple(config["methods"]) != METHODS:
        raise ValueError("methods must match the preregistered method order")
    if str(config["activation"]) not in {"tanh", "relu"}:
        raise ValueError("activation must be tanh or relu")
    if str(config["dtype"]) not in {"float32", "float64"}:
        raise ValueError("dtype must be float32 or float64")
    if str(config["device"]) not in {"auto", "cpu", "cuda"}:
        raise ValueError("device must be auto, cpu, or cuda")
    for key in (
        "damping",
        "noise_variance",
        "compute_cap_accelerator_hours",
        "compute_cap_cpu_hours",
    ):
        value = float(config[key])
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError(f"{key} must be finite and positive")


def _peak_host_memory_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def _reset_peak(torch: Any, device: str) -> None:
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()


def _peak_accelerator(torch: Any, device: str) -> int:
    return int(torch.cuda.max_memory_allocated()) if device == "cuda" else 0


def _timed(
    torch: Any,
    device: str,
    function: Callable[[], Any],
    *,
    warmups: int,
    repetitions: int,
) -> tuple[Any, list[float], int]:
    for _ in range(warmups):
        function()
    synchronize_device(torch, device)
    _reset_peak(torch, device)
    timings = []
    result = None
    for _ in range(repetitions):
        started = time.perf_counter()
        result = function()
        synchronize_device(torch, device)
        timings.append(time.perf_counter() - started)
    return result, timings, _peak_accelerator(torch, device)


def _streaming_diagonal(
    torch: Any,
    parameters: Any,
    inputs: Any,
    architecture: tuple[int, ...],
    activation: str,
    damping: float,
    noise_variance: float,
    chunk_size: int,
) -> Any:
    def output_one(flat: Any, sample: Any) -> Any:
        return mlp_forward(torch, flat, sample, architecture, activation)

    gradient = torch.func.grad(output_one, argnums=0)
    diagonal = torch.full_like(parameters, damping)
    sample_count = int(inputs.shape[0])
    for start in range(0, sample_count, chunk_size):
        chunk = inputs[start : start + chunk_size]
        chunk_gradients = torch.func.vmap(gradient, in_dims=(None, 0))(
            parameters, chunk
        )
        diagonal = diagonal + torch.sum(chunk_gradients * chunk_gradients, dim=0) / (
            sample_count * noise_variance
        )
        del chunk_gradients
    return diagonal.detach()


def _batched_pcg(
    torch: Any,
    operator: AutodiffGGN,
    right_hand_sides: Any,
    diagonal: Any,
    maximum_iterations: int,
    relative_tolerance: float,
) -> dict[str, Any]:
    action_count = int(right_hand_sides.shape[0])
    solutions = torch.zeros_like(right_hand_sides)
    residuals = right_hand_sides.clone()
    preconditioned = residuals / diagonal[None, :]
    directions = preconditioned.clone()
    rz = torch.sum(residuals * preconditioned, dim=1)
    thresholds = relative_tolerance * torch.linalg.vector_norm(
        right_hand_sides, dim=1
    )
    active = torch.ones(action_count, dtype=torch.bool, device=right_hand_sides.device)
    iterations = torch.zeros(
        action_count, dtype=torch.int64, device=right_hand_sides.device
    )
    for _ in range(maximum_iterations):
        indices = torch.nonzero(active, as_tuple=False).flatten()
        if int(indices.numel()) == 0:
            break
        applied = operator.matmat(directions[indices])
        curvature = torch.sum(directions[indices] * applied, dim=1)
        if bool(torch.any(curvature <= 0.0)):
            raise ArithmeticError("PCG encountered nonpositive curvature")
        old_rz = rz[indices].clone()
        steps = old_rz / curvature
        solutions[indices] += steps[:, None] * directions[indices]
        residuals[indices] -= steps[:, None] * applied
        iterations[indices] += 1
        norms = torch.linalg.vector_norm(residuals[indices], dim=1)
        converged = norms <= thresholds[indices]
        active[indices[converged]] = False
        remaining = indices[~converged]
        if int(remaining.numel()) > 0:
            new_preconditioned = residuals[remaining] / diagonal[None, :]
            next_rz = torch.sum(residuals[remaining] * new_preconditioned, dim=1)
            directions[remaining] = new_preconditioned + (
                next_rz / old_rz[~converged]
            )[:, None] * directions[remaining]
            preconditioned[remaining] = new_preconditioned
            rz[remaining] = next_rz
    explicit = right_hand_sides - operator.matmat(solutions)
    relative = torch.linalg.vector_norm(explicit, dim=1) / torch.linalg.vector_norm(
        right_hand_sides, dim=1
    )
    return {
        "solutions": solutions.detach(),
        "iterations": iterations.detach(),
        "relative_residuals": relative.detach(),
    }


def _hidden_features(
    torch: Any,
    parameters: Any,
    inputs: Any,
    architecture: tuple[int, ...],
    activation: str,
) -> Any:
    offset = 0
    values = inputs
    for layer, (input_size, output_size) in enumerate(
        zip(architecture[:-1], architecture[1:], strict=True)
    ):
        if layer + 2 == len(architecture):
            break
        count = input_size * output_size
        weights = parameters[offset : offset + count].reshape(output_size, input_size)
        offset += count
        bias = parameters[offset : offset + output_size]
        offset += output_size
        values = values @ weights.transpose(0, 1) + bias
        values = torch.tanh(values) if activation == "tanh" else torch.relu(values)
    ones = torch.ones((values.shape[0], 1), dtype=values.dtype, device=values.device)
    return torch.cat((values, ones), dim=1).detach()


def _last_layer_widths(
    torch: Any,
    history_features: Any,
    candidate_features: Any,
    damping: float,
    noise_variance: float,
) -> Any:
    sample_count = int(history_features.shape[0])
    scaled = history_features / math.sqrt(sample_count * noise_variance)
    small = torch.eye(
        sample_count, dtype=scaled.dtype, device=scaled.device
    ) + scaled @ scaled.transpose(0, 1) / damping
    projection = candidate_features @ scaled.transpose(0, 1)
    correction = torch.linalg.solve(small, projection.transpose(0, 1)).transpose(
        0, 1
    ) @ scaled
    solutions = candidate_features / damping - correction / (damping * damping)
    return torch.sum(candidate_features * solutions, dim=1).detach()


def _rank_agreement(torch: Any, values: Any, reference: Any | None) -> dict[str, Any]:
    if reference is None:
        return {"top_action_agreement": None, "complete_rank_agreement": None}
    candidate_order = torch.argsort(values, descending=True)
    reference_order = torch.argsort(reference, descending=True)
    return {
        "top_action_agreement": bool(candidate_order[0] == reference_order[0]),
        "complete_rank_agreement": bool(torch.equal(candidate_order, reference_order)),
    }


def _solver_record(
    torch: Any,
    method: str,
    result: Mapping[str, Any],
    right_hand_sides: Any,
    timings: Sequence[float],
    peak_memory: int,
    operator: AutodiffGGN,
    reference_widths: Any | None,
    reference_solutions: Any | None,
) -> dict[str, Any]:
    execution_applications = operator.equivalent_matvecs
    widths = torch.sum(right_hand_sides * result["solutions"], dim=1)
    if reference_widths is None:
        errors = None
    else:
        errors = [
            float(value)
            for value in (
                torch.abs(widths - reference_widths)
                / torch.clamp(torch.abs(reference_widths), min=1e-30)
            )
            .detach()
            .cpu()
        ]
    energy_errors = None
    diagnostic_applications = 0
    if reference_solutions is not None:
        difference = result["solutions"] - reference_solutions
        before = operator.equivalent_matvecs
        applied = operator.matmat(difference)
        diagnostic_applications = operator.equivalent_matvecs - before
        numerator = torch.sum(difference * applied, dim=1)
        denominator = torch.sum(reference_solutions * right_hand_sides, dim=1)
        energy_errors = [
            float(value)
            for value in torch.sqrt(
                torch.clamp(numerator, min=0.0)
                / torch.clamp(denominator, min=1e-30)
            )
            .detach()
            .cpu()
        ]
    raw_iterations = result["iterations"]
    iteration_values = (
        raw_iterations.cpu() if hasattr(raw_iterations, "cpu") else raw_iterations
    )
    return {
        "method": method,
        "wall_time_seconds": statistics.median(timings),
        "wall_time_repetitions_seconds": list(timings),
        "peak_accelerator_memory_bytes": peak_memory,
        "peak_host_memory_bytes": _peak_host_memory_bytes(),
        "operator_applications": execution_applications,
        "sample_cvps": execution_applications * operator.sample_count,
        "diagnostic_operator_applications": diagnostic_applications,
        "per_action_iterations": [int(value) for value in iteration_values],
        "per_action_original_relative_residual": [
            float(value) for value in result["relative_residuals"].cpu()
        ],
        "per_action_width_squared_relative_error": errors,
        "per_action_energy_relative_error": energy_errors,
        **_rank_agreement(torch, widths, reference_widths),
    }


def run_cell(
    config: Mapping[str, Any], model: Mapping[str, Any], seed: int, buffer_size: int,
    action_count: int, target: float
) -> dict[str, Any]:
    import torch

    capability = torch_capability()
    if not capability.available:
        raise RuntimeError(capability.reason or "PyTorch is unavailable")
    device, error = select_device(torch, str(config["device"]))
    if device is None:
        raise RuntimeError(error or "requested device is unavailable")
    dtype = torch.float32 if config["dtype"] == "float32" else torch.float64
    seed_everything(seed)
    torch.manual_seed(seed)
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    architecture = tuple(int(value) for value in model["architecture"])
    parameter_count = mlp_parameter_count(architecture)
    parameters = (
        torch.randn(parameter_count, generator=generator, dtype=dtype)
        / math.sqrt(float(architecture[0]))
    ).to(device)
    history = torch.randn(
        buffer_size, architecture[0], generator=generator, dtype=dtype
    ).to(device)
    candidates = torch.randn(
        action_count, architecture[0], generator=generator, dtype=dtype
    ).to(device)
    history /= torch.clamp(torch.linalg.vector_norm(history, dim=1, keepdim=True), min=1.0)
    candidates /= torch.clamp(
        torch.linalg.vector_norm(candidates, dim=1, keepdim=True), min=1.0
    )
    damping = float(config["damping"])
    noise_variance = float(config["noise_variance"])
    operator = AutodiffGGN(
        torch,
        parameters,
        history,
        architecture,
        str(config["activation"]),
        damping,
        noise_variance,
    )
    candidate_started = time.perf_counter()
    right_hand_sides = candidate_gradients(
        torch, parameters, candidates, architecture, str(config["activation"])
    )
    synchronize_device(torch, device)
    candidate_seconds = time.perf_counter() - candidate_started
    warmups = int(config["warmup_repetitions"])
    repetitions = int(config["timing_repetitions"])
    maximum_iterations = int(config["maximum_cg_iterations"])

    def scalar_call() -> dict[str, Any]:
        operator.reset_counts()
        return scalar_cg(
            torch, operator, right_hand_sides, maximum_iterations, target
        )

    scalar, scalar_times, scalar_peak = _timed(
        torch, device, scalar_call, warmups=warmups, repetitions=repetitions
    )
    scalar_counts = (operator.equivalent_matvecs, operator.sample_count)

    def batched_call() -> dict[str, Any]:
        operator.reset_counts()
        return batched_cg(
            torch, operator, right_hand_sides, maximum_iterations, target
        )

    batched, batched_times, batched_peak = _timed(
        torch, device, batched_call, warmups=warmups, repetitions=repetitions
    )
    batched_counts = (operator.equivalent_matvecs, operator.sample_count)

    diagonal, diagonal_times, diagonal_peak = _timed(
        torch,
        device,
        lambda: _streaming_diagonal(
            torch,
            parameters,
            history,
            architecture,
            str(config["activation"]),
            damping,
            noise_variance,
            int(config["diagonal_chunk_size"]),
        ),
        warmups=warmups,
        repetitions=repetitions,
    )

    def pcg_call() -> dict[str, Any]:
        operator.reset_counts()
        return _batched_pcg(
            torch,
            operator,
            right_hand_sides,
            diagonal,
            maximum_iterations,
            target,
        )

    pcg, pcg_times, pcg_peak = _timed(
        torch, device, pcg_call, warmups=warmups, repetitions=repetitions
    )
    pcg_counts = (operator.equivalent_matvecs, operator.sample_count)
    diagonal_solutions = (right_hand_sides / diagonal[None, :]).detach()
    operator.reset_counts()
    diagonal_residual = right_hand_sides - operator.matmat(diagonal_solutions)
    diagonal_relative = torch.linalg.vector_norm(diagonal_residual, dim=1) / torch.linalg.vector_norm(
        right_hand_sides, dim=1
    )

    history_last = _hidden_features(
        torch, parameters, history, architecture, str(config["activation"])
    )
    candidate_last = _hidden_features(
        torch, parameters, candidates, architecture, str(config["activation"])
    )
    last_widths, last_times, last_peak = _timed(
        torch,
        device,
        lambda: _last_layer_widths(
            torch, history_last, candidate_last, damping, noise_variance
        ),
        warmups=warmups,
        repetitions=repetitions,
    )

    reference_solutions = None
    reference_widths = None
    reference_seconds = None
    reference_peak = 0
    if bool(model["dense_reference"]):
        def reference_call() -> tuple[Any, Any]:
            jacobian = torch.func.jacrev(operator.outputs)(parameters).detach()
            return exact_sample_space_reference(
                torch, jacobian, right_hand_sides, damping, noise_variance
            )

        reference, reference_times, reference_peak = _timed(
            torch, device, reference_call, warmups=0, repetitions=1
        )
        reference_solutions, reference_widths = reference
        reference_seconds = reference_times[0]

    common = {
        "status": "completed",
        "actual_autodiff": True,
        "ggn_application": "torch.func.jvp then torch.func.vjp; torch.vmap for batches",
        "explicit_jacobian_stored_by_matrix_free_methods": False,
        "model": str(model["name"]),
        "architecture": list(architecture),
        "parameter_count": parameter_count,
        "buffer_size": buffer_size,
        "action_count": action_count,
        "cg_target_original_relative_residual": target,
        "device": device,
        "dtype": str(config["dtype"]),
        "torch_version": capability.version,
        "candidate_gradient_seconds": candidate_seconds,
    }
    operator.equivalent_matvecs = scalar_counts[0]
    records = [
        {
            **common,
            **_solver_record(
                torch,
                "separate_cg",
                scalar,
                right_hand_sides,
                scalar_times,
                scalar_peak,
                operator,
                reference_widths,
                reference_solutions,
            ),
        },
    ]
    operator.equivalent_matvecs = batched_counts[0]
    records.append(
        {
            **common,
            **_solver_record(
                torch,
                "batched_cg",
                batched,
                right_hand_sides,
                batched_times,
                batched_peak,
                operator,
                reference_widths,
                reference_solutions,
            ),
        }
    )
    operator.equivalent_matvecs = pcg_counts[0]
    records.append(
        {
            **common,
            **_solver_record(
                torch,
                "jacobi_pcg",
                pcg,
                right_hand_sides,
                pcg_times,
                pcg_peak,
                operator,
                reference_widths,
                reference_solutions,
            ),
        }
    )
    diagonal_widths = torch.sum(right_hand_sides * diagonal_solutions, dim=1)
    diagonal_energy_errors = None
    if reference_solutions is not None:
        diagonal_difference = diagonal_solutions - reference_solutions
        diagonal_applied = operator.matmat(diagonal_difference)
        diagonal_energy_errors = [
            float(value)
            for value in torch.sqrt(
                torch.clamp(
                    torch.sum(diagonal_difference * diagonal_applied, dim=1),
                    min=0.0,
                )
                / torch.clamp(
                    torch.sum(reference_solutions * right_hand_sides, dim=1),
                    min=1e-30,
                )
            )
            .cpu()
        ]
    records.append(
        {
            **common,
            "method": "diagonal",
            "wall_time_seconds": statistics.median(diagonal_times),
            "wall_time_repetitions_seconds": diagonal_times,
            "peak_accelerator_memory_bytes": diagonal_peak,
            "peak_host_memory_bytes": _peak_host_memory_bytes(),
            "operator_applications": 0,
            "sample_cvps": 0,
            "per_action_iterations": [0] * action_count,
            "per_action_original_relative_residual": [
                float(value) for value in diagonal_relative.cpu()
            ],
                "per_action_width_squared_relative_error": None
            if reference_widths is None
            else [
                float(value)
                for value in (
                    torch.abs(diagonal_widths - reference_widths)
                    / torch.clamp(torch.abs(reference_widths), min=1e-30)
                ).cpu()
            ],
            "per_action_energy_relative_error": diagonal_energy_errors,
            **_rank_agreement(torch, diagonal_widths, reference_widths),
            "diagonal_construction": "streaming per-example gradient chunks; no full m-by-d Jacobian retained",
        }
    )
    records.append(
        {
            **common,
            "method": "last_layer",
            "wall_time_seconds": statistics.median(last_times),
            "wall_time_repetitions_seconds": last_times,
            "peak_accelerator_memory_bytes": last_peak,
            "peak_host_memory_bytes": _peak_host_memory_bytes(),
            "operator_applications": 0,
            "sample_cvps": 0,
            "per_action_iterations": [0] * action_count,
            "per_action_original_relative_residual": None,
            "per_action_width_squared_relative_error": None,
            "per_action_energy_relative_error": None,
            **_rank_agreement(torch, last_widths, reference_widths),
            "last_layer_dimension": int(candidate_last.shape[1]),
        }
    )
    if reference_widths is not None:
        records.append(
            {
                **common,
                "method": "explicit_dense_reference",
                "wall_time_seconds": reference_seconds,
                "wall_time_repetitions_seconds": [reference_seconds],
                "peak_accelerator_memory_bytes": reference_peak,
                "peak_host_memory_bytes": _peak_host_memory_bytes(),
                "operator_applications": 0,
                "sample_cvps": 0,
                "per_action_iterations": [0] * action_count,
                "per_action_original_relative_residual": [0.0] * action_count,
                "per_action_width_squared_relative_error": [0.0] * action_count,
                "per_action_energy_relative_error": [0.0] * action_count,
                "top_action_agreement": True,
                "complete_rank_agreement": True,
                "explicit_jacobian_audit_only": True,
            }
        )
    else:
        records.append(
            {
                **common,
                "method": "explicit_dense_reference",
                "status": "skipped",
                "skip_reason": "preregistered infeasible for the approximately 10M-parameter model",
            }
        )
    return {"common": common, "records": records}


def run_grid(
    config: Mapping[str, Any],
    *,
    profile: str,
    seed_set: str,
    pilot: bool,
    output_root: Path,
    overwrite: bool,
) -> dict[str, Any]:
    validate_benchmark_config(config)
    import torch

    device, _ = select_device(torch, str(config["device"]))
    cap_hours = float(
        config[
            "compute_cap_accelerator_hours"
            if device == "cuda"
            else "compute_cap_cpu_hours"
        ]
    )
    started = time.perf_counter()
    seeds = get_seed_set(config, seed_set)
    buffer_sizes = config["buffer_sizes"][:1] if pilot else config["buffer_sizes"]
    action_counts = config["action_counts"][:1] if pilot else config["action_counts"]
    targets = config["cg_targets"][:1] if pilot else config["cg_targets"]
    metadata = collect_run_metadata(
        repository=Path(__file__).resolve().parents[1],
        packages=tuple(config["provenance"]["packages"]),
    )
    completed = 0
    skipped = 0
    for seed in seeds:
        for model in config["models"]:
            for buffer_size in buffer_sizes:
                for action_count in action_counts:
                    for target in targets:
                        token = (
                            f"model-{model['name']}_m-{buffer_size}_K-{action_count}_"
                            f"tol-{float(target):.0e}"
                        )
                        destination = output_root / profile / seed_set / f"seed-{seed}" / token
                        elapsed_hours = (time.perf_counter() - started) / 3600.0
                        if elapsed_hours >= cap_hours:
                            result = {
                                "status": "skipped",
                                "skip_reason": "preregistered compute cap reached",
                                "elapsed_hours": elapsed_hours,
                            }
                            skipped += 1
                        else:
                            try:
                                result = run_cell(
                                    config,
                                    model,
                                    seed,
                                    int(buffer_size),
                                    int(action_count),
                                    float(target),
                                )
                                completed += 1
                            except RuntimeError as error:
                                result = {
                                    "status": "skipped",
                                    "skip_reason": f"runtime failure: {type(error).__name__}: {error}",
                                }
                                skipped += 1
                        if destination.exists() and not overwrite:
                            raise FileExistsError(f"refusing to overwrite {destination}")
                        destination.mkdir(parents=True, exist_ok=True)
                        write_json_artifact(destination / "result.json", result)
                        write_json_artifact(
                            destination / "manifest.json",
                            {
                                "schema_version": 1,
                                "experiment": "autodiff_ggn_benchmark",
                                "profile": profile,
                                "phase": seed_set,
                                "seed": seed,
                                "cell": token,
                                "config": config,
                                "config_digest": config_digest(config),
                                "evaluation_data_used_for_selection": False,
                                "timestamp_utc": dt.datetime.now(dt.timezone.utc)
                                .isoformat()
                                .replace("+00:00", "Z"),
                                "provenance": metadata,
                            },
                        )
    return {
        "profile": profile,
        "seed_set": seed_set,
        "development_pilot": pilot,
        "device": device,
        "seeds": list(seeds),
        "completed_cells": completed,
        "skipped_cells": skipped,
        "elapsed_hours": (time.perf_counter() - started) / 3600.0,
        "compute_cap_hours": cap_hours,
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--profile", choices=("smoke", "full"), required=True)
    parser.add_argument(
        "--seed-set",
        choices=("development", "evaluation"),
        default="evaluation",
    )
    parser.add_argument(
        "--pilot",
        action="store_true",
        help="run the first buffer/action/tolerance cell for every model",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config, profile=args.profile)
    result = run_grid(
        config,
        profile=args.profile,
        seed_set=args.seed_set,
        pilot=args.pilot,
        output_root=args.output_root,
        overwrite=args.overwrite,
    )
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())


__all__ = ["METHODS", "run_cell", "run_grid", "validate_benchmark_config"]
