"""Actual-autodiff GGN systems benchmark with an explicit not-run path.

The existing :mod:`experiments.run_systems_scaling` benchmark applies a
synthetic parameter-vector operator.  This driver is deliberately separate:
it constructs a scalar-output MLP and applies its squared-loss GGN with
``torch.func.jvp`` and ``torch.func.vjp``.  PyTorch remains optional.  When it
is unavailable (or lacks the required functional transforms), the driver
writes a machine-readable ``not_run`` artifact and performs no timing.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import resource
import statistics
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import config_digest, get_seed_set, load_config
from .logging_utils import ExperimentLogger, append_jsonl, canonical_json, seed_everything


BENCHMARK_KIND = "actual_autodiff_squared_loss_ggn_mlp"
METHODS = ("ggn_cvp", "scalar_cg", "batched_cg", "diagonal")
BUCK_TORCH_BLOCKER_REASON = (
    "Buck target fbsource//third-party/pypi/torch:torch cannot be configured "
    "from this standalone repository cell. The dependency chain through "
    "fbcode//caffe2:torch reaches "
    "fbsource//third-party/python/3.12:python-for-embedding and fails while "
    "evaluating feature_rollout_utils.bzl with 'Starlark call stack overflow'. "
    "No PyTorch timing was executed."
)


@dataclass(frozen=True)
class TorchCapability:
    available: bool
    version: str | None
    reason_code: str | None
    reason: str | None


@dataclass(frozen=True)
class AutodiffSystemsRun:
    seed: int
    status: str
    records: tuple[dict[str, Any], ...]
    summary: dict[str, Any]


def torch_capability() -> TorchCapability:
    """Return whether the required optional autodiff API can be imported."""

    if importlib.util.find_spec("torch") is None:
        return TorchCapability(
            available=False,
            version=None,
            reason_code="missing_optional_dependency",
            reason="PyTorch is not installed; no autodiff timing was executed.",
        )
    try:
        import torch
    except (ImportError, OSError) as exc:
        return TorchCapability(
            available=False,
            version=None,
            reason_code="torch_import_failed",
            reason=f"PyTorch could not be imported ({type(exc).__name__}); no timing was executed.",
        )
    func = getattr(torch, "func", None)
    missing = [
        name
        for name in ("grad", "jacrev", "jvp", "vjp", "vmap")
        if func is None or not callable(getattr(func, name, None))
    ]
    if missing:
        return TorchCapability(
            available=False,
            version=str(torch.__version__),
            reason_code="unsupported_torch_func_api",
            reason=(
                "PyTorch lacks required torch.func transforms "
                f"{missing}; no autodiff timing was executed."
            ),
        )
    return TorchCapability(
        available=True,
        version=str(torch.__version__),
        reason_code=None,
        reason=None,
    )


def mlp_parameter_count(architecture: Sequence[int]) -> int:
    """Return the exact weight-plus-bias count for a dense MLP."""

    checked = _validate_architecture(architecture)
    return sum(
        (input_size + 1) * output_size
        for input_size, output_size in zip(
            checked[:-1], checked[1:], strict=True
        )
    )


def _validate_architecture(value: Sequence[int]) -> tuple[int, ...]:
    if isinstance(value, (str, bytes)) or len(value) < 2:
        raise ValueError("architecture must contain at least input and output dimensions")
    checked: list[int] = []
    for index, dimension in enumerate(value):
        if isinstance(dimension, bool) or not isinstance(dimension, int) or dimension <= 0:
            raise ValueError(f"architecture[{index}] must be a positive integer")
        checked.append(int(dimension))
    if checked[-1] != 1:
        raise ValueError("the GGN benchmark requires a scalar-output MLP")
    return tuple(checked)


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


def _nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return int(value)


def _positive_float(value: Any, name: str) -> float:
    checked = float(value)
    if not math.isfinite(checked) or checked <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return checked


def _settings(config: Mapping[str, Any]) -> dict[str, Any]:
    architecture_raw = config.get("architecture")
    if not isinstance(architecture_raw, Sequence) or isinstance(architecture_raw, (str, bytes)):
        raise ValueError("architecture must be a sequence")
    architecture = _validate_architecture(architecture_raw)
    parameter_count = mlp_parameter_count(architecture)
    minimum = _nonnegative_int(config.get("minimum_parameter_count", 0), "minimum_parameter_count")
    if parameter_count < minimum:
        raise ValueError(
            f"architecture has {parameter_count} parameters, below required minimum {minimum}"
        )
    history_size = _positive_int(config.get("history_size"), "history_size")
    window_size = _positive_int(config.get("window_size"), "window_size")
    if window_size > history_size:
        raise ValueError("window_size must not exceed history_size")
    activation = str(config.get("activation", "tanh"))
    if activation not in {"tanh", "relu"}:
        raise ValueError("activation must be 'tanh' or 'relu'")
    dtype = str(config.get("dtype", "float32"))
    if dtype not in {"float32", "float64"}:
        raise ValueError("dtype must be 'float32' or 'float64'")
    requested_device = str(config.get("device", "auto"))
    if requested_device not in {"auto", "cpu", "cuda", "mps"}:
        raise ValueError("device must be auto, cpu, cuda, or mps")
    return {
        "architecture": architecture,
        "parameter_count": parameter_count,
        "history_size": history_size,
        "window_size": window_size,
        "action_count": _positive_int(config.get("action_count"), "action_count"),
        "cg_max_iterations": _positive_int(
            config.get("cg_max_iterations"), "cg_max_iterations"
        ),
        "cg_relative_tolerance": _positive_float(
            config.get("cg_relative_tolerance"), "cg_relative_tolerance"
        ),
        "damping": _positive_float(config.get("damping"), "damping"),
        "noise_variance": _positive_float(
            config.get("noise_variance", 1.0), "noise_variance"
        ),
        "activation": activation,
        "dtype": dtype,
        "device": requested_device,
        "warmup_repetitions": _nonnegative_int(
            config.get("warmup_repetitions", 0), "warmup_repetitions"
        ),
        "timing_repetitions": _positive_int(
            config.get("timing_repetitions", 1), "timing_repetitions"
        ),
    }


def _not_run(
    config: Mapping[str, Any],
    seed: int,
    capability: TorchCapability,
    *,
    reason_code: str | None = None,
    reason: str | None = None,
) -> AutodiffSystemsRun:
    code = reason_code or capability.reason_code or "unavailable_runtime"
    explanation = reason or capability.reason or "The requested runtime is unavailable."
    record = {
        "benchmark_kind": BENCHMARK_KIND,
        "method": "not_run",
        "status": "not_run",
        "reason_code": code,
        "reason": explanation,
        "torch_available": capability.available,
        "torch_version": capability.version,
        "timing_executed": False,
        "numerical_result_reportable": False,
    }
    summary = {
        "schema_version": 1,
        "experiment": str(config.get("name", "autodiff_systems")),
        "profile": str(config.get("profile", "unknown")),
        "seed": seed,
        "status": "not_run",
        "reason_code": code,
        "reason": explanation,
        "torch_available": capability.available,
        "torch_version": capability.version,
        "timing_executed": False,
        "numerical_result_reportable": False,
        "config_digest": config_digest(config),
    }
    return AutodiffSystemsRun(seed, "not_run", (record,), summary)


def _select_device(torch: Any, requested: str) -> tuple[str | None, str | None]:
    cuda = bool(torch.cuda.is_available())
    mps_backend = getattr(torch.backends, "mps", None)
    mps = bool(mps_backend is not None and mps_backend.is_available())
    if requested == "auto":
        return ("cuda" if cuda else "mps" if mps else "cpu"), None
    if requested == "cuda" and not cuda:
        return None, "CUDA was requested but no CUDA device is available."
    if requested == "mps" and not mps:
        return None, "MPS was requested but no MPS device is available."
    return requested, None


def _synchronize(torch: Any, device: str) -> None:
    if device == "cuda":
        torch.cuda.synchronize()
    elif device == "mps" and hasattr(torch, "mps"):
        torch.mps.synchronize()


def _peak_accelerator_memory(torch: Any, device: str) -> tuple[int | None, str]:
    if device == "cuda":
        return int(torch.cuda.max_memory_allocated()), "torch.cuda.max_memory_allocated"
    if device == "mps" and hasattr(torch, "mps"):
        return int(torch.mps.current_allocated_memory()), "torch.mps.current_allocated_memory_not_peak"
    return 0, "not_applicable_cpu"


def _reset_peak_memory(torch: Any, device: str) -> None:
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()


def _peak_host_memory_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def _mlp_forward(
    torch: Any,
    flat_parameters: Any,
    inputs: Any,
    architecture: tuple[int, ...],
    activation: str,
) -> Any:
    offset = 0
    values = inputs
    for layer, (input_size, output_size) in enumerate(
        zip(architecture[:-1], architecture[1:], strict=True)
    ):
        weight_count = input_size * output_size
        weights = flat_parameters[offset : offset + weight_count].reshape(
            output_size, input_size
        )
        offset += weight_count
        bias = flat_parameters[offset : offset + output_size]
        offset += output_size
        values = values @ weights.transpose(0, 1) + bias
        if layer + 2 < len(architecture):
            values = torch.tanh(values) if activation == "tanh" else torch.relu(values)
    if offset != flat_parameters.numel():
        raise RuntimeError("parameter unpacking did not consume the flat vector")
    return values.squeeze(-1)


class _AutodiffGGN:
    """Matrix-free ``damping I + J.T J / (n * noise_variance)``."""

    def __init__(
        self,
        torch: Any,
        parameters: Any,
        inputs: Any,
        architecture: tuple[int, ...],
        activation: str,
        damping: float,
        noise_variance: float,
    ) -> None:
        self.torch = torch
        self.parameters = parameters
        self.inputs = inputs
        self.architecture = architecture
        self.activation = activation
        self.damping = damping
        self.noise_variance = noise_variance
        self.sample_count = int(inputs.shape[0])
        self.matvec_calls = 0
        self.matmat_calls = 0
        self.equivalent_matvecs = 0

    def outputs(self, parameters: Any) -> Any:
        return _mlp_forward(
            self.torch,
            parameters,
            self.inputs,
            self.architecture,
            self.activation,
        )

    def reset_counts(self) -> None:
        self.matvec_calls = 0
        self.matmat_calls = 0
        self.equivalent_matvecs = 0

    def matvec(self, vector: Any) -> Any:
        torch = self.torch
        _, jacobian_vector = torch.func.jvp(
            self.outputs, (self.parameters,), (vector,)
        )
        _, transpose = torch.func.vjp(self.outputs, self.parameters)
        jacobian_transpose_vector = transpose(jacobian_vector)[0]
        self.matvec_calls += 1
        self.equivalent_matvecs += 1
        return (
            self.damping * vector
            + jacobian_transpose_vector / (self.sample_count * self.noise_variance)
        ).detach()

    def matmat(self, vectors: Any) -> Any:
        torch = self.torch

        def jvp_one(vector: Any) -> Any:
            return torch.func.jvp(
                self.outputs, (self.parameters,), (vector,)
            )[1]

        jacobian_vectors = torch.func.vmap(jvp_one)(vectors)
        _, transpose = torch.func.vjp(self.outputs, self.parameters)
        transpose_products = torch.func.vmap(lambda value: transpose(value)[0])(
            jacobian_vectors
        )
        batch_size = int(vectors.shape[0])
        self.matmat_calls += 1
        self.equivalent_matvecs += batch_size
        return (
            self.damping * vectors
            + transpose_products / (self.sample_count * self.noise_variance)
        ).detach()


def _candidate_gradients(
    torch: Any,
    parameters: Any,
    candidates: Any,
    architecture: tuple[int, ...],
    activation: str,
) -> Any:
    def output_one(flat: Any, candidate: Any) -> Any:
        return _mlp_forward(torch, flat, candidate, architecture, activation)

    gradient = torch.func.grad(output_one, argnums=0)
    return torch.func.vmap(gradient, in_dims=(None, 0))(
        parameters, candidates
    ).detach()


def _exact_sample_space_reference(
    torch: Any,
    jacobian: Any,
    right_hand_sides: Any,
    damping: float,
    noise_variance: float,
) -> tuple[Any, Any]:
    sample_count = int(jacobian.shape[0])
    scaled = jacobian / math.sqrt(sample_count * noise_variance)
    small = torch.eye(
        sample_count, dtype=jacobian.dtype, device=jacobian.device
    ) + (scaled @ scaled.transpose(0, 1)) / damping
    projection = right_hand_sides @ scaled.transpose(0, 1)
    correction = torch.linalg.solve(small, projection.transpose(0, 1)).transpose(
        0, 1
    ) @ scaled
    solutions = right_hand_sides / damping - correction / (damping * damping)
    widths_squared = torch.sum(right_hand_sides * solutions, dim=1)
    return solutions.detach(), widths_squared.detach()


def _scalar_cg(
    torch: Any,
    operator: _AutodiffGGN,
    right_hand_sides: Any,
    maximum_iterations: int,
    relative_tolerance: float,
) -> dict[str, Any]:
    solutions = []
    iterations: list[int] = []
    for rhs in right_hand_sides:
        solution = torch.zeros_like(rhs)
        residual = rhs.clone()
        direction = residual.clone()
        residual_squared = torch.dot(residual, residual)
        threshold = relative_tolerance * float(torch.linalg.vector_norm(rhs))
        completed = 0
        for completed in range(1, maximum_iterations + 1):
            applied = operator.matvec(direction)
            curvature = torch.dot(direction, applied)
            if float(curvature) <= 0.0:
                raise ArithmeticError("CG encountered nonpositive curvature")
            step = residual_squared / curvature
            solution = solution + step * direction
            residual = residual - step * applied
            next_squared = torch.dot(residual, residual)
            if float(torch.sqrt(next_squared)) <= threshold:
                residual_squared = next_squared
                break
            direction = residual + (next_squared / residual_squared) * direction
            residual_squared = next_squared
        solutions.append(solution.detach())
        iterations.append(completed)
    stacked = torch.stack(solutions)
    explicit = right_hand_sides - operator.matmat(stacked)
    rhs_norm = torch.linalg.vector_norm(right_hand_sides, dim=1)
    relative = torch.linalg.vector_norm(explicit, dim=1) / rhs_norm
    return {
        "solutions": stacked,
        "iterations": iterations,
        "relative_residuals": relative.detach(),
    }


def _batched_cg(
    torch: Any,
    operator: _AutodiffGGN,
    right_hand_sides: Any,
    maximum_iterations: int,
    relative_tolerance: float,
) -> dict[str, Any]:
    action_count = int(right_hand_sides.shape[0])
    solutions = torch.zeros_like(right_hand_sides)
    residuals = right_hand_sides.clone()
    directions = residuals.clone()
    residual_squared = torch.sum(residuals * residuals, dim=1)
    thresholds = relative_tolerance * torch.linalg.vector_norm(
        right_hand_sides, dim=1
    )
    active = torch.ones(action_count, dtype=torch.bool, device=right_hand_sides.device)
    iterations = torch.zeros(action_count, dtype=torch.int64, device=right_hand_sides.device)
    for _ in range(maximum_iterations):
        indices = torch.nonzero(active, as_tuple=False).flatten()
        if int(indices.numel()) == 0:
            break
        applied = operator.matmat(directions[indices])
        curvature = torch.sum(directions[indices] * applied, dim=1)
        if bool(torch.any(curvature <= 0.0)):
            raise ArithmeticError("batched CG encountered nonpositive curvature")
        old_squared = residual_squared[indices].clone()
        steps = old_squared / curvature
        solutions[indices] = solutions[indices] + steps[:, None] * directions[indices]
        residuals[indices] = residuals[indices] - steps[:, None] * applied
        next_squared = torch.sum(residuals[indices] * residuals[indices], dim=1)
        iterations[indices] += 1
        converged = torch.sqrt(next_squared) <= thresholds[indices]
        active[indices[converged]] = False
        remaining = indices[~converged]
        if int(remaining.numel()) > 0:
            remaining_next = next_squared[~converged]
            directions[remaining] = residuals[remaining] + (
                remaining_next / old_squared[~converged]
            )[:, None] * directions[remaining]
            residual_squared[remaining] = remaining_next
    explicit = right_hand_sides - operator.matmat(solutions)
    relative = torch.linalg.vector_norm(explicit, dim=1) / torch.linalg.vector_norm(
        right_hand_sides, dim=1
    )
    return {
        "solutions": solutions.detach(),
        "iterations": iterations.detach(),
        "relative_residuals": relative.detach(),
    }


def _timed(
    torch: Any,
    device: str,
    function: Callable[[], Any],
    warmups: int,
    repetitions: int,
) -> tuple[Any, list[float]]:
    for _ in range(warmups):
        function()
    _synchronize(torch, device)
    timings: list[float] = []
    result: Any = None
    for _ in range(repetitions):
        started = time.perf_counter()
        result = function()
        _synchronize(torch, device)
        timings.append(time.perf_counter() - started)
    return result, timings


def _relative_width_error(torch: Any, approximate: Any, reference: Any) -> list[float]:
    values = torch.abs(approximate - reference) / reference
    return [float(value) for value in values.detach().cpu()]


def run_autodiff_systems(
    config: Mapping[str, Any],
    seed: int,
    *,
    capability: TorchCapability | None = None,
) -> AutodiffSystemsRun:
    """Execute one seed or return an explicit, nonreportable not-run result."""

    checked = _settings(config)
    runtime = torch_capability() if capability is None else capability
    if not runtime.available:
        return _not_run(config, seed, runtime)

    import torch

    device, device_error = _select_device(torch, checked["device"])
    if device is None:
        return _not_run(
            config,
            seed,
            runtime,
            reason_code="requested_device_unavailable",
            reason=device_error,
        )
    assert device is not None
    dtype = torch.float32 if checked["dtype"] == "float32" else torch.float64
    if device == "mps" and dtype == torch.float64:
        return _not_run(
            config,
            seed,
            runtime,
            reason_code="unsupported_device_dtype",
            reason="MPS does not support the requested float64 benchmark dtype.",
        )

    seed_everything(seed)
    torch.manual_seed(seed)
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    architecture = checked["architecture"]
    parameter_count = checked["parameter_count"]
    parameters = (
        torch.randn(parameter_count, generator=generator, dtype=dtype)
        / math.sqrt(float(max(1, architecture[0])))
    ).to(device)
    history = torch.randn(
        checked["history_size"], architecture[0], generator=generator, dtype=dtype
    ).to(device)
    candidates = torch.randn(
        checked["action_count"], architecture[0], generator=generator, dtype=dtype
    ).to(device)
    history = history / torch.clamp(
        torch.linalg.vector_norm(history, dim=1, keepdim=True), min=1.0
    )
    candidates = candidates / torch.clamp(
        torch.linalg.vector_norm(candidates, dim=1, keepdim=True), min=1.0
    )

    candidate_started = time.perf_counter()
    right_hand_sides = _candidate_gradients(
        torch,
        parameters,
        candidates,
        architecture,
        checked["activation"],
    )
    _synchronize(torch, device)
    candidate_gradient_seconds = time.perf_counter() - candidate_started
    records: list[dict[str, Any]] = []

    for operator_kind, sample_inputs in (
        ("full_history", history),
        ("growing_window", history[-checked["window_size"] :]),
    ):
        operator = _AutodiffGGN(
            torch,
            parameters,
            sample_inputs,
            architecture,
            checked["activation"],
            checked["damping"],
            checked["noise_variance"],
        )
        probe = torch.ones_like(parameters) / math.sqrt(parameter_count)

        def one_cvp() -> Any:
            operator.reset_counts()
            return operator.matvec(probe)

        _reset_peak_memory(torch, device)
        cvp_result, cvp_timings = _timed(
            torch,
            device,
            one_cvp,
            checked["warmup_repetitions"],
            checked["timing_repetitions"],
        )
        accelerator_peak, accelerator_measurement = _peak_accelerator_memory(
            torch, device
        )

        # The per-example Jacobian is audit machinery. Construct it only after
        # measuring the matrix-free CVP so it cannot inflate the CVP peak.
        reference_started = time.perf_counter()
        jacobian = torch.func.jacrev(operator.outputs)(parameters).detach()
        exact_solutions, exact_widths = _exact_sample_space_reference(
            torch,
            jacobian,
            right_hand_sides,
            checked["damping"],
            checked["noise_variance"],
        )
        _synchronize(torch, device)
        reference_seconds = time.perf_counter() - reference_started
        if bool(torch.any(exact_widths <= 0.0)):
            raise FloatingPointError("sample-space reference produced a nonpositive width")
        explicit_probe = checked["damping"] * probe + (
            jacobian.transpose(0, 1) @ (jacobian @ probe)
        ) / (operator.sample_count * checked["noise_variance"])
        probe_relative_error = float(
            torch.linalg.vector_norm(cvp_result - explicit_probe)
            / torch.linalg.vector_norm(explicit_probe)
        )
        del exact_solutions, explicit_probe, jacobian
        common = {
            "benchmark_kind": BENCHMARK_KIND,
            "status": "completed",
            "actual_autodiff": True,
            "ggn_definition": "damping_I_plus_JtJ_over_n_noise_variance",
            "ggn_application": "torch_func_jvp_then_vjp",
            "operator_kind": operator_kind,
            "sample_count": operator.sample_count,
            "history_size": checked["history_size"],
            "window_size": checked["window_size"],
            "parameter_count": parameter_count,
            "architecture": list(architecture),
            "action_count": checked["action_count"],
            "dtype": checked["dtype"],
            "device": device,
            "torch_version": runtime.version,
            "damping": checked["damping"],
            "noise_variance": checked["noise_variance"],
            "candidate_gradient_seconds": candidate_gradient_seconds,
            "reference_seconds": reference_seconds,
            "reference_implementation": "exact_woodbury_sample_space_from_per_example_jacobian",
            "peak_host_memory_bytes": _peak_host_memory_bytes(),
            "peak_accelerator_memory_bytes": accelerator_peak,
            "accelerator_memory_measurement": accelerator_measurement,
            "timing_repetitions": checked["timing_repetitions"],
            "warmup_repetitions": checked["warmup_repetitions"],
        }
        records.append(
            {
                **common,
                "method": "ggn_cvp",
                "wall_time_seconds": statistics.median(cvp_timings),
                "wall_time_repetitions_seconds": cvp_timings,
                "complete_action_scoring_seconds": None,
                "operator_matvec_count": operator.equivalent_matvecs,
                "batch_operator_call_count": operator.matmat_calls,
                "sample_cvp_count": operator.equivalent_matvecs * operator.sample_count,
                "operator_probe_relative_error": probe_relative_error,
                "per_action_iterations": None,
                "per_action_explicit_relative_residual": None,
                "per_action_width_squared_relative_error": None,
            }
        )

        def scalar_call() -> dict[str, Any]:
            operator.reset_counts()
            return _scalar_cg(
                torch,
                operator,
                right_hand_sides,
                checked["cg_max_iterations"],
                checked["cg_relative_tolerance"],
            )

        _reset_peak_memory(torch, device)
        scalar, scalar_timings = _timed(
            torch,
            device,
            scalar_call,
            checked["warmup_repetitions"],
            checked["timing_repetitions"],
        )
        scalar_widths = torch.sum(right_hand_sides * scalar["solutions"], dim=1)
        scalar_width_error = _relative_width_error(torch, scalar_widths, exact_widths)
        accelerator_peak, accelerator_measurement = _peak_accelerator_memory(torch, device)
        records.append(
            {
                **common,
                "method": "scalar_cg",
                "wall_time_seconds": statistics.median(scalar_timings),
                "wall_time_repetitions_seconds": scalar_timings,
                "complete_action_scoring_seconds": candidate_gradient_seconds
                + statistics.median(scalar_timings),
                "operator_matvec_count": operator.equivalent_matvecs,
                "batch_operator_call_count": operator.matmat_calls,
                "sample_cvp_count": operator.equivalent_matvecs * operator.sample_count,
                "per_action_iterations": scalar["iterations"],
                "per_action_explicit_relative_residual": [
                    float(value) for value in scalar["relative_residuals"].cpu()
                ],
                "per_action_width_squared_relative_error": scalar_width_error,
                "max_width_squared_relative_error": max(scalar_width_error),
                "peak_accelerator_memory_bytes": accelerator_peak,
                "accelerator_memory_measurement": accelerator_measurement,
            }
        )

        def batched_call() -> dict[str, Any]:
            operator.reset_counts()
            return _batched_cg(
                torch,
                operator,
                right_hand_sides,
                checked["cg_max_iterations"],
                checked["cg_relative_tolerance"],
            )

        _reset_peak_memory(torch, device)
        batched, batched_timings = _timed(
            torch,
            device,
            batched_call,
            checked["warmup_repetitions"],
            checked["timing_repetitions"],
        )
        batched_widths = torch.sum(right_hand_sides * batched["solutions"], dim=1)
        batched_width_error = _relative_width_error(torch, batched_widths, exact_widths)
        accelerator_peak, accelerator_measurement = _peak_accelerator_memory(torch, device)
        records.append(
            {
                **common,
                "method": "batched_cg",
                "wall_time_seconds": statistics.median(batched_timings),
                "wall_time_repetitions_seconds": batched_timings,
                "complete_action_scoring_seconds": candidate_gradient_seconds
                + statistics.median(batched_timings),
                "operator_matvec_count": operator.equivalent_matvecs,
                "batch_operator_call_count": operator.matmat_calls,
                "sample_cvp_count": operator.equivalent_matvecs * operator.sample_count,
                "per_action_iterations": [
                    int(value) for value in batched["iterations"].cpu()
                ],
                "per_action_explicit_relative_residual": [
                    float(value) for value in batched["relative_residuals"].cpu()
                ],
                "per_action_width_squared_relative_error": batched_width_error,
                "max_width_squared_relative_error": max(batched_width_error),
                "peak_accelerator_memory_bytes": accelerator_peak,
                "accelerator_memory_measurement": accelerator_measurement,
                "solver": "row_batched_independent_cg_with_shared_torch_func_vmap",
            }
        )

        def diagonal_call() -> dict[str, Any]:
            current_jacobian = torch.func.jacrev(operator.outputs)(parameters).detach()
            diagonal = checked["damping"] + torch.sum(
                current_jacobian * current_jacobian, dim=0
            ) / (operator.sample_count * checked["noise_variance"])
            solutions = right_hand_sides / diagonal[None, :]
            return {"solutions": solutions.detach()}

        _reset_peak_memory(torch, device)
        diagonal, diagonal_timings = _timed(
            torch,
            device,
            diagonal_call,
            checked["warmup_repetitions"],
            checked["timing_repetitions"],
        )
        diagonal_widths = torch.sum(right_hand_sides * diagonal["solutions"], dim=1)
        diagonal_width_error = _relative_width_error(torch, diagonal_widths, exact_widths)
        accelerator_peak, accelerator_measurement = _peak_accelerator_memory(torch, device)
        operator.reset_counts()
        diagonal_residual = right_hand_sides - operator.matmat(diagonal["solutions"])
        diagonal_relative_residual = torch.linalg.vector_norm(
            diagonal_residual, dim=1
        ) / torch.linalg.vector_norm(right_hand_sides, dim=1)
        records.append(
            {
                **common,
                "method": "diagonal",
                "wall_time_seconds": statistics.median(diagonal_timings),
                "wall_time_repetitions_seconds": diagonal_timings,
                "complete_action_scoring_seconds": candidate_gradient_seconds
                + statistics.median(diagonal_timings),
                "operator_matvec_count": 0,
                "batch_operator_call_count": 0,
                "sample_cvp_count": 0,
                "diagnostic_full_operator_matvec_count": operator.equivalent_matvecs,
                "per_action_iterations": [0] * checked["action_count"],
                "per_action_explicit_relative_residual": [
                    float(value) for value in diagonal_relative_residual.cpu()
                ],
                "per_action_width_squared_relative_error": diagonal_width_error,
                "max_width_squared_relative_error": max(diagonal_width_error),
                "peak_accelerator_memory_bytes": accelerator_peak,
                "accelerator_memory_measurement": accelerator_measurement,
                "surrogate": "exact_coordinate_diagonal_of_empirical_ggn",
            }
        )

    summary = {
        "schema_version": 1,
        "experiment": str(config.get("name", "autodiff_systems")),
        "profile": str(config.get("profile", "unknown")),
        "seed": seed,
        "status": "completed",
        "benchmark_kind": BENCHMARK_KIND,
        "actual_autodiff": True,
        "torch_available": True,
        "torch_version": runtime.version,
        "device": device,
        "requested_device": checked["device"],
        "dtype": checked["dtype"],
        "architecture": list(architecture),
        "parameter_count": parameter_count,
        "minimum_parameter_count": int(config.get("minimum_parameter_count", 0)),
        "history_size": checked["history_size"],
        "window_size": checked["window_size"],
        "methods": list(METHODS),
        "record_count": len(records),
        "timing_executed": True,
        "numerical_result_reportable": True,
        "foundation_model_benchmark": False,
        "extrapolation_to_larger_models": False,
        "config_digest": config_digest(config),
    }
    return AutodiffSystemsRun(seed, "completed", tuple(records), summary)


def _write_status_artifact(
    path: Path, summary: Mapping[str, Any], *, overwrite: bool
) -> None:
    payload = (canonical_json(summary) + "\n").encode("utf-8")
    if path.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    path.with_suffix(path.suffix + ".sha256").write_text(
        f"{digest}  {path.name}\n", encoding="ascii"
    )


def save_run(
    run: AutodiffSystemsRun,
    output_dir: str | Path,
    config: Mapping[str, Any],
    *,
    overwrite: bool = False,
) -> Path:
    destination = Path(output_dir)
    manifest_config = dict(config)
    manifest_config["execution"] = {
        "driver": "run_autodiff_systems",
        "seed": run.seed,
        "status": run.status,
        "benchmark_kind": BENCHMARK_KIND,
    }
    with ExperimentLogger(
        destination,
        manifest_config,
        run.seed,
        repository=Path(__file__).resolve().parents[1],
        overwrite=overwrite,
    ) as logger:
        for index, record in enumerate(run.records):
            logger.log_round(index, record)
    summary_path = destination / "summary.jsonl"
    if overwrite and summary_path.exists():
        summary_path.unlink()
    append_jsonl(summary_path, run.summary)
    _write_status_artifact(
        destination / "status.json", run.summary, overwrite=overwrite
    )
    return destination


def run_experiment(
    config: Mapping[str, Any],
    *,
    seed_set: str,
    output_root: str | Path,
    overwrite: bool = False,
    capability: TorchCapability | None = None,
) -> tuple[AutodiffSystemsRun, ...]:
    runs: list[AutodiffSystemsRun] = []
    for seed in get_seed_set(config, seed_set):
        run = run_autodiff_systems(config, seed, capability=capability)
        destination = (
            Path(output_root)
            / str(config.get("name", "autodiff_systems"))
            / str(config.get("profile", "unknown"))
            / seed_set
            / f"seed-{seed}"
        )
        save_run(run, destination, config, overwrite=overwrite)
        runs.append(run)
    return tuple(runs)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config_path", nargs="?", type=Path)
    parser.add_argument("--config", dest="config_option", type=Path)
    parser.add_argument("--profile", choices=("smoke", "full"), required=True)
    parser.add_argument(
        "--seed-set",
        choices=("development", "tuning", "evaluation"),
        required=True,
    )
    parser.add_argument(
        "--output-root", type=Path, default=Path("results/raw")
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--record-buck-torch-blocker",
        action="store_true",
        help=(
            "record the verified host Buck dependency failure without probing or "
            "timing a Python runtime"
        ),
    )
    args = parser.parse_args(argv)
    if args.config_path is not None and args.config_option is not None:
        parser.error("provide the config either positionally or with --config, not both")
    config_path = args.config_option or args.config_path
    if config_path is None:
        parser.error("a config path is required")
    config = load_config(config_path, profile=args.profile)
    capability = None
    if args.record_buck_torch_blocker:
        capability = TorchCapability(
            available=False,
            version=None,
            reason_code="missing_buck_dependency",
            reason=BUCK_TORCH_BLOCKER_REASON,
        )
    runs = run_experiment(
        config,
        seed_set=args.seed_set,
        output_root=args.output_root,
        overwrite=args.overwrite,
        capability=capability,
    )
    print(
        json.dumps(
            {
                "experiment": config["name"],
                "profile": args.profile,
                "seed_set": args.seed_set,
                "seeds": [run.seed for run in runs],
                "statuses": [run.status for run in runs],
                "output_root": str(args.output_root),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AutodiffSystemsRun",
    "BENCHMARK_KIND",
    "BUCK_TORCH_BLOCKER_REASON",
    "METHODS",
    "TorchCapability",
    "main",
    "mlp_parameter_count",
    "run_autodiff_systems",
    "run_experiment",
    "save_run",
    "torch_capability",
]
