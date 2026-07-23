"""Run a balanced MNIST contextual bandit with matched local baselines."""

from __future__ import annotations

import argparse
import hashlib
import math
import multiprocessing
import shutil
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import psutil
from numpy.typing import NDArray

from .artifact_utils import atomic_write_text, sha256_file, write_json_artifact, write_sha256_sidecar
from .config import config_digest, load_config
from .logging_utils import canonical_json, collect_run_metadata, derive_seed


FloatArray = NDArray[np.float64]
ACTION_COUNT = 10


@dataclass(frozen=True)
class MNISTData:
    pretrain_x: FloatArray
    pretrain_y: NDArray[np.int64]
    tuning_x: FloatArray
    tuning_y: NDArray[np.int64]
    evaluation_x: FloatArray
    evaluation_y: NDArray[np.int64]
    pixel_indices: NDArray[np.int64]
    digest: str


@dataclass
class ManualNetwork:
    w: FloatArray
    b: FloatArray
    v: FloatArray
    c: FloatArray

    @classmethod
    def initialize(cls, input_dimension: int, hidden_width: int, seed: int) -> "ManualNetwork":
        rng = np.random.Generator(np.random.PCG64(seed))
        return cls(
            rng.normal(scale=1.0 / math.sqrt(input_dimension), size=(hidden_width, input_dimension)),
            np.zeros(hidden_width, dtype=np.float64),
            rng.normal(scale=1.0 / math.sqrt(hidden_width), size=(ACTION_COUNT, hidden_width)),
            np.zeros(ACTION_COUNT, dtype=np.float64),
        )

    def copy(self) -> "ManualNetwork":
        return ManualNetwork(self.w.copy(), self.b.copy(), self.v.copy(), self.c.copy())

    @property
    def parameter_count(self) -> int:
        return self.w.size + self.b.size + self.v.size + self.c.size

    @property
    def hidden_parameter_count(self) -> int:
        return self.w.size + self.b.size

    def hidden(self, x: FloatArray) -> FloatArray:
        return np.tanh(x @ self.w.T + self.b)

    def means(self, x: FloatArray) -> FloatArray:
        hidden = self.hidden(x)
        logits = hidden @ self.v.T + self.c
        return 1.0 / (1.0 + np.exp(-np.clip(logits, -30.0, 30.0)))

    def action_gradient(self, x: FloatArray, action: int) -> FloatArray:
        hidden = np.tanh(self.w @ x + self.b)
        logit = float(self.v[action] @ hidden + self.c[action])
        mean = 1.0 / (1.0 + math.exp(-max(min(logit, 30.0), -30.0)))
        output_derivative = mean * (1.0 - mean)
        hidden_derivative = output_derivative * self.v[action] * (1.0 - hidden * hidden)
        grad_w = np.outer(hidden_derivative, x).ravel()
        grad_b = hidden_derivative
        grad_v = np.zeros_like(self.v)
        grad_v[action] = output_derivative * hidden
        grad_c = np.zeros_like(self.c)
        grad_c[action] = output_derivative
        return np.concatenate((grad_w, grad_b, grad_v.ravel(), grad_c))

    def selected_action_gradients(
        self, x: FloatArray, actions: NDArray[np.int64]
    ) -> FloatArray:
        """Return one full-parameter gradient per (context, action) pair."""
        contexts = np.asarray(x, dtype=np.float64)
        selected_actions = np.asarray(actions, dtype=np.int64)
        if contexts.ndim != 2 or selected_actions.shape != (contexts.shape[0],):
            raise ValueError("contexts and actions must contain aligned batches")
        if np.any((selected_actions < 0) | (selected_actions >= ACTION_COUNT)):
            raise ValueError("action index is out of range")
        hidden = np.tanh(contexts @ self.w.T + self.b)
        selected_v = self.v[selected_actions]
        logits = np.sum(selected_v * hidden, axis=1) + self.c[selected_actions]
        means = 1.0 / (1.0 + np.exp(-np.clip(logits, -30.0, 30.0)))
        output_derivatives = means * (1.0 - means)
        hidden_derivatives = (
            output_derivatives[:, None]
            * selected_v
            * (1.0 - hidden * hidden)
        )
        grad_w = (hidden_derivatives[:, :, None] * contexts[:, None, :]).reshape(
            contexts.shape[0], -1
        )
        grad_v = np.zeros(
            (contexts.shape[0], ACTION_COUNT, self.v.shape[1]), dtype=np.float64
        )
        grad_v[np.arange(contexts.shape[0]), selected_actions] = (
            output_derivatives[:, None] * hidden
        )
        grad_c = np.zeros((contexts.shape[0], ACTION_COUNT), dtype=np.float64)
        grad_c[np.arange(contexts.shape[0]), selected_actions] = output_derivatives
        return np.concatenate(
            (grad_w, hidden_derivatives, grad_v.reshape(contexts.shape[0], -1), grad_c),
            axis=1,
        )

    def parameters(self) -> FloatArray:
        return np.concatenate((self.w.ravel(), self.b, self.v.ravel(), self.c))

    def set_parameters(self, vector: FloatArray) -> None:
        position = 0
        next_position = position + self.w.size
        self.w[...] = vector[position:next_position].reshape(self.w.shape)
        position = next_position
        next_position += self.b.size
        self.b[...] = vector[position:next_position]
        position = next_position
        next_position += self.v.size
        self.v[...] = vector[position:next_position].reshape(self.v.shape)
        position = next_position
        self.c[...] = vector[position:]

    def update_bandit(
        self,
        x: FloatArray,
        action: int,
        reward: float,
        *,
        learning_rate: float,
        ridge: float,
        noise_variance: float,
        maximum_step_norm: float,
    ) -> None:
        prediction = float(self.means(x[None, :])[0, action])
        gradient = (prediction - reward) * self.action_gradient(x, action) / noise_variance
        gradient += ridge * self.parameters()
        step = learning_rate * gradient
        norm = float(np.linalg.norm(step))
        if norm > maximum_step_norm:
            step *= maximum_step_norm / norm
        self.set_parameters(self.parameters() - step)


