"""Run a balanced MNIST contextual bandit with matched local baselines."""

from __future__ import annotations

import argparse
import hashlib
import math
import shutil
import time
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


def _dataset_arrays(dataset: Any) -> tuple[NDArray[np.uint8], NDArray[np.int64]]:
    return np.asarray(dataset.data.cpu().numpy()), np.asarray(dataset.targets.cpu().numpy(), dtype=np.int64)


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
    train_order = rng.permutation(train_y.size)
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

    pre_indices = train_order[:pre_count]
    tune_indices = train_order[pre_count : pre_count + tuning_count]
    evaluation_indices = np.arange(evaluation_count, dtype=np.int64)
    pre_x = project(train_x_raw, pre_indices)
    tune_x = project(train_x_raw, tune_indices)
    evaluation_x = project(test_x_raw, evaluation_indices)
    pre_y = train_y[pre_indices]
    tune_y = train_y[tune_indices]
    evaluation_y = test_y[evaluation_indices]
    for name, labels in (("tuning", tune_y), ("evaluation", evaluation_y)):
        majority = float(np.max(np.bincount(labels, minlength=ACTION_COUNT)) / labels.size)
        if majority > 0.13:
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
) -> tuple[FloatArray, int]:
    def matvec(vector: FloatArray) -> FloatArray:
        if features.size == 0:
            return ridge * vector
        return ridge * vector + features.T @ (features @ vector) / noise_variance

    widths = np.empty(candidates.shape[0], dtype=np.float64)
    total_iterations = 0
    for index, rhs in enumerate(candidates):
        solution = np.zeros_like(rhs)
        residual = rhs.copy()
        direction = residual.copy()
        rhs_norm = float(np.linalg.norm(rhs))
        residual_squared = float(residual @ residual)
        iterations = 0
        if rhs_norm > 0.0:
            for iterations in range(1, maximum_iterations + 1):
                applied = matvec(direction)
                step = residual_squared / float(direction @ applied)
                solution += step * direction
                residual -= step * applied
                next_squared = float(residual @ residual)
                if math.sqrt(max(next_squared, 0.0)) <= tolerance * rhs_norm:
                    break
                direction = residual + (next_squared / residual_squared) * direction
                residual_squared = next_squared
        widths[index] = math.sqrt(max(float(rhs @ solution), 0.0))
        total_iterations += iterations
    return widths, total_iterations


def _lofi_widths(
    features: FloatArray, candidates: FloatArray, *, ridge: float, noise_variance: float, rank: int
) -> FloatArray:
    if features.size == 0:
        return np.linalg.norm(candidates, axis=1) / math.sqrt(ridge)
    scaled = features / math.sqrt(noise_variance)
    _, singular, right = np.linalg.svd(scaled, full_matrices=False)
    retained = min(rank, singular.size)
    low_rank = singular[:retained, None] * right[:retained]
    total_diagonal = np.sum(scaled * scaled, axis=0)
    residual_diagonal = np.maximum(total_diagonal - np.sum(low_rank * low_rank, axis=0), 0.0)
    inverse_diagonal = 1.0 / (ridge + residual_diagonal)
    middle = np.eye(retained) + (low_rank * inverse_diagonal) @ low_rank.T
    projected = (candidates * inverse_diagonal) @ low_rank.T
    quadratic = np.sum(candidates * candidates * inverse_diagonal, axis=1)
    if retained:
        quadratic -= np.sum(projected * np.linalg.solve(middle, projected.T).T, axis=1)
    return np.sqrt(np.maximum(quadratic, 0.0))


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
    arm_counts = np.zeros(ACTION_COUNT, dtype=np.int64)
    arm_sums = np.zeros(ACTION_COUNT, dtype=np.float64)
    rng = np.random.Generator(np.random.PCG64(derive_seed(seed, method, phase, "policy")))
    cumulative_regret = 0.0
    sample_cvps = 0
    records: list[dict[str, Any]] = []
    started = time.perf_counter()
    full_trainable = method in {
        "current_full_ggn_cg", "historical_neural_ucb", "neural_ts",
        "all_layer_diagonal", "block_laplace", "lofi", "greedy"
    }
    for round_index, (x, label, noise) in enumerate(zip(x_stream, labels, noises, strict=True)):
        predictions = network.means(x[None, :])[0] if full_trainable else np.zeros(ACTION_COUNT)
        widths = np.zeros(ACTION_COUNT, dtype=np.float64)
        iterations = 0
        candidate_gradients: FloatArray | None = None
        if method in {"current_full_ggn_cg", "historical_neural_ucb", "neural_ts", "all_layer_diagonal", "block_laplace", "lofi"}:
            candidate_gradients = np.stack([network.action_gradient(x, action) for action in range(ACTION_COUNT)])
        if method == "current_full_ggn_cg":
            features = np.stack(
                [network.action_gradient(old_x, old_action) for old_x, old_action in zip(history_x, history_actions, strict=True)]
            ) if history_x else np.empty((0, parameter_count))
            widths, iterations = _cg_widths(
                features, candidate_gradients, ridge=ridge, noise_variance=noise_variance,
                tolerance=float(config["cg"]["relative_residual"]),
                maximum_iterations=int(config["cg"]["max_iterations"]),
            )
            sample_cvps += iterations * len(history_x)
        elif method in {"historical_neural_ucb", "neural_ts"}:
            features = np.stack(historical_gradients) if historical_gradients else np.empty((0, parameter_count))
            widths, iterations = _cg_widths(
                features, candidate_gradients, ridge=ridge, noise_variance=noise_variance,
                tolerance=float(config["cg"]["relative_residual"]),
                maximum_iterations=int(config["cg"]["max_iterations"]),
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
            features = np.stack(historical_gradients) if historical_gradients else np.empty((0, parameter_count))
            widths = _lofi_widths(features, candidate_gradients, ridge=ridge, noise_variance=noise_variance, rank=int(config["lofi_rank"]))
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
                "cumulative_sample_cvps": sample_cvps,
            }
        )
        if candidate_gradients is not None:
            selected_gradient = candidate_gradients[action].copy()
            historical_gradients.append(selected_gradient)
            diagonal += selected_gradient * selected_gradient / noise_variance
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
        "implementation": "local_matched_reimplementation_not_official",
    }
    return records, summary


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    atomic_write_text(path, "".join(canonical_json(record) + "\n" for record in records), encoding="ascii")
    write_sha256_sidecar(path)


def run_benchmark(config: dict[str, Any], output_root: str | Path, *, overwrite: bool = False) -> dict[str, Any]:
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
    for method in methods:
        for config_index, hyperparameters in enumerate(grid):
            for seed in config["seed_sets"]["tuning"]:
                records, summary = run_policy(config, data, pretrained, method, int(seed), "tuning", hyperparameters)
                summary["config_index"] = config_index
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
    for method in methods:
        hyperparameters = dict(selection["selected"][method]["hyperparameters"])
        for seed in config["seed_sets"]["evaluation"]:
            records, summary = run_policy(config, data, pretrained, method, int(seed), "evaluation", hyperparameters)
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
        "provenance": collect_run_metadata(repository=Path(__file__).resolve().parents[1], packages=("numpy", "torch", "torchvision", "psutil")),
        "limitations": [
            "all neural baselines are local matched reimplementations, not official packages",
            "the full current-GGN method has quadratic replay work and no truncation is substituted",
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
    return parser


def main() -> None:
    args = _parser().parse_args()
    config = load_config(args.config, args.profile)
    result = run_benchmark(config, args.output_root, overwrite=args.overwrite)
    print(canonical_json(result))


if __name__ == "__main__":
    main()
