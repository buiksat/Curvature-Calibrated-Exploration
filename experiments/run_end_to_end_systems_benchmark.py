"""Run a real-PyTorch end-to-end contextual-bandit systems benchmark."""

from __future__ import annotations

import argparse
import hashlib
import math
import os
import resource
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import psutil
from numpy.typing import NDArray

from .artifact_utils import (
    input_set_sha256,
    sha256_file,
    write_deterministic_npz,
    write_json_artifact,
)
from .config import config_digest, get_seed_set, load_config
from .logging_utils import (
    canonical_json,
    collect_run_metadata,
    derive_seed,
    seed_everything,
)
from .run_autodiff_systems import (
    _batched_cg,
    _candidate_gradients,
    _mlp_forward,
    _select_device,
    _synchronize,
    mlp_parameter_count,
    torch_capability,
)
from .run_autodiff_ggn_benchmark import _hidden_features


DEFAULT_CONFIG = (
    Path(__file__).with_name("configs") / "end_to_end_systems_benchmark.yaml"
)
METHODS = (
    "current_replay_ggn_cg",
    "historical_gradient_cg",
    "empirical_diagonal",
    "exact_last_layer",
    "local_tensor_block_isotropic",
    "greedy",
)
COMPONENTS = (
    "forward_seconds",
    "candidate_gradient_seconds",
    "curvature_seconds",
    "action_selection_seconds",
    "reward_seconds",
    "training_seconds",
    "replay_update_seconds",
    "round_total_seconds",
)


@dataclass(frozen=True)
class TorchStream:
    candidates: Any
    true_means: Any
    noises: Any
    initial_parameters: Any
    teacher_parameters: Any
    stream_sha256: str
    generation_seconds: float


@dataclass(frozen=True)
class PolicyResult:
    arrays: dict[str, NDArray[np.generic]]
    summary: dict[str, Any]