def _selected_action_gradients_torch(
    network: ManualNetwork,
    contexts: FloatArray,
    actions: NDArray[np.int64],
    *,
    device: str,
    dtype: str,
) -> Any:
    import torch

    torch_dtype = torch.float32 if dtype == "float32" else torch.float64
    x = torch.as_tensor(contexts, dtype=torch_dtype, device=device)
    selected_actions = torch.as_tensor(actions, dtype=torch.int64, device=device)
    w = torch.as_tensor(network.w, dtype=torch_dtype, device=device)
    b = torch.as_tensor(network.b, dtype=torch_dtype, device=device)
    v = torch.as_tensor(network.v, dtype=torch_dtype, device=device)
    c = torch.as_tensor(network.c, dtype=torch_dtype, device=device)
    hidden = torch.tanh(x @ w.T + b)
    selected_v = v[selected_actions]
    logits = torch.sum(selected_v * hidden, dim=1) + c[selected_actions]
    means = torch.sigmoid(logits)
    output_derivatives = means * (1.0 - means)
    hidden_derivatives = (
        output_derivatives[:, None]
        * selected_v
        * (1.0 - hidden * hidden)
    )
    grad_w = (hidden_derivatives[:, :, None] * x[:, None, :]).reshape(x.shape[0], -1)
    grad_v = torch.zeros(
        (x.shape[0], ACTION_COUNT, network.v.shape[1]),
        dtype=torch_dtype,
        device=device,
    )
    grad_v[torch.arange(x.shape[0], device=device), selected_actions] = (
        output_derivatives[:, None] * hidden
    )
    grad_c = torch.zeros(
        (x.shape[0], ACTION_COUNT), dtype=torch_dtype, device=device
    )
    grad_c[torch.arange(x.shape[0], device=device), selected_actions] = output_derivatives
    return torch.cat(
        (grad_w, hidden_derivatives, grad_v.reshape(x.shape[0], -1), grad_c), dim=1
    )


def validate_mnist_config(config: dict[str, Any], *, full: bool) -> None:
    if int(config["rounds"]) <= 0 or int(config["tuning_rounds"]) <= 0:
        raise ValueError("round counts must be positive")
    if set(config["seed_sets"]["tuning"]) & set(config["seed_sets"]["evaluation"]):
        raise ValueError("tuning and evaluation seeds overlap")
    if full and (
        list(config["seed_sets"]["tuning"]) != list(range(3000, 3010))
        or list(config["seed_sets"]["evaluation"]) != list(range(3100, 3120))
    ):
        raise ValueError("full MNIST seed manifests do not match the preregistration")
    grid = config["tuning_grid"]
    if not grid or (full and len(grid) != 4):
        raise ValueError("the full profile requires four tuning configurations")
    if int(config["selection"]["equal_configuration_count"]) != (4 if full else len(grid)):
        raise ValueError("equal tuning-budget declaration is inconsistent")
    if len(set(config["methods"])) != len(config["methods"]):
        raise ValueError("methods must be unique")
    if str(config["cg"].get("device", "cpu")) not in {"auto", "cpu", "cuda"}:
        raise ValueError("cg.device must be auto, cpu, or cuda")
    if str(config["cg"].get("preconditioner", "none")) not in {"none", "jacobi"}:
        raise ValueError("cg.preconditioner must be none or jacobi")
    if str(config["cg"].get("dtype", "float64")) not in {"float32", "float64"}:
        raise ValueError("cg.dtype must be float32 or float64")
    if not isinstance(config["cg"].get("materialize_operator", False), bool):
        raise ValueError("cg.materialize_operator must be boolean")
    if str(config["cg"].get("solver", "cg")) not in {"cg", "dense"}:
        raise ValueError("cg.solver must be cg or dense")


def _dataset_arrays(dataset: Any) -> tuple[NDArray[np.uint8], NDArray[np.int64]]:
    return np.asarray(dataset.data.cpu().numpy()), np.asarray(dataset.targets.cpu().numpy(), dtype=np.int64)


def _balanced_indices(
    labels: NDArray[np.int64],
    count: int,
    rng: np.random.Generator,
    *,
    candidates: NDArray[np.int64] | None = None,
) -> NDArray[np.int64]:
    """Draw a deterministic near-uniform class sample without replacement."""
    available = (
        np.arange(labels.size, dtype=np.int64)
        if candidates is None
        else np.asarray(candidates, dtype=np.int64)
    )
    if count < 0 or count > available.size:
        raise ValueError("balanced sample size exceeds the candidate pool")

    class_pools = [
        rng.permutation(available[labels[available] == action])
        for action in range(ACTION_COUNT)
    ]
    base, remainder = divmod(count, ACTION_COUNT)
    quotas = np.asarray(
        [base + int(action < remainder) for action in range(ACTION_COUNT)],
        dtype=np.int64,
    )
    capacities = np.asarray([pool.size for pool in class_pools], dtype=np.int64)
    quotas = np.minimum(quotas, capacities)
    deficit = count - int(np.sum(quotas))
    while deficit:
        eligible = np.flatnonzero(quotas < capacities)
        if eligible.size == 0:
            raise ValueError("class capacities cannot satisfy the requested sample size")
        for action in eligible:
            if deficit == 0:
                break
            quotas[action] += 1
            deficit -= 1

    selected = np.concatenate(
        [pool[: int(quota)] for pool, quota in zip(class_pools, quotas, strict=True)]
    )
    return np.asarray(rng.permutation(selected), dtype=np.int64)


