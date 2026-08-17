"""Matrix-free ``torch.func`` GGN primitives used by the retained benchmark."""

from __future__ import annotations

import importlib.util
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TorchCapability:
    available: bool
    version: str | None
    reason_code: str | None
    reason: str | None


def torch_capability() -> TorchCapability:
    """Report whether the required optional ``torch.func`` API is available."""

    if importlib.util.find_spec("torch") is None:
        return TorchCapability(
            False,
            None,
            "missing_optional_dependency",
            "PyTorch is not installed; no autodiff timing was executed.",
        )
    try:
        import torch
    except (ImportError, OSError) as error:
        return TorchCapability(
            False,
            None,
            "torch_import_failed",
            f"PyTorch could not be imported ({type(error).__name__}).",
        )
    func = getattr(torch, "func", None)
    missing = [
        name
        for name in ("grad", "jacrev", "jvp", "vjp", "vmap")
        if func is None or not callable(getattr(func, name, None))
    ]
    if missing:
        return TorchCapability(
            False,
            str(torch.__version__),
            "unsupported_torch_func_api",
            f"PyTorch lacks required torch.func transforms {missing}.",
        )
    return TorchCapability(True, str(torch.__version__), None, None)


def validate_architecture(value: Sequence[int]) -> tuple[int, ...]:
    if isinstance(value, (str, bytes)) or len(value) < 2:
        raise ValueError("architecture must contain input and output dimensions")
    checked: list[int] = []
    for index, dimension in enumerate(value):
        if isinstance(dimension, bool) or not isinstance(dimension, int) or dimension <= 0:
            raise ValueError(f"architecture[{index}] must be a positive integer")
        checked.append(int(dimension))
    if checked[-1] != 1:
        raise ValueError("the GGN benchmark requires a scalar-output MLP")
    return tuple(checked)


def mlp_parameter_count(architecture: Sequence[int]) -> int:
    checked = validate_architecture(architecture)
    return sum(
        (input_size + 1) * output_size
        for input_size, output_size in zip(checked[:-1], checked[1:], strict=True)
    )


def select_device(torch: Any, requested: str) -> tuple[str | None, str | None]:
    cuda = bool(torch.cuda.is_available())
    mps_backend = getattr(torch.backends, "mps", None)
    mps = bool(mps_backend is not None and mps_backend.is_available())
    if requested == "auto":
        return ("cuda" if cuda else "mps" if mps else "cpu"), None
    if requested == "cuda" and not cuda:
        return None, "CUDA was requested but no CUDA device is available."
    if requested == "mps" and not mps:
        return None, "MPS was requested but no MPS device is available."
    if requested not in {"cpu", "cuda", "mps"}:
        return None, f"unsupported device {requested!r}"
    return requested, None


def synchronize_device(torch: Any, device: str) -> None:
    if device == "cuda":
        torch.cuda.synchronize()
    elif device == "mps" and hasattr(torch, "mps"):
        torch.mps.synchronize()


def mlp_forward(
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


class AutodiffGGN:
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
        if int(inputs.shape[0]) <= 0:
            raise ValueError("GGN inputs must contain at least one sample")
        if not math.isfinite(damping) or damping <= 0.0:
            raise ValueError("damping must be finite and positive")
        if not math.isfinite(noise_variance) or noise_variance <= 0.0:
            raise ValueError("noise_variance must be finite and positive")
        self.torch = torch
        self.parameters = parameters
        self.inputs = inputs
        self.architecture = validate_architecture(architecture)
        self.activation = activation
        self.damping = float(damping)
        self.noise_variance = float(noise_variance)
        self.sample_count = int(inputs.shape[0])
        self.matvec_calls = 0
        self.matmat_calls = 0
        self.equivalent_matvecs = 0

    def outputs(self, parameters: Any) -> Any:
        return mlp_forward(
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
        product = transpose(jacobian_vector)[0]
        self.matvec_calls += 1
        self.equivalent_matvecs += 1
        return (
            self.damping * vector
            + product / (self.sample_count * self.noise_variance)
        ).detach()

    def matmat(self, vectors: Any) -> Any:
        torch = self.torch

        def jvp_one(vector: Any) -> Any:
            return torch.func.jvp(self.outputs, (self.parameters,), (vector,))[1]

        jacobian_vectors = torch.func.vmap(jvp_one)(vectors)
        _, transpose = torch.func.vjp(self.outputs, self.parameters)
        products = torch.func.vmap(lambda value: transpose(value)[0])(
            jacobian_vectors
        )
        batch_size = int(vectors.shape[0])
        self.matmat_calls += 1
        self.equivalent_matvecs += batch_size
        return (
            self.damping * vectors
            + products / (self.sample_count * self.noise_variance)
        ).detach()


def candidate_gradients(
    torch: Any,
    parameters: Any,
    candidates: Any,
    architecture: tuple[int, ...],
    activation: str,
) -> Any:
    def output_one(flat: Any, candidate: Any) -> Any:
        return mlp_forward(torch, flat, candidate, architecture, activation)

    gradient = torch.func.grad(output_one, argnums=0)
    return torch.func.vmap(gradient, in_dims=(None, 0))(
        parameters, candidates
    ).detach()


def exact_sample_space_reference(
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


def scalar_cg(
    torch: Any,
    operator: AutodiffGGN,
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
                break
            direction = residual + (next_squared / residual_squared) * direction
            residual_squared = next_squared
        solutions.append(solution.detach())
        iterations.append(completed)
    stacked = torch.stack(solutions)
    explicit = right_hand_sides - operator.matmat(stacked)
    relative = torch.linalg.vector_norm(explicit, dim=1) / torch.linalg.vector_norm(
        right_hand_sides, dim=1
    )
    return {
        "solutions": stacked,
        "iterations": iterations,
        "relative_residuals": relative.detach(),
    }


def batched_cg(
    torch: Any,
    operator: AutodiffGGN,
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


__all__ = [
    "AutodiffGGN",
    "TorchCapability",
    "batched_cg",
    "candidate_gradients",
    "exact_sample_space_reference",
    "mlp_forward",
    "mlp_parameter_count",
    "scalar_cg",
    "select_device",
    "synchronize_device",
    "torch_capability",
    "validate_architecture",
]