def _positive_int(value: Any, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _nonnegative_int(value: Any, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result < 0:
        raise ValueError(f"{name} must be nonnegative")
    return result


def _positive_float(value: Any, *, name: str) -> float:
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def validate_benchmark_config(config: Mapping[str, Any]) -> None:
    rounds = _positive_int(config["rounds"], name="rounds")
    warmup = _nonnegative_int(config["warmup_rounds"], name="warmup_rounds")
    if warmup >= rounds:
        raise ValueError("warmup_rounds must be smaller than rounds")

    models = config.get("models")
    if (
        not isinstance(models, Sequence)
        or isinstance(models, (str, bytes))
        or not models
    ):
        raise ValueError("models must be a nonempty list")
    names: list[str] = []
    for model in models:
        if not isinstance(model, Mapping):
            raise ValueError("each model must be an object")
        name = str(model.get("name", ""))
        architecture = model.get("architecture")
        if (
            not name
            or not isinstance(architecture, Sequence)
            or isinstance(architecture, (str, bytes))
        ):
            raise ValueError("each model requires a name and architecture")
        checked = tuple(int(value) for value in architecture)
        if len(checked) < 2 or checked[-1] != 1 or any(value <= 0 for value in checked):
            raise ValueError("architectures must be positive and scalar-output")
        mlp_parameter_count(checked)
        names.append(name)
    if len(names) != len(set(names)):
        raise ValueError("model names must be unique")

    action_counts = tuple(
        _positive_int(value, name="action_counts entry")
        for value in config["action_counts"]
    )
    replay_sizes = tuple(
        _positive_int(value, name="replay_sizes entry")
        for value in config["replay_sizes"]
    )
    if len(set(action_counts)) != len(action_counts):
        raise ValueError("action_counts must be unique")
    if len(set(replay_sizes)) != len(replay_sizes):
        raise ValueError("replay_sizes must be unique")
    if max(replay_sizes) >= rounds:
        raise ValueError("replay_sizes must be smaller than rounds")
    if tuple(str(value) for value in config["methods"]) != METHODS:
        raise ValueError(f"methods must equal the implemented order {METHODS}")
    semantics = config.get("method_semantics")
    if not isinstance(semantics, Mapping) or set(semantics) != set(METHODS):
        raise ValueError("method_semantics must describe every implemented method")
    unavailable = config.get("unavailable_baselines")
    if not isinstance(unavailable, Mapping) or set(unavailable) != {"lofi", "kfac"}:
        raise ValueError("unavailable_baselines must explicitly record LO-FI and KFAC")
    if "lofi" in METHODS or "kfac" in METHODS:
        raise ValueError("unavailable faithful baselines cannot appear as methods")
    if "not KFAC" not in str(semantics["local_tensor_block_isotropic"]):
        raise ValueError(
            "the local tensor-block method must explicitly say it is not KFAC"
        )

    if str(config["activation"]) != "tanh":
        raise ValueError("this benchmark is preregistered for tanh MLPs")
    if str(config["dtype"]) not in {"float32", "float64"}:
        raise ValueError("dtype must be float32 or float64")
    if str(config["device"]) not in {"auto", "cpu", "cuda"}:
        raise ValueError("device must be auto, cpu, or cuda")
    for key in (
        "noise_std",
        "damping",
        "bonus_scale",
        "learning_rate",
        "model_ridge",
        "maximum_step_norm",
        "cg_relative_tolerance",
        "compute_cap_accelerator_hours",
        "compute_cap_cpu_hours",
    ):
        _positive_float(config[key], name=key)
    if float(config["cg_relative_tolerance"]) >= 1.0:
        raise ValueError("cg_relative_tolerance must be below one")
    _positive_int(config["cg_max_iterations"], name="cg_max_iterations")
    if config.get("deterministic_algorithms") is not True:
        raise ValueError("deterministic_algorithms must be enabled")
    if config.get("synchronize_component_boundaries") is not True:
        raise ValueError("component-boundary synchronization must be enabled")


def benchmark_grid(
    config: Mapping[str, Any], seed_set: str = "evaluation"
) -> tuple[tuple[Mapping[str, Any], int, int, int, str], ...]:
    validate_benchmark_config(config)
    return tuple(
        (model, int(action_count), int(replay_size), int(seed), method)
        for model in config["models"]
        for action_count in config["action_counts"]
        for replay_size in config["replay_sizes"]
        for seed in get_seed_set(config, seed_set)
        for method in METHODS
    )


def summarize_timings(values: Sequence[float]) -> dict[str, float | int]:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size == 0 or not np.all(np.isfinite(array)):
        raise ValueError("timing values must be a nonempty finite vector")
    if np.any(array < 0.0):
        raise ValueError("timing values must be nonnegative")
    return {
        "count": int(array.size),
        "total_seconds": float(np.sum(array)),
        "mean_seconds": float(np.mean(array)),
        "p50_seconds": float(np.percentile(array, 50.0)),
        "p95_seconds": float(np.percentile(array, 95.0)),
        "minimum_seconds": float(np.min(array)),
        "maximum_seconds": float(np.max(array)),
    }


def _array_digest(*arrays: NDArray[np.generic]) -> str:
    digest = hashlib.sha256()
    for array in arrays:
        contiguous = np.ascontiguousarray(array)
        digest.update(str(contiguous.dtype).encode("ascii"))
        digest.update(canonical_json(list(contiguous.shape)).encode("ascii"))
        digest.update(contiguous.tobytes(order="C"))
    return digest.hexdigest()


def _initialize_parameters(
    torch: Any,
    architecture: tuple[int, ...],
    generator: Any,
    dtype: Any,
) -> Any:
    parts = []
    for input_size, output_size in zip(
        architecture[:-1], architecture[1:], strict=True
    ):
        weights = torch.randn(
            output_size,
            input_size,
            generator=generator,
            dtype=dtype,
            device="cpu",
        ) / math.sqrt(float(input_size))
        bias = torch.zeros(output_size, dtype=dtype, device="cpu")
        parts.extend((weights.reshape(-1), bias))
    return torch.cat(parts)


def _parameter_blocks(
    architecture: tuple[int, ...],
) -> tuple[tuple[str, int, int], ...]:
    blocks: list[tuple[str, int, int]] = []
    offset = 0
    for layer, (input_size, output_size) in enumerate(
        zip(architecture[:-1], architecture[1:], strict=True)
    ):
        weight_count = input_size * output_size
        blocks.append((f"layer_{layer}_weight", offset, offset + weight_count))
        offset += weight_count
        blocks.append((f"layer_{layer}_bias", offset, offset + output_size))
        offset += output_size
    if offset != mlp_parameter_count(architecture):
        raise AssertionError("parameter block layout is inconsistent")
    return tuple(blocks)


def _make_stream(
    torch: Any,
    config: Mapping[str, Any],
    model: Mapping[str, Any],
    action_count: int,
    seed: int,
    *,
    device: str,
    dtype: Any,
) -> TorchStream:
    started = time.perf_counter()
    architecture = tuple(int(value) for value in model["architecture"])
    rounds = int(config["rounds"])
    generator = torch.Generator(device="cpu")
    generator.manual_seed(
        derive_seed(seed, "end-to-end-systems", model["name"], action_count)
    )
    candidates_cpu = torch.randn(
        rounds,
        action_count,
        architecture[0],
        generator=generator,
        dtype=dtype,
        device="cpu",
    )
    candidates_cpu = candidates_cpu / torch.clamp(
        torch.linalg.vector_norm(candidates_cpu, dim=2, keepdim=True), min=1.0
    )
    initial_cpu = _initialize_parameters(torch, architecture, generator, dtype)
    teacher_cpu = _initialize_parameters(torch, architecture, generator, dtype)
    noises_cpu = torch.randn(
        rounds,
        action_count,
        generator=generator,
        dtype=dtype,
        device="cpu",
    ) * float(config["noise_std"])
    candidates = candidates_cpu.to(device)
    initial = initial_cpu.to(device)
    teacher = teacher_cpu.to(device)
    noises = noises_cpu.to(device)
    with torch.no_grad():
        true_means = _mlp_forward(
            torch,
            teacher,
            candidates.reshape(-1, architecture[0]),
            architecture,
            "tanh",
        ).reshape(rounds, action_count)
    _synchronize(torch, device)
    generation_seconds = time.perf_counter() - started
    stream_sha = _array_digest(
        candidates_cpu.numpy(),
        noises_cpu.numpy(),
        initial_cpu.numpy(),
        teacher_cpu.numpy(),
    )
    return TorchStream(
        candidates=candidates,
        true_means=true_means.detach(),
        noises=noises,
        initial_parameters=initial.detach(),
        teacher_parameters=teacher.detach(),
        stream_sha256=stream_sha,
        generation_seconds=generation_seconds,
    )


class _SummedAutodiffGGN:
    """Real JVP/VJP operator for damping I + J.T J / noise_variance."""

    def __init__(
        self,
        torch: Any,
        parameters: Any,
        inputs: Any,
        architecture: tuple[int, ...],
        damping: float,
        noise_variance: float,
    ) -> None:
        self.torch = torch
        self.parameters = parameters.detach()
        self.inputs = inputs
        self.architecture = architecture
        self.damping = damping
        self.noise_variance = noise_variance
        self.sample_count = int(inputs.shape[0])
        self.equivalent_matvecs = 0
        self.matmat_calls = 0

    def outputs(self, parameters: Any) -> Any:
        return _mlp_forward(
            self.torch, parameters, self.inputs, self.architecture, "tanh"
        )

    def matmat(self, vectors: Any) -> Any:
        torch = self.torch

        def jvp_one(vector: Any) -> Any:
            return torch.func.jvp(self.outputs, (self.parameters,), (vector,))[1]

        jacobian_vectors = torch.func.vmap(jvp_one)(vectors)
        _, transpose = torch.func.vjp(self.outputs, self.parameters)
        transpose_products = torch.func.vmap(lambda value: transpose(value)[0])(
            jacobian_vectors
        )
        batch_size = int(vectors.shape[0])
        self.equivalent_matvecs += batch_size
        self.matmat_calls += 1
        return (
            self.damping * vectors + transpose_products / self.noise_variance
        ).detach()


class _HistoricalGradientOperator:
    """Explicit collection-time gradient Gram used by a local control."""

    def __init__(
        self,
        gradients: Any,
        *,
        damping: float,
        noise_variance: float,
    ) -> None:
        self.gradients = gradients
        self.damping = damping
        self.noise_variance = noise_variance
        self.sample_count = int(gradients.shape[0])
        self.equivalent_matvecs = 0
        self.matmat_calls = 0

    def matmat(self, vectors: Any) -> Any:
        batch_size = int(vectors.shape[0])
        self.equivalent_matvecs += batch_size
        self.matmat_calls += 1
        return (
            self.damping * vectors
            + (vectors @ self.gradients.transpose(0, 1))
            @ self.gradients
            / self.noise_variance
        ).detach()


def _timed_component(torch: Any, device: str, function: Any) -> tuple[Any, float]:
    _synchronize(torch, device)
    started = time.perf_counter()
    result = function()
    _synchronize(torch, device)
    return result, time.perf_counter() - started


def _rss_high_water_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def _cg_uncertainty(
    torch: Any,
    operator: Any,
    candidate_gradients: Any,
    *,
    damping: float,
    tolerance: float,
    maximum_iterations: int,
) -> tuple[Any, dict[str, Any]]:
    if operator is None:
        widths = torch.linalg.vector_norm(candidate_gradients, dim=1) / math.sqrt(
            damping
        )
        return widths.detach(), {
            "sample_cvps": 0,
            "maximum_relative_residual": 0.0,
            "all_converged": True,
            "mean_iterations": 0.0,
        }
    result = _batched_cg(
        torch,
        operator,
        candidate_gradients,
        maximum_iterations,
        tolerance,
    )
    widths_squared = torch.sum(candidate_gradients * result["solutions"], dim=1)
    relative = result["relative_residuals"]
    raw_iterations = result["iterations"]
    if hasattr(raw_iterations, "to"):
        iteration_values = raw_iterations.to(dtype=torch.float64)
    else:
        iteration_values = torch.as_tensor(
            raw_iterations, dtype=torch.float64, device=candidate_gradients.device
        )
    return torch.sqrt(torch.clamp(widths_squared, min=0.0)).detach(), {
        "sample_cvps": int(operator.equivalent_matvecs * operator.sample_count),
        "maximum_relative_residual": float(torch.max(relative).detach().cpu()),
        "all_converged": bool(torch.all(relative <= tolerance * (1.0 + 1e-5))),
        "mean_iterations": float(torch.mean(iteration_values).detach().cpu()),
    }


def _last_inverse_add(inverse: Any, vector: Any, variance: float) -> Any:
    transformed = inverse @ vector
    return inverse - (transformed[:, None] @ transformed[None, :]) / (
        variance + vector @ transformed
    )


def _last_inverse_remove(inverse: Any, vector: Any, variance: float) -> Any | None:
    transformed = inverse @ vector
    denominator = variance - vector @ transformed
    if float(denominator.detach().cpu()) <= 1e-8 * variance:
        return None
    return inverse + (transformed[:, None] @ transformed[None, :]) / denominator


def _recompute_last_inverse(
    torch: Any,
    vectors: Sequence[Any],
    *,
    dimension: int,
    damping: float,
    variance: float,
    device: str,
    dtype: Any,
) -> Any:
    matrix = damping * torch.eye(dimension, dtype=dtype, device=device)
    if vectors:
        stacked = torch.stack(tuple(vectors))
        matrix = matrix + stacked.transpose(0, 1) @ stacked / variance
    return torch.linalg.inv(matrix)


def _training_step(
    torch: Any,
    parameters: Any,
    selected_input: Any,
    reward: Any,
    *,
    architecture: tuple[int, ...],
    variance: float,
    learning_rate: float,
    model_ridge: float,
    maximum_step_norm: float,
) -> tuple[Any, float]:
    prediction = _mlp_forward(torch, parameters, selected_input, architecture, "tanh")
    loss = 0.5 * (prediction - reward) ** 2 / variance
    loss = loss + 0.5 * model_ridge * torch.mean(parameters * parameters)
    gradient = torch.autograd.grad(loss, parameters)[0]
    gradient_norm = torch.linalg.vector_norm(gradient)
    raw_step_norm = learning_rate * gradient_norm
    scale = torch.clamp(
        maximum_step_norm / torch.clamp(raw_step_norm, min=1e-30), max=1.0
    )
    next_parameters = (
        (parameters - learning_rate * scale * gradient).detach().requires_grad_(True)
    )
    return next_parameters, float(
        torch.minimum(
            raw_step_norm, torch.as_tensor(maximum_step_norm, device=gradient.device)
        )
        .detach()
        .cpu()
    )


def run_policy(
    torch: Any,
    config: Mapping[str, Any],
    model: Mapping[str, Any],
    *,
    action_count: int,
    replay_size: int,
    seed: int,
    method: str,
    stream: TorchStream,
    device: str,
    dtype: Any,
) -> PolicyResult:
    if method not in METHODS:
        raise ValueError(f"unknown method {method!r}")
    architecture = tuple(int(value) for value in model["architecture"])
    parameter_count = mlp_parameter_count(architecture)
    rounds = int(config["rounds"])
    warmup_rounds = int(config["warmup_rounds"])
    variance = float(config["noise_std"]) ** 2
    damping = float(config["damping"])
    blocks = _parameter_blocks(architecture)
    needs_full_gradients = method in {
        "current_replay_ggn_cg",
        "historical_gradient_cg",
        "empirical_diagonal",
        "local_tensor_block_isotropic",
    }
    parameters = stream.initial_parameters.clone().detach().requires_grad_(True)
    process = psutil.Process()

    context_ring: list[Any] = []
    gradient_ring: list[Any] = []
    diagonal_precision = torch.full(
        (parameter_count,), damping, dtype=dtype, device=device
    )
    block_precision = torch.full((len(blocks),), damping, dtype=dtype, device=device)
    block_contribution_ring: list[Any] = []
    last_dimension = architecture[-2] + 1
    last_inverse = torch.eye(last_dimension, dtype=dtype, device=device) / damping
    last_feature_ring: list[Any] = []

    component_values: dict[str, list[float]] = {name: [] for name in COMPONENTS}
    cumulative_regret = np.empty(rounds, dtype=np.float64)
    selected_actions = np.empty(rounds, dtype=np.int64)
    optimal_actions = np.empty(rounds, dtype=np.int64)
    update_norms = np.empty(rounds, dtype=np.float64)
    measured_round_indices: list[int] = []
    measured_host_rss: list[int] = []
    measured_device_allocated: list[int] = []
    measured_device_reserved: list[int] = []
    regret_total = 0.0
    sample_cvps_total = 0
    maximum_relative_residual = 0.0
    all_cg_converged = True
    cg_iteration_values: list[float] = []
    measured_peak_host_rss = process.memory_info().rss
    initial_host_rss = measured_peak_host_rss
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    policy_started = time.perf_counter()

    for round_index in range(rounds):
        if round_index == warmup_rounds:
            _synchronize(torch, device)
            measured_peak_host_rss = process.memory_info().rss
            if device == "cuda":
                torch.cuda.reset_peak_memory_stats()
        _synchronize(torch, device)
        round_started = time.perf_counter()
        candidates = stream.candidates[round_index]

        predictions, forward_seconds = _timed_component(
            torch,
            device,
            lambda: _mlp_forward(
                torch, parameters, candidates, architecture, "tanh"
            ).detach(),
        )

        if needs_full_gradients:
            candidate_gradients, gradient_seconds = _timed_component(
                torch,
                device,
                lambda: _candidate_gradients(
                    torch, parameters.detach(), candidates, architecture, "tanh"
                ),
            )
        else:
            candidate_gradients = None
            gradient_seconds = 0.0

        round_cg: dict[str, Any] = {
            "sample_cvps": 0,
            "maximum_relative_residual": 0.0,
            "all_converged": True,
            "mean_iterations": 0.0,
        }
        selected_last_features: Any = None

        def uncertainty() -> Any:
            nonlocal round_cg, selected_last_features
            if method == "current_replay_ggn_cg":
                operator = (
                    _SummedAutodiffGGN(
                        torch,
                        parameters,
                        torch.stack(tuple(context_ring)),
                        architecture,
                        damping,
                        variance,
                    )
                    if context_ring
                    else None
                )
                widths, round_cg = _cg_uncertainty(
                    torch,
                    operator,
                    candidate_gradients,
                    damping=damping,
                    tolerance=float(config["cg_relative_tolerance"]),
                    maximum_iterations=int(config["cg_max_iterations"]),
                )
                return widths
            if method == "historical_gradient_cg":
                operator = (
                    _HistoricalGradientOperator(
                        torch.stack(tuple(gradient_ring)),
                        damping=damping,
                        noise_variance=variance,
                    )
                    if gradient_ring
                    else None
                )
                widths, round_cg = _cg_uncertainty(
                    torch,
                    operator,
                    candidate_gradients,
                    damping=damping,
                    tolerance=float(config["cg_relative_tolerance"]),
                    maximum_iterations=int(config["cg_max_iterations"]),
                )
                return widths
            if method == "empirical_diagonal":
                return torch.sqrt(
                    torch.sum(
                        candidate_gradients
                        * candidate_gradients
                        / diagonal_precision[None, :],
                        dim=1,
                    )
                ).detach()
            if method == "local_tensor_block_isotropic":
                width_squared = torch.zeros(action_count, dtype=dtype, device=device)
                for block_index, (_, start, stop) in enumerate(blocks):
                    width_squared += (
                        torch.sum(candidate_gradients[:, start:stop] ** 2, dim=1)
                        / block_precision[block_index]
                    )
                return torch.sqrt(torch.clamp(width_squared, min=0.0)).detach()
            if method == "exact_last_layer":
                features = _hidden_features(
                    torch, parameters.detach(), candidates, architecture, "tanh"
                )
                selected_last_features = features
                return torch.sqrt(
                    torch.clamp(
                        torch.sum((features @ last_inverse) * features, dim=1),
                        min=0.0,
                    )
                ).detach()
            return torch.zeros(action_count, dtype=dtype, device=device)

        widths, curvature_seconds = _timed_component(torch, device, uncertainty)

        def select_action() -> tuple[int, Any]:
            scores = (
                predictions
                if method == "greedy"
                else predictions + float(config["bonus_scale"]) * widths
            )
            action = int(torch.argmax(scores).detach().cpu())
            return action, scores

        (selected_action, _), action_seconds = _timed_component(
            torch, device, select_action
        )

        def observe_reward() -> tuple[Any, int, float]:
            means = stream.true_means[round_index]
            optimal_action = int(torch.argmax(means).detach().cpu())
            regret = float(
                (means[optimal_action] - means[selected_action]).detach().cpu()
            )
            reward = (
                means[selected_action] + stream.noises[round_index, selected_action]
            )
            return reward.detach(), optimal_action, regret

        (reward, optimal_action, regret), reward_seconds = _timed_component(
            torch, device, observe_reward
        )

        (parameters, update_norm), training_seconds = _timed_component(
            torch,
            device,
            lambda: _training_step(
                torch,
                parameters,
                candidates[selected_action],
                reward,
                architecture=architecture,
                variance=variance,
                learning_rate=float(config["learning_rate"]),
                model_ridge=float(config["model_ridge"]),
                maximum_step_norm=float(config["maximum_step_norm"]),
            ),
        )

        def update_replay() -> None:
            nonlocal last_inverse
            if method == "current_replay_ggn_cg":
                context_ring.append(candidates[selected_action].detach().clone())
                if len(context_ring) > replay_size:
                    context_ring.pop(0)
            elif method == "historical_gradient_cg":
                gradient_ring.append(
                    candidate_gradients[selected_action].detach().clone()
                )
                if len(gradient_ring) > replay_size:
                    gradient_ring.pop(0)
            elif method == "empirical_diagonal":
                selected_gradient = (
                    candidate_gradients[selected_action].detach().clone()
                )
                if len(gradient_ring) == replay_size:
                    removed = gradient_ring.pop(0)
                    diagonal_precision.sub_(removed * removed / variance)
                gradient_ring.append(selected_gradient)
                diagonal_precision.add_(
                    selected_gradient * selected_gradient / variance
                )
                diagonal_precision.clamp_(min=damping)
            elif method == "local_tensor_block_isotropic":
                selected_gradient = candidate_gradients[selected_action]
                contribution = torch.stack(
                    tuple(
                        torch.mean(selected_gradient[start:stop] ** 2) / variance
                        for _, start, stop in blocks
                    )
                ).detach()
                if len(block_contribution_ring) == replay_size:
                    block_precision.sub_(block_contribution_ring.pop(0))
                block_contribution_ring.append(contribution.clone())
                block_precision.add_(contribution)
                block_precision.clamp_(min=damping)
            elif method == "exact_last_layer":
                selected_feature = (
                    selected_last_features[selected_action].detach().clone()
                )
                if len(last_feature_ring) == replay_size:
                    removed = last_feature_ring.pop(0)
                    downdated = _last_inverse_remove(last_inverse, removed, variance)
                    last_inverse = (
                        downdated
                        if downdated is not None
                        else _recompute_last_inverse(
                            torch,
                            last_feature_ring,
                            dimension=last_dimension,
                            damping=damping,
                            variance=variance,
                            device=device,
                            dtype=dtype,
                        )
                    )
                last_feature_ring.append(selected_feature)
                last_inverse = _last_inverse_add(
                    last_inverse, selected_feature, variance
                )
                last_inverse = 0.5 * (last_inverse + last_inverse.transpose(0, 1))

        _, replay_seconds = _timed_component(torch, device, update_replay)
        _synchronize(torch, device)
        round_total_seconds = time.perf_counter() - round_started

        regret_total += regret
        cumulative_regret[round_index] = regret_total
        selected_actions[round_index] = selected_action
        optimal_actions[round_index] = optimal_action
        update_norms[round_index] = update_norm
        sample_cvps_total += int(round_cg["sample_cvps"])
        maximum_relative_residual = max(
            maximum_relative_residual,
            float(round_cg["maximum_relative_residual"]),
        )
        all_cg_converged = all_cg_converged and bool(round_cg["all_converged"])
        cg_iteration_values.append(float(round_cg["mean_iterations"]))
        current_host_rss = int(process.memory_info().rss)
        measured_peak_host_rss = max(measured_peak_host_rss, current_host_rss)
        if round_index >= warmup_rounds:
            measured_round_indices.append(round_index + 1)
            measured_host_rss.append(current_host_rss)
            if device == "cuda":
                measured_device_allocated.append(int(torch.cuda.memory_allocated()))
                measured_device_reserved.append(int(torch.cuda.memory_reserved()))
            else:
                measured_device_allocated.append(0)
                measured_device_reserved.append(0)
            values = {
                "forward_seconds": forward_seconds,
                "candidate_gradient_seconds": gradient_seconds,
                "curvature_seconds": curvature_seconds,
                "action_selection_seconds": action_seconds,
                "reward_seconds": reward_seconds,
                "training_seconds": training_seconds,
                "replay_update_seconds": replay_seconds,
                "round_total_seconds": round_total_seconds,
            }
            for name, value in values.items():
                component_values[name].append(value)

    _synchronize(torch, device)
    complete_policy_seconds = time.perf_counter() - policy_started
    if device == "cuda":
        peak_allocated = int(torch.cuda.max_memory_allocated())
        peak_reserved = int(torch.cuda.max_memory_reserved())
        ending_allocated = int(torch.cuda.memory_allocated())
        ending_reserved = int(torch.cuda.memory_reserved())
    else:
        peak_allocated = peak_reserved = ending_allocated = ending_reserved = 0
    latencies = {
        name: summarize_timings(values) for name, values in component_values.items()
    }
    arrays: dict[str, NDArray[np.generic]] = {
        "round": np.arange(1, rounds + 1, dtype=np.int64),
        "cumulative_pseudo_regret": cumulative_regret,
        "selected_actions": selected_actions,
        "optimal_actions": optimal_actions,
        "training_update_norm": update_norms,
        "measured_round": np.asarray(measured_round_indices, dtype=np.int64),
        "host_rss_bytes": np.asarray(measured_host_rss, dtype=np.int64),
        "device_allocated_bytes": np.asarray(measured_device_allocated, dtype=np.int64),
        "device_reserved_bytes": np.asarray(measured_device_reserved, dtype=np.int64),
    }
    for name, values in component_values.items():
        arrays[name] = np.asarray(values, dtype=np.float64)
    summary = {
        "schema_version": 1,
        "experiment": "end_to_end_systems_benchmark",
        "status": "completed",
        "method": method,
        "method_semantics": str(config["method_semantics"][method]),
        "model": str(model["name"]),
        "architecture": list(architecture),
        "parameter_count": parameter_count,
        "action_count": action_count,
        "replay_size": replay_size,
        "seed": seed,
        "rounds": rounds,
        "warmup_rounds": warmup_rounds,
        "measured_rounds": rounds - warmup_rounds,
        "warmup_semantics": (
            "warmup rounds execute the complete online loop and update policy state "
            "but are excluded from latency quantiles"
        ),
        "actual_pytorch": True,
        "actual_candidate_autodiff": needs_full_gradients,
        "matrix_free_autodiff_ggn": method == "current_replay_ggn_cg",
        "full_online_loop": True,
        "terminal_pseudo_regret": float(cumulative_regret[-1]),
        "complete_policy_wall_seconds": complete_policy_seconds,
        "stream_generation_seconds_shared_cell": stream.generation_seconds,
        "latency_components": latencies,
        "measured_rounds_per_second": (
            (rounds - warmup_rounds)
            / float(latencies["round_total_seconds"]["total_seconds"])
        ),
        "sample_cvp_count": sample_cvps_total,
        "maximum_cg_relative_residual": maximum_relative_residual,
        "all_cg_solves_converged": all_cg_converged,
        "mean_per_action_cg_iterations": float(np.mean(cg_iteration_values)),
        "initial_host_rss_bytes": initial_host_rss,
        "peak_measured_host_rss_bytes": measured_peak_host_rss,
        "process_lifetime_high_water_bytes": _rss_high_water_bytes(),
        "peak_device_allocated_bytes": peak_allocated,
        "peak_device_reserved_bytes": peak_reserved,
        "ending_device_allocated_bytes": ending_allocated,
        "ending_device_reserved_bytes": ending_reserved,
        "host_memory_scope": (
            "absolute process RSS sampled after every synchronized measured round; "
            "the process is reused across policies and RSS is not allocator-isolated"
        ),
        "device_memory_scope": (
            "CUDA peak counters reset after warmup for each policy; the CUDA caching "
            "allocator remains live across sequential policies"
            if device == "cuda"
            else "not applicable on CPU; device memory values are zero"
        ),
        "synchronization": "explicit before and after every timed component",
        "timing_clock": "time.perf_counter",
        "numerical_claim": "systems measurement only; no regret superiority claim",
    }
    return PolicyResult(arrays=arrays, summary=summary)


def _runtime_metadata(
    torch: Any, device: str, config: Mapping[str, Any]
) -> dict[str, Any]:
    repository = Path(__file__).resolve().parents[1]
    metadata = collect_run_metadata(
        repository=repository,
        packages=tuple(config.get("provenance", {}).get("packages", ())),
    )
    source_paths = (
        Path("experiments/run_end_to_end_systems_benchmark.py"),
        Path("experiments/run_autodiff_systems.py"),
        Path("experiments/run_autodiff_ggn_benchmark.py"),
        Path("experiments/artifact_utils.py"),
        Path("experiments/config.py"),
        Path("experiments/logging_utils.py"),
        Path("scripts/reproduce_fig_end_to_end_systems.sh"),
    )
    metadata["source_files"] = [
        {
            "path": path.as_posix(),
            "sha256": sha256_file(repository / path),
        }
        for path in source_paths
    ]
    affinity = (
        sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None
    )
    runtime: dict[str, Any] = {
        "torch_version": str(torch.__version__),
        "torch_cuda_version": getattr(torch.version, "cuda", None),
        "requested_device": str(config["device"]),
        "device": device,
        "torch_num_threads": int(torch.get_num_threads()),
        "torch_num_interop_threads": int(torch.get_num_interop_threads()),
        "physical_cpu_count": psutil.cpu_count(logical=False),
        "logical_cpu_count": psutil.cpu_count(logical=True),
        "cpu_affinity": affinity,
        "cpu_affinity_count": None if affinity is None else len(affinity),
        "thread_environment": {
            name: os.environ.get(name)
            for name in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "KMP_AFFINITY",
                "CUBLAS_WORKSPACE_CONFIG",
            )
        },
        "deterministic_algorithms": bool(torch.are_deterministic_algorithms_enabled()),
        "synchronize_component_boundaries": True,
        "warmup_rounds": int(config["warmup_rounds"]),
        "policy_process_isolation": "none; methods execute sequentially in one process",
        "method_execution_order": list(METHODS),
    }
    if device == "cuda":
        properties = torch.cuda.get_device_properties(torch.cuda.current_device())
        runtime["cuda_device"] = {
            "name": properties.name,
            "total_memory_bytes": int(properties.total_memory),
            "capability": list(torch.cuda.get_device_capability()),
            "cudnn_version": torch.backends.cudnn.version(),
        }
    metadata["runtime"] = runtime
    return metadata


def _run_directory(
    root: Path,
    profile: str,
    seed_set: str,
    model_name: str,
    action_count: int,
    replay_size: int,
    method: str,
    seed: int,
) -> Path:
    return (
        root
        / profile
        / seed_set
        / f"model-{model_name}_K-{action_count}_replay-{replay_size}"
        / method
        / f"seed-{seed}"
    )


def _save_policy(
    result: PolicyResult,
    destination: Path,
    *,
    config: Mapping[str, Any],
    profile: str,
    seed_set: str,
    stream: TorchStream,
    metadata: Mapping[str, Any],
    overwrite: bool,
) -> tuple[Path, Path, Path]:
    if destination.exists():
        if not overwrite:
            raise FileExistsError(f"refusing to overwrite {destination}")
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    timings_path, _ = write_deterministic_npz(
        destination / "timings.npz", result.arrays
    )
    summary_value = {
        **result.summary,
        "profile": profile,
        "seed_set": seed_set,
        "config_digest": config_digest(config),
        "stream_sha256": stream.stream_sha256,
    }
    summary_path, _ = write_json_artifact(destination / "summary.json", summary_value)
    manifest = {
        "schema_version": 1,
        "experiment": "end_to_end_systems_benchmark",
        "profile": profile,
        "seed_set": seed_set,
        "identity": {
            key: summary_value[key]
            for key in (
                "model",
                "parameter_count",
                "action_count",
                "replay_size",
                "method",
                "seed",
            )
        },
        "config_digest": config_digest(config),
        "config": dict(config),
        "stream_sha256": stream.stream_sha256,
        "timings_sha256": sha256_file(timings_path),
        "summary_sha256": sha256_file(summary_path),
        "provenance": dict(metadata),
    }
    manifest_path, _ = write_json_artifact(destination / "manifest.json", manifest)
    return timings_path, summary_path, manifest_path


def run_grid(
    config: dict[str, Any],
    *,
    profile: str,
    seed_set: str,
    output_root: Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    validate_benchmark_config(config)
    if seed_set not in {"development", "tuning", "evaluation"}:
        raise ValueError("seed_set must be development, tuning, or evaluation")
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    capability = torch_capability()
    phase_root = output_root / profile / seed_set
    if not capability.available:
        manifest, _ = write_json_artifact(
            phase_root / "manifest.json",
            {
                "schema_version": 1,
                "experiment": "end_to_end_systems_benchmark",
                "profile": profile,
                "seed_set": seed_set,
                "status": "not_run",
                "reason": capability.reason,
                "completed_run_count": 0,
                "reportable_complete": False,
            },
        )
        return {
            "status": "not_run",
            "manifest": manifest.as_posix(),
            "reason": capability.reason,
        }

    import torch

    requested_device = str(config["device"])
    resolved_device = requested_device
    if requested_device == "auto":
        resolved_device = "cuda" if torch.cuda.is_available() else "cpu"
    device, device_error = _select_device(torch, resolved_device)
    if device is None:
        manifest, _ = write_json_artifact(
            phase_root / "manifest.json",
            {
                "schema_version": 1,
                "experiment": "end_to_end_systems_benchmark",
                "profile": profile,
                "seed_set": seed_set,
                "status": "not_run",
                "reason": device_error,
                "completed_run_count": 0,
                "reportable_complete": False,
            },
        )
        return {
            "status": "not_run",
            "manifest": manifest.as_posix(),
            "reason": device_error,
        }
    dtype = torch.float32 if config["dtype"] == "float32" else torch.float64
    seed_everything(derive_seed(0, "end-to-end-systems-grid"))
    torch.manual_seed(derive_seed(0, "end-to-end-systems-grid", "torch"))
    torch.use_deterministic_algorithms(bool(config["deterministic_algorithms"]))
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
    metadata = _runtime_metadata(torch, device, config)
    cap_hours = float(
        config[
            (
                "compute_cap_accelerator_hours"
                if device == "cuda"
                else "compute_cap_cpu_hours"
            )
        ]
    )
    cap_seconds = cap_hours * 3600.0
    started = time.perf_counter()
    inputs: list[dict[str, str]] = []
    completed = 0
    expected = len(benchmark_grid(config, seed_set))
    cap_reached = False
    for model in config["models"]:
        for action_count in config["action_counts"]:
            for replay_size in config["replay_sizes"]:
                for seed in get_seed_set(config, seed_set):
                    stream = _make_stream(
                        torch,
                        config,
                        model,
                        int(action_count),
                        int(seed),
                        device=device,
                        dtype=dtype,
                    )
                    for method in METHODS:
                        if time.perf_counter() - started >= cap_seconds:
                            cap_reached = True
                            break
                        result = run_policy(
                            torch,
                            config,
                            model,
                            action_count=int(action_count),
                            replay_size=int(replay_size),
                            seed=int(seed),
                            method=method,
                            stream=stream,
                            device=device,
                            dtype=dtype,
                        )
                        destination = _run_directory(
                            output_root,
                            profile,
                            seed_set,
                            str(model["name"]),
                            int(action_count),
                            int(replay_size),
                            method,
                            int(seed),
                        )
                        paths = _save_policy(
                            result,
                            destination,
                            config=config,
                            profile=profile,
                            seed_set=seed_set,
                            stream=stream,
                            metadata=metadata,
                            overwrite=overwrite,
                        )
                        for path in paths:
                            inputs.append(
                                {
                                    "path": path.relative_to(phase_root).as_posix(),
                                    "sha256": sha256_file(path),
                                }
                            )
                        completed += 1
                    del stream
                    if device == "cuda":
                        torch.cuda.empty_cache()
                    if cap_reached:
                        break
                if cap_reached:
                    break
            if cap_reached:
                break
        if cap_reached:
            break
    elapsed = time.perf_counter() - started
    status = "compute_cap_reached" if cap_reached else "completed"
    manifest_value = {
        "schema_version": 1,
        "experiment": "end_to_end_systems_benchmark",
        "profile": profile,
        "seed_set": seed_set,
        "status": status,
        "config_digest": config_digest(config),
        "expected_run_count": expected,
        "completed_run_count": completed,
        "reportable_complete": completed == expected and status == "completed",
        "elapsed_seconds": elapsed,
        "compute_cap_hours": cap_hours,
        "compute_cap_semantics": "soft wall-clock cap checked between complete policy runs",
        "device": device,
        "inputs": sorted(inputs, key=lambda item: item["path"]),
        "input_set_sha256": input_set_sha256(inputs),
        "provenance": metadata,
    }
    manifest_path, _ = write_json_artifact(phase_root / "manifest.json", manifest_value)
    return {
        "status": status,
        "manifest": manifest_path.as_posix(),
        "expected_run_count": expected,
        "completed_run_count": completed,
        "elapsed_seconds": elapsed,
        "device": device,
        "reportable_complete": manifest_value["reportable_complete"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--profile", choices=("smoke", "full"), required=True)
    parser.add_argument(
        "--seed-set",
        choices=("development", "tuning", "evaluation"),
        default="evaluation",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = load_config(args.config, profile=args.profile)
    result = run_grid(
        config,
        profile=args.profile,
        seed_set=args.seed_set,
        output_root=args.output_root,
        overwrite=args.overwrite,
    )
    print(canonical_json(result))
    return 0 if result["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "COMPONENTS",
    "DEFAULT_CONFIG",
    "METHODS",
    "benchmark_grid",
    "run_grid",
    "run_policy",
    "summarize_timings",
    "validate_benchmark_config",
]