def load_mnist_data(config: dict[str, Any]) -> MNISTData:
    try:
        from torchvision.datasets import MNIST
    except ImportError as error:
        raise RuntimeError("torchvision is required through the Buck Conda target") from error
    root = Path(config["dataset_root"])
    train = MNIST(root=root, train=True, download=bool(config["download"]))
    test = MNIST(root=root, train=False, download=bool(config["download"]))
    train_x_raw, train_y = _dataset_arrays(train)
    test_x_raw, test_y = _dataset_arrays(test)
    rng = np.random.Generator(np.random.PCG64(20260722))
    pixel_indices = np.sort(
        rng.choice(28 * 28, size=int(config["input_dimension"]), replace=False)
    ).astype(np.int64)
    pre_count = int(config["pretraining_count"])
    tuning_count = int(config["tuning_pool_count"])
    evaluation_count = int(config["evaluation_pool_count"])
    if pre_count + tuning_count > train_y.size or evaluation_count > test_y.size:
        raise ValueError("configured MNIST split exceeds the available dataset")

    def project(raw: NDArray[np.uint8], indices: NDArray[np.int64]) -> FloatArray:
        flat = raw.reshape(raw.shape[0], -1)[:, pixel_indices].astype(np.float64) / 255.0
        return np.asarray((flat - 0.1307) / 0.3081, dtype=np.float64)

    pre_indices = _balanced_indices(train_y, pre_count, rng)
    remaining_train = np.setdiff1d(
        np.arange(train_y.size, dtype=np.int64), pre_indices, assume_unique=True
    )
    tune_indices = _balanced_indices(
        train_y, tuning_count, rng, candidates=remaining_train
    )
    evaluation_indices = _balanced_indices(test_y, evaluation_count, rng)
    pre_x = project(train_x_raw, pre_indices)
    tune_x = project(train_x_raw, tune_indices)
    evaluation_x = project(test_x_raw, evaluation_indices)
    pre_y = train_y[pre_indices]
    tune_y = train_y[tune_indices]
    evaluation_y = test_y[evaluation_indices]
    for name, labels in (("tuning", tune_y), ("evaluation", evaluation_y)):
        majority = float(np.max(np.bincount(labels, minlength=ACTION_COUNT)) / labels.size)
        if majority > 0.101:
            raise ValueError(f"{name} split is too imbalanced for the benchmark: {majority}")
    digest = hashlib.sha256()
    for array in (
        pre_indices, tune_indices, evaluation_indices, pixel_indices,
        pre_x, tune_x, evaluation_x, pre_y, tune_y, evaluation_y,
    ):
        digest.update(np.ascontiguousarray(array).tobytes())
    return MNISTData(pre_x, pre_y, tune_x, tune_y, evaluation_x, evaluation_y, pixel_indices, digest.hexdigest())


def pretrain_network(config: dict[str, Any], data: MNISTData) -> ManualNetwork:
    network = ManualNetwork.initialize(
        int(config["input_dimension"]), int(config["hidden_width"]), 20260722
    )
    rng = np.random.Generator(np.random.PCG64(20260723))
    batch_size = int(config["pretraining_batch_size"])
    rate = float(config["pretraining_learning_rate"])
    for _ in range(int(config["pretraining_epochs"])):
        order = rng.permutation(data.pretrain_y.size)
        for start in range(0, data.pretrain_y.size, batch_size):
            indices = order[start : start + batch_size]
            x, labels = data.pretrain_x[indices], data.pretrain_y[indices]
            hidden = network.hidden(x)
            logits = hidden @ network.v.T + network.c
            logits -= np.max(logits, axis=1, keepdims=True)
            probabilities = np.exp(logits)
            probabilities /= np.sum(probabilities, axis=1, keepdims=True)
            probabilities[np.arange(labels.size), labels] -= 1.0
            probabilities /= labels.size
            grad_v = probabilities.T @ hidden
            grad_c = np.sum(probabilities, axis=0)
            grad_hidden = (probabilities @ network.v) * (1.0 - hidden * hidden)
            network.v -= rate * grad_v
            network.c -= rate * grad_c
            network.w -= rate * (grad_hidden.T @ x)
            network.b -= rate * np.sum(grad_hidden, axis=0)
    return network


def _cg_widths(
    features: FloatArray,
    candidates: FloatArray,
    *,
    ridge: float,
    noise_variance: float,
    tolerance: float,
    maximum_iterations: int,
    device: str = "cpu",
    preconditioner: str = "none",
    dtype: str = "float64",
    materialize_operator: bool = False,
) -> tuple[FloatArray, int, float]:
    if device != "cpu":
        import torch

        resolved_device = (
            "cuda" if device == "auto" and torch.cuda.is_available() else device
        )
        if resolved_device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("MNIST CG requested CUDA, but CUDA is unavailable")
        if resolved_device == "cuda":
            torch.use_deterministic_algorithms(True)
        torch_dtype = torch.float32 if dtype == "float32" else torch.float64
        torch_features = torch.as_tensor(features, dtype=torch_dtype, device=resolved_device)
        torch_candidates = torch.as_tensor(candidates, dtype=torch_dtype, device=resolved_device)

        torch_operator = None
        if materialize_operator:
            torch_operator = ridge * torch.eye(
                torch_features.shape[1], dtype=torch_dtype, device=resolved_device
            )
            if torch_features.numel():
                torch_operator = (
                    torch_operator
                    + torch_features.T @ torch_features / noise_variance
                )

        def torch_matmat(vectors: Any) -> Any:
            if torch_operator is not None:
                return vectors @ torch_operator
            if torch_features.numel() == 0:
                return ridge * vectors
            return (
                ridge * vectors
                + (
                    torch_features.T
                    @ (torch_features @ vectors.T)
                ).T
                / noise_variance
            )

        solutions = torch.zeros_like(torch_candidates)
        residuals = torch_candidates.clone()
        if preconditioner == "jacobi":
            torch_diagonal = (
                torch.diagonal(torch_operator)
                if torch_operator is not None
                else ridge
                + torch.sum(torch_features * torch_features, dim=0)
                / noise_variance
            )
            preconditioned = residuals / torch_diagonal
        else:
            torch_diagonal = None
            preconditioned = residuals
        directions = preconditioned.clone()
        rhs_norms = torch.linalg.vector_norm(torch_candidates, dim=1)
        inner_products = torch.sum(residuals * preconditioned, dim=1)
        active = rhs_norms > 0.0
        per_action_iterations = torch.zeros(
            candidates.shape[0], dtype=torch.int64, device=resolved_device
        )
        for _ in range(maximum_iterations):
            applied = torch_matmat(directions)
            denominators = torch.sum(directions * applied, dim=1)
            steps = torch.zeros_like(rhs_norms)
            valid = active & (denominators > 0.0)
            steps[valid] = inner_products[valid] / denominators[valid]
            solutions[valid] += steps[valid, None] * directions[valid]
            residuals[valid] -= steps[valid, None] * applied[valid]
            per_action_iterations[active] += 1
            next_squared = torch.sum(residuals * residuals, dim=1)
            converged = active & (
                torch.sqrt(torch.clamp(next_squared, min=0.0))
                <= tolerance * rhs_norms
            )
            continuing = active & ~converged & valid
            next_preconditioned = (
                residuals / torch_diagonal
                if torch_diagonal is not None
                else residuals
            )
            next_inner_products = torch.sum(
                residuals * next_preconditioned, dim=1
            )
            betas = torch.zeros_like(rhs_norms)
            betas[continuing] = (
                next_inner_products[continuing] / inner_products[continuing]
            )
            directions[continuing] = (
                next_preconditioned[continuing]
                + betas[continuing, None] * directions[continuing]
            )
            directions[~continuing] = 0.0
            inner_products = next_inner_products
            active = continuing
        quadratic = torch.sum(torch_candidates * solutions, dim=1)
        widths = torch.sqrt(torch.clamp(quadratic, min=0.0)).cpu().numpy()
        relative_residuals = torch.linalg.vector_norm(residuals, dim=1) / torch.clamp(
            rhs_norms, min=torch.finfo(torch_dtype).tiny
        )
        return (
            widths,
            int(torch.sum(per_action_iterations).cpu()),
            float(torch.max(relative_residuals).cpu()),
        )

    operator = None
    if materialize_operator:
        operator = ridge * np.eye(features.shape[1])
        if features.size:
            operator += features.T @ features / noise_variance

    def matmat(vectors: FloatArray) -> FloatArray:
        if operator is not None:
            return vectors @ operator
        if features.size == 0:
            return ridge * vectors
        return (
            ridge * vectors
            + (features.T @ (features @ vectors.T)).T / noise_variance
        )

    solutions = np.zeros_like(candidates)
    residuals = candidates.copy()
    if preconditioner == "jacobi":
        diagonal_preconditioner = (
            np.diag(operator)
            if operator is not None
            else ridge + np.sum(features * features, axis=0) / noise_variance
        )
        preconditioned = residuals / diagonal_preconditioner
    else:
        diagonal_preconditioner = None
        preconditioned = residuals
    directions = preconditioned.copy()
    rhs_norms = np.linalg.norm(candidates, axis=1)
    inner_products = np.einsum("ij,ij->i", residuals, preconditioned)
    active = rhs_norms > 0.0
    per_action_iterations = np.zeros(candidates.shape[0], dtype=np.int64)
    for _ in range(maximum_iterations):
        if not np.any(active):
            break
        applied = matmat(directions)
        denominators = np.einsum("ij,ij->i", directions, applied)
        steps = np.zeros(candidates.shape[0], dtype=np.float64)
        valid = active & (denominators > 0.0)
        steps[valid] = inner_products[valid] / denominators[valid]
        solutions[valid] += steps[valid, None] * directions[valid]
        residuals[valid] -= steps[valid, None] * applied[valid]
        per_action_iterations[active] += 1
        next_squared = np.einsum("ij,ij->i", residuals, residuals)
        converged = active & (
            np.sqrt(np.maximum(next_squared, 0.0)) <= tolerance * rhs_norms
        )
        continuing = active & ~converged & valid
        next_preconditioned = (
            residuals / diagonal_preconditioner
            if diagonal_preconditioner is not None
            else residuals
        )
        next_inner_products = np.einsum(
            "ij,ij->i", residuals, next_preconditioned
        )
        betas = np.zeros(candidates.shape[0], dtype=np.float64)
        betas[continuing] = (
            next_inner_products[continuing] / inner_products[continuing]
        )
        directions[continuing] = (
            next_preconditioned[continuing]
            + betas[continuing, None] * directions[continuing]
        )
        directions[~continuing] = 0.0
        inner_products = next_inner_products
        active = continuing
    quadratic = np.einsum("ij,ij->i", candidates, solutions)
    relative_residuals = np.linalg.norm(residuals, axis=1) / np.maximum(
        rhs_norms, np.finfo(np.float64).tiny
    )
    return (
        np.sqrt(np.maximum(quadratic, 0.0)),
        int(np.sum(per_action_iterations)),
        float(np.max(relative_residuals)),
    )


def _lofi_widths(
    diagonal: FloatArray, factor: FloatArray, candidates: FloatArray
) -> FloatArray:
    inverse_diagonal = 1.0 / diagonal
    retained = factor.shape[1]
    middle = np.eye(retained) + (factor.T * inverse_diagonal) @ factor
    projected = (candidates * inverse_diagonal) @ factor
    quadratic = np.sum(candidates * candidates * inverse_diagonal, axis=1)
    if retained:
        quadratic -= np.sum(projected * np.linalg.solve(middle, projected.T).T, axis=1)
    return np.sqrt(np.maximum(quadratic, 0.0))


def _dense_full_widths(
    features: Any,
    candidates: Any,
    *,
    ridge: float,
    noise_variance: float,
    device: str,
    dtype: str,
) -> tuple[FloatArray, float]:
    if device != "cpu":
        import torch

        resolved_device = "cuda" if device == "auto" and torch.cuda.is_available() else device
        torch_dtype = torch.float32 if dtype == "float32" else torch.float64
        torch_features = torch.as_tensor(features, dtype=torch_dtype, device=resolved_device)
        torch_candidates = torch.as_tensor(candidates, dtype=torch_dtype, device=resolved_device)
        matrix = ridge * torch.eye(
            torch_features.shape[1], dtype=torch_dtype, device=resolved_device
        )
        if torch_features.numel():
            matrix = matrix + torch_features.T @ torch_features / noise_variance
        solutions = torch.linalg.solve(matrix, torch_candidates.T).T
        residuals = torch_candidates - solutions @ matrix
        relative = torch.linalg.vector_norm(residuals, dim=1) / torch.clamp(
            torch.linalg.vector_norm(torch_candidates, dim=1),
            min=torch.finfo(torch_dtype).tiny,
        )
        widths = torch.sqrt(
            torch.clamp(torch.sum(torch_candidates * solutions, dim=1), min=0.0)
        )
        return widths.cpu().numpy(), float(torch.max(relative).cpu())

    array_features = np.asarray(features, dtype=np.float64)
    array_candidates = np.asarray(candidates, dtype=np.float64)
    matrix = ridge * np.eye(array_features.shape[1])
    if array_features.size:
        matrix += array_features.T @ array_features / noise_variance
    solutions = np.linalg.solve(matrix, array_candidates.T).T
    residuals = array_candidates - solutions @ matrix
    relative = np.linalg.norm(residuals, axis=1) / np.maximum(
        np.linalg.norm(array_candidates, axis=1), np.finfo(np.float64).tiny
    )
    widths = np.sqrt(
        np.maximum(np.einsum("ij,ij->i", array_candidates, solutions), 0.0)
    )
    return widths, float(np.max(relative))


def _lofi_update(
    diagonal: FloatArray,
    factor: FloatArray,
    gradient: FloatArray,
    *,
    noise_variance: float,
    rank: int,
) -> tuple[FloatArray, FloatArray]:
    augmented = np.column_stack((factor, gradient / math.sqrt(noise_variance)))
    left, singular, _ = np.linalg.svd(augmented, full_matrices=False)
    retained = min(rank, singular.size)
    next_factor = left[:, :retained] * singular[:retained]
    if retained < singular.size:
        dropped = left[:, retained:] * singular[retained:]
        diagonal = diagonal + np.sum(dropped * dropped, axis=1)
    return diagonal, next_factor


def _stream(data: MNISTData, seed: int, phase: str, rounds: int, noise_std: float) -> tuple[FloatArray, NDArray[np.int64], FloatArray]:
    x_pool, y_pool = (data.tuning_x, data.tuning_y) if phase == "tuning" else (data.evaluation_x, data.evaluation_y)
    rng = np.random.Generator(np.random.PCG64(derive_seed(seed, "mnist_contextual", phase)))
    if rounds > y_pool.size:
        raise ValueError("horizon exceeds the disjoint context pool")
    order = rng.permutation(y_pool.size)[:rounds]
    noises = rng.normal(scale=noise_std, size=rounds)
    return x_pool[order], y_pool[order], np.asarray(noises, dtype=np.float64)


def run_policy(
    config: dict[str, Any], data: MNISTData, pretrained: ManualNetwork, method: str,
    seed: int, phase: str, hyperparameters: dict[str, float]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rounds = int(config["tuning_rounds"] if phase == "tuning" else config["rounds"])
    x_stream, labels, noises = _stream(data, seed, phase, rounds, float(config["noise_std"]))
    network = pretrained.copy()
    frozen = pretrained.copy()
    ridge = float(hyperparameters["ridge"])
    bonus = float(hyperparameters["bonus"])
    learning_rate = float(hyperparameters["learning_rate"])
    noise_variance = float(config["noise_std"]) ** 2
    parameter_count = network.parameter_count
    historical_gradients: list[FloatArray] = []
    history_x: list[FloatArray] = []
    history_actions: list[int] = []
    diagonal = np.full(parameter_count, ridge, dtype=np.float64)
    head_dimension = frozen.v.shape[1] + 1
    head_matrices = np.stack([np.eye(head_dimension) * ridge for _ in range(ACTION_COUNT)])
    head_rhs = np.zeros((ACTION_COUNT, head_dimension), dtype=np.float64)
    lofi_diagonal = np.full(parameter_count, ridge, dtype=np.float64)
    lofi_factor = np.empty((parameter_count, 0), dtype=np.float64)
    arm_counts = np.zeros(ACTION_COUNT, dtype=np.int64)
    arm_sums = np.zeros(ACTION_COUNT, dtype=np.float64)
    rng = np.random.Generator(np.random.PCG64(derive_seed(seed, method, phase, "policy")))
    cumulative_regret = 0.0
    sample_cvps = 0
    maximum_cg_relative_residual = 0.0
    records: list[dict[str, Any]] = []
    started = time.perf_counter()
    configured_cg_device = str(config["cg"].get("device", "cpu"))
    resolved_cg_device = configured_cg_device
    torch_historical: Any = None
    if configured_cg_device != "cpu":
        import torch

        resolved_cg_device = (
            "cuda"
            if configured_cg_device == "auto" and torch.cuda.is_available()
            else configured_cg_device
        )
        if resolved_cg_device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("MNIST CG requested CUDA, but CUDA is unavailable")
        if method in {"historical_neural_ucb", "neural_ts"}:
            torch_dtype = (
                torch.float32
                if str(config["cg"].get("dtype", "float64")) == "float32"
                else torch.float64
            )
            torch_historical = torch.empty(
                (rounds, parameter_count), dtype=torch_dtype, device=resolved_cg_device
            )
    full_trainable = method in {
        "current_full_ggn_cg", "historical_neural_ucb", "neural_ts",
        "all_layer_diagonal", "block_laplace", "lofi", "greedy"
    }
    for round_index, (x, label, noise) in enumerate(zip(x_stream, labels, noises, strict=True)):
        predictions = network.means(x[None, :])[0] if full_trainable else np.zeros(ACTION_COUNT)
        widths = np.zeros(ACTION_COUNT, dtype=np.float64)
        iterations = 0
        cg_relative_residual = 0.0
        candidate_gradients: FloatArray | None = None
        candidate_gradients_torch: Any = None
        if method in {"current_full_ggn_cg", "historical_neural_ucb", "neural_ts", "all_layer_diagonal", "block_laplace", "lofi"}:
            candidate_contexts = np.repeat(x[None, :], ACTION_COUNT, axis=0)
            candidate_actions = np.arange(ACTION_COUNT, dtype=np.int64)
            if method in {"current_full_ggn_cg", "historical_neural_ucb", "neural_ts"} and configured_cg_device != "cpu":
                candidate_gradients_torch = _selected_action_gradients_torch(
                    network,
                    candidate_contexts,
                    candidate_actions,
                    device=resolved_cg_device,
                    dtype=str(config["cg"].get("dtype", "float64")),
                )
                candidate_gradients = candidate_gradients_torch.cpu().numpy().astype(
                    np.float64, copy=False
                )
            else:
                candidate_gradients = network.selected_action_gradients(
                    candidate_contexts, candidate_actions
                )
        if method == "current_full_ggn_cg":
            if history_x and configured_cg_device != "cpu":
                features: Any = _selected_action_gradients_torch(
                    network,
                    np.asarray(history_x, dtype=np.float64),
                    np.asarray(history_actions, dtype=np.int64),
                    device=resolved_cg_device,
                    dtype=str(config["cg"].get("dtype", "float64")),
                )
            elif history_x:
                features = network.selected_action_gradients(
                    np.asarray(history_x, dtype=np.float64),
                    np.asarray(history_actions, dtype=np.int64),
                )
            else:
                features = np.empty((0, parameter_count))
            candidate_system = (
                candidate_gradients_torch
                if candidate_gradients_torch is not None
                else candidate_gradients
            )
            if str(config["cg"].get("solver", "cg")) == "dense":
                widths, cg_relative_residual = _dense_full_widths(
                    features,
                    candidate_system,
                    ridge=ridge,
                    noise_variance=noise_variance,
                    device=str(config["cg"].get("device", "cpu")),
                    dtype=str(config["cg"].get("dtype", "float64")),
                )
            else:
                widths, iterations, cg_relative_residual = _cg_widths(
                    features,
                    candidate_system,
                    ridge=ridge, noise_variance=noise_variance,
                    tolerance=float(config["cg"]["relative_residual"]),
                    maximum_iterations=int(config["cg"]["max_iterations"]),
                    device=str(config["cg"].get("device", "cpu")),
                    preconditioner=str(config["cg"].get("preconditioner", "none")),
                    dtype=str(config["cg"].get("dtype", "float64")),
                    materialize_operator=bool(config["cg"].get("materialize_operator", False)),
                )
            sample_cvps += iterations * len(history_x)
        elif method in {"historical_neural_ucb", "neural_ts"}:
            features = (
                torch_historical[:round_index]
                if torch_historical is not None
                else (
                    np.stack(historical_gradients)
                    if historical_gradients
                    else np.empty((0, parameter_count))
                )
            )
            candidate_system = (
                candidate_gradients_torch
                if candidate_gradients_torch is not None
                else candidate_gradients
            )
            if str(config["cg"].get("solver", "cg")) == "dense":
                widths, cg_relative_residual = _dense_full_widths(
                    features,
                    candidate_system,
                    ridge=ridge,
                    noise_variance=noise_variance,
                    device=str(config["cg"].get("device", "cpu")),
                    dtype=str(config["cg"].get("dtype", "float64")),
                )
            else:
                widths, iterations, cg_relative_residual = _cg_widths(
                    features,
                    candidate_system,
                    ridge=ridge, noise_variance=noise_variance,
                    tolerance=float(config["cg"]["relative_residual"]),
                    maximum_iterations=int(config["cg"]["max_iterations"]),
                    device=str(config["cg"].get("device", "cpu")),
                    preconditioner=str(config["cg"].get("preconditioner", "none")),
                    dtype=str(config["cg"].get("dtype", "float64")),
                    materialize_operator=bool(config["cg"].get("materialize_operator", False)),
                )
            sample_cvps += iterations * len(historical_gradients)
        elif method == "all_layer_diagonal":
            widths = np.sqrt(np.sum(candidate_gradients * candidate_gradients / diagonal, axis=1))
        elif method == "block_laplace":
            hidden_count = network.hidden_parameter_count
            widths = np.sqrt(np.sum(candidate_gradients[:, :hidden_count] ** 2 / diagonal[:hidden_count], axis=1))
            for action in range(ACTION_COUNT):
                head_gradient = np.concatenate((candidate_gradients[action, hidden_count + action * network.v.shape[1] : hidden_count + (action + 1) * network.v.shape[1]], [candidate_gradients[action, -ACTION_COUNT + action]]))
                widths[action] = math.sqrt(widths[action] ** 2 + float(head_gradient @ np.linalg.solve(head_matrices[action], head_gradient)))
        elif method == "lofi":
            widths = _lofi_widths(lofi_diagonal, lofi_factor, candidate_gradients)
        elif method in {"neural_linear", "frozen_last_layer_ucb", "linucb_frozen"}:
            representation = np.concatenate((frozen.hidden(x[None, :])[0], [1.0]))
            for action in range(ACTION_COUNT):
                estimate = np.linalg.solve(head_matrices[action], head_rhs[action])
                predictions[action] = float(representation @ estimate)
                widths[action] = math.sqrt(float(representation @ np.linalg.solve(head_matrices[action], representation)))
        elif method in {"context_free_ucb", "context_free_ts"}:
            predictions = np.divide(arm_sums, np.maximum(arm_counts, 1))
            widths = np.sqrt(1.0 / (arm_counts + ridge))

        if method == "neural_ts":
            scores = rng.normal(predictions, bonus * widths)
        elif method == "neural_linear":
            scores = rng.normal(predictions, bonus * widths)
        elif method == "context_free_ts":
            scores = rng.normal(predictions, bonus * widths)
        elif method == "greedy":
            scores = predictions
        elif method == "context_free_ucb" and round_index < ACTION_COUNT:
            scores = np.full(ACTION_COUNT, -np.inf)
            scores[round_index] = np.inf
        else:
            scores = predictions + bonus * widths
        action = int(np.argmax(scores))
        maximum_cg_relative_residual = max(
            maximum_cg_relative_residual, cg_relative_residual
        )
        true_means = np.equal(np.arange(ACTION_COUNT), int(label)).astype(np.float64)
        reward = float(true_means[action] + noise)
        regret = float(1.0 - true_means[action])
        cumulative_regret += regret
        coverage = np.abs(true_means - predictions) <= bonus * widths
        records.append(
            {
                "round": round_index + 1,
                "method": method,
                "seed": seed,
                "phase": phase,
                "selected_action": action,
                "label": int(label),
                "pseudo_regret": regret,
                "cumulative_pseudo_regret": cumulative_regret,
                "accuracy": float(action == int(label)),
                "coverage_all_actions": float(np.mean(coverage)),
                "average_bonus": float(np.mean(bonus * widths)),
                "cg_iterations": iterations,
                "cg_max_original_relative_residual": cg_relative_residual,
                "cumulative_sample_cvps": sample_cvps,
            }
        )
        if candidate_gradients is not None:
            selected_gradient = candidate_gradients[action].copy()
            historical_gradients.append(selected_gradient)
            if torch_historical is not None and candidate_gradients_torch is not None:
                torch_historical[round_index].copy_(candidate_gradients_torch[action])
            diagonal += selected_gradient * selected_gradient / noise_variance
            if method == "lofi":
                lofi_diagonal, lofi_factor = _lofi_update(
                    lofi_diagonal,
                    lofi_factor,
                    selected_gradient,
                    noise_variance=noise_variance,
                    rank=int(config["lofi_rank"]),
                )
            if method == "block_laplace":
                hidden_count = network.hidden_parameter_count
                head_gradient = np.concatenate((selected_gradient[hidden_count + action * network.v.shape[1] : hidden_count + (action + 1) * network.v.shape[1]], [selected_gradient[-ACTION_COUNT + action]]))
                head_matrices[action] += np.outer(head_gradient, head_gradient) / noise_variance
        if method in {"neural_linear", "frozen_last_layer_ucb", "linucb_frozen"}:
            representation = np.concatenate((frozen.hidden(x[None, :])[0], [1.0]))
            head_matrices[action] += np.outer(representation, representation) / noise_variance
            head_rhs[action] += representation * reward / noise_variance
        if method in {"context_free_ucb", "context_free_ts"}:
            arm_counts[action] += 1
            arm_sums[action] += reward
        if full_trainable:
            network.update_bandit(
                x, action, reward, learning_rate=learning_rate, ridge=ridge,
                noise_variance=noise_variance,
                maximum_step_norm=float(config["maximum_step_norm"]),
            )
        history_x.append(x.copy())
        history_actions.append(action)

    elapsed = time.perf_counter() - started
    summary = {
        "method": method,
        "seed": seed,
        "phase": phase,
        "hyperparameters": dict(hyperparameters),
        "rounds": rounds,
        "cumulative_pseudo_regret": cumulative_regret,
        "accuracy": float(np.mean([record["accuracy"] for record in records])),
        "empirical_coverage": float(np.mean([record["coverage_all_actions"] for record in records])),
        "average_bonus": float(np.mean([record["average_bonus"] for record in records])),
        "wall_seconds": elapsed,
        "peak_rss_bytes": psutil.Process().memory_info().rss,
        "sample_cvps": sample_cvps,
        "maximum_cg_original_relative_residual": maximum_cg_relative_residual,
        "cg_device": str(config["cg"].get("device", "cpu")),
        "cg_preconditioner": str(config["cg"].get("preconditioner", "none")),
        "cg_dtype": str(config["cg"].get("dtype", "float64")),
        "cg_materialize_operator": bool(config["cg"].get("materialize_operator", False)),
        "full_gram_solver": str(config["cg"].get("solver", "cg")),
        "implementation": "local_matched_reimplementation_not_official",
    }
    return records, summary


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    atomic_write_text(path, "".join(canonical_json(record) + "\n" for record in records), encoding="ascii")
    write_sha256_sidecar(path)


_POLICY_WORKER_CONTEXT: tuple[dict[str, Any], MNISTData, ManualNetwork] | None = None


def _initialize_policy_worker(
    config: dict[str, Any], data: MNISTData, pretrained: ManualNetwork
) -> None:
    global _POLICY_WORKER_CONTEXT
    _POLICY_WORKER_CONTEXT = (config, data, pretrained)


def _execute_policy_task(
    task: tuple[str, int, str, dict[str, float], int]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if _POLICY_WORKER_CONTEXT is None:
        raise RuntimeError("policy worker context is not initialized")
    config, data, pretrained = _POLICY_WORKER_CONTEXT
    method, seed, phase, hyperparameters, config_index = task
    records, summary = run_policy(
        config, data, pretrained, method, seed, phase, hyperparameters
    )
    summary["config_index"] = config_index
    return records, summary


def _run_policy_tasks(
    config: dict[str, Any],
    data: MNISTData,
    pretrained: ManualNetwork,
    tasks: list[tuple[str, int, str, dict[str, float], int]],
    workers: int,
) -> list[tuple[list[dict[str, Any]], dict[str, Any]]]:
    if workers <= 1:
        _initialize_policy_worker(config, data, pretrained)
        return [_execute_policy_task(task) for task in tasks]
    with ProcessPoolExecutor(
        max_workers=workers,
        mp_context=multiprocessing.get_context("spawn"),
        initializer=_initialize_policy_worker,
        initargs=(config, data, pretrained),
    ) as executor:
        results: list[tuple[list[dict[str, Any]], dict[str, Any]]] = []
        for index, result in enumerate(
            executor.map(_execute_policy_task, tasks, chunksize=1), start=1
        ):
            results.append(result)
            if index == 1 or index % 10 == 0 or index == len(tasks):
                print(
                    f"completed {index}/{len(tasks)} policy tasks",
                    flush=True,
                )
        return results


def run_benchmark(
    config: dict[str, Any],
    output_root: str | Path,
    *,
    overwrite: bool = False,
    workers: int = 1,
) -> dict[str, Any]:
    full = len(config["seed_sets"]["evaluation"]) == 20
    validate_mnist_config(config, full=full)
    destination = Path(output_root)
    if destination.exists() and overwrite:
        shutil.rmtree(destination)
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"refusing to overwrite nonempty {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    data = load_mnist_data(config)
    pretrained = pretrain_network(config, data)
    methods = tuple(str(method) for method in config["methods"])
    grid = tuple(dict(item) for item in config["tuning_grid"])
    tuning_summaries: list[dict[str, Any]] = []
    all_rounds: list[dict[str, Any]] = []
    tuning_tasks = [
        (method, int(seed), "tuning", hyperparameters, config_index)
        for method in methods
        for config_index, hyperparameters in enumerate(grid)
        for seed in config["seed_sets"]["tuning"]
    ]
    for records, summary in _run_policy_tasks(
        config, data, pretrained, tuning_tasks, workers
    ):
        tuning_summaries.append(summary)
        all_rounds.extend(records)
    selection: dict[str, Any] = {
        "schema_version": 1,
        "selection_phase": "tuning_only",
        "tuning_seeds": list(config["seed_sets"]["tuning"]),
        "evaluation_seeds_inspected": False,
        "equal_configuration_count": len(grid),
        "selected": {},
    }
    for method in methods:
        candidates = []
        for config_index, hyperparameters in enumerate(grid):
            values = [float(row["cumulative_pseudo_regret"]) for row in tuning_summaries if row["method"] == method and row["config_index"] == config_index]
            candidates.append((float(np.mean(values)), config_index, hyperparameters))
        mean, index, hyperparameters = min(candidates, key=lambda item: (item[0], item[1]))
        selection["selected"][method] = {"config_index": index, "hyperparameters": hyperparameters, "mean_tuning_regret": mean}
    selection_path, _ = write_json_artifact(destination / "selection.json", selection)
    selection_sha = sha256_file(selection_path)
    evaluation_summaries: list[dict[str, Any]] = []
    evaluation_tasks = [
        (
            method,
            int(seed),
            "evaluation",
            dict(selection["selected"][method]["hyperparameters"]),
            int(selection["selected"][method]["config_index"]),
        )
        for method in methods
        for seed in config["seed_sets"]["evaluation"]
    ]
    for records, summary in _run_policy_tasks(
        config, data, pretrained, evaluation_tasks, workers
    ):
        summary["selection_sha256"] = selection_sha
        evaluation_summaries.append(summary)
        all_rounds.extend(records)
    _write_jsonl(destination / "tuning_summaries.jsonl", tuning_summaries)
    _write_jsonl(destination / "evaluation_summaries.jsonl", evaluation_summaries)
    _write_jsonl(destination / "rounds.jsonl", all_rounds)
    manifest = {
        "schema_version": 1,
        "study": "mnist_contextual_benchmark",
        "config_digest": config_digest(config),
        "dataset_digest": data.digest,
        "pixel_indices": data.pixel_indices.tolist(),
        "tuning_seeds": list(config["seed_sets"]["tuning"]),
        "evaluation_seeds": list(config["seed_sets"]["evaluation"]),
        "evaluation_seeds_inspected_during_selection": False,
        "method_count": len(methods),
        "tuning_configuration_count_per_method": len(grid),
        "evaluation_run_count": len(evaluation_summaries),
        "context_free_optimum_tuning": float(np.max(np.bincount(data.tuning_y, minlength=ACTION_COUNT)) / data.tuning_y.size),
        "context_free_optimum_evaluation": float(np.max(np.bincount(data.evaluation_y, minlength=ACTION_COUNT)) / data.evaluation_y.size),
        "parameter_count": pretrained.parameter_count,
        "workers": workers,
        "aggregate_policy_cpu_hours": float(
            sum(row["wall_seconds"] for row in tuning_summaries + evaluation_summaries)
            / 3600.0
        ),
        "provenance": collect_run_metadata(repository=Path(__file__).resolve().parents[1], packages=("numpy", "torch", "torchvision", "psutil")),
        "limitations": [
            "all neural baselines are local matched reimplementations, not official packages",
            "the full current-GGN method has quadratic replay work and no truncation is substituted",
            "per-policy wall times under multi-process execution are resource accounting under host contention, not controlled method-speed comparisons",
        ],
    }
    write_json_artifact(destination / "manifest.json", manifest)
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("experiments/configs/mnist_contextual_benchmark.yaml"))
    parser.add_argument("--profile", choices=("smoke", "full"), default="smoke")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    return parser


def main() -> None:
    args = _parser().parse_args()
    config = load_config(args.config, args.profile)
    result = run_benchmark(
        config, args.output_root, overwrite=args.overwrite, workers=args.workers
    )
    print(canonical_json(result))


if __name__ == "__main__":
    main()
