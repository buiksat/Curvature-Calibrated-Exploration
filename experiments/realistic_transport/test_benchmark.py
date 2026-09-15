from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import pytest
from experiments.realistic_transport.aggregate import (
    _validate_ratio_records,
    _validate_round_semantics,
)
from experiments.realistic_transport.benchmark import (
    BenchmarkSettings,
    corrected_center,
    corrected_confidence_radius,
    OptimizerSpec,
    run_method_grid,
    run_policy_trajectory,
    run_tuning_trajectory,
    SelectedHistory,
    tangent_center,
)
from experiments.realistic_transport.configuration import (
    EXPECTED_METHODS,
    load_config,
    method_spec,
)
from experiments.realistic_transport.environment import (
    CONTROLLED_MISSPECIFIED_TASK,
    LABEL_TASK,
    PolicyRound,
    PotentialOutcomeStream,
    REALIZABLE_TASK,
)
from experiments.realistic_transport.features import FeatureMapSpec
from experiments.realistic_transport.model import scaled_tanh_gradient, scaled_tanh_mean


@dataclass(frozen=True)
class _ToyEnvironment:
    task_name: str
    feature_map: FeatureMapSpec
    theta: np.ndarray | None
    width: float = 100.0
    noise_proxy: float = 0.25
    rho: float = 0.0

    @property
    def context_dimension(self) -> int:
        return self.feature_map.context_dimension

    @property
    def action_count(self) -> int:
        return self.feature_map.action_count

    @property
    def feature_dimension(self) -> int:
        return self.feature_map.feature_dimension

    @property
    def theta_star(self) -> np.ndarray | None:
        return self.theta

    @property
    def theorem_applicable(self) -> bool:
        return self.task_name != LABEL_TASK

    @property
    def historical_misspecification_envelope(self) -> float | None:
        return None if self.task_name == LABEL_TASK else self.rho

    @property
    def current_misspecification_envelope(self) -> float | None:
        return self.historical_misspecification_envelope

    def feature_matrix(self, context: np.ndarray) -> np.ndarray:
        return self.feature_map.all_action_features(context)


def _toy_environment(task: str) -> _ToyEnvironment:
    feature_map = FeatureMapSpec(context_dimension=8, action_count=7)
    theta = None
    noise_proxy = 0.5 if task == LABEL_TASK else 0.25
    rho = 0.0
    if task != LABEL_TASK:
        theta = np.linspace(-1.0, 1.0, feature_map.feature_dimension)
        theta /= np.linalg.norm(theta)
    if task == CONTROLLED_MISSPECIFIED_TASK:
        rho = 0.025
    return _ToyEnvironment(
        task_name=task,
        feature_map=feature_map,
        theta=theta,
        noise_proxy=noise_proxy,
        rho=rho,
    )


def _toy_stream(
    environment: _ToyEnvironment,
    *,
    phase: str = "evaluation",
    rounds: int = 3,
) -> PotentialOutcomeStream:
    generator = np.random.default_rng(8102)
    contexts = generator.normal(size=(rounds, environment.context_dimension))
    contexts /= np.maximum(1.0, np.linalg.norm(contexts, axis=1))[:, None]
    labels = np.arange(rounds, dtype=np.int64) % environment.action_count
    means = np.empty((rounds, environment.action_count), dtype=np.float64)
    for index, context in enumerate(contexts):
        if environment.task_name == LABEL_TASK:
            means[index] = 0.1
            means[index, labels[index]] = 0.9
        else:
            features = environment.feature_matrix(context)
            means[index] = scaled_tanh_mean(
                environment.theta_star, features, environment.width
            )
            if environment.task_name == CONTROLLED_MISSPECIFIED_TASK:
                phases = np.arange(environment.action_count, dtype=np.float64)
                means[index] += environment.rho * np.sin(
                    phases + float(np.sum(context))
                )
    if environment.task_name == LABEL_TASK:
        rewards = np.zeros_like(means)
        rewards[np.arange(rounds), labels] = 1.0
        noises = rewards - means
    else:
        noises = np.zeros_like(means)
        rewards = means.copy()
    return PotentialOutcomeStream(
        task_name=environment.task_name,
        seed=100,
        phase=phase,
        row_indices=np.arange(rounds, dtype=np.int64),
        contexts=contexts,
        _labels=labels,
        means=means,
        noises=noises,
        rewards=rewards,
        _feature_map=environment.feature_map,
    )


def _settings(*, prefixes: tuple[int, ...] = (1, 2, 3)) -> BenchmarkSettings:
    return BenchmarkSettings(
        optimizer=OptimizerSpec(learning_rate=1e-4, steps_per_round=1),
        prefixes=prefixes,
        linucb_alpha=0.5,
    )


def test_corrected_center_and_confidence_radius_identities() -> None:
    environment = _toy_environment(REALIZABLE_TASK)
    context = np.linspace(-0.4, 0.4, environment.context_dimension)
    features = environment.feature_matrix(context)
    theta = np.linspace(-0.2, 0.2, environment.feature_dimension)
    theta_hat = np.linspace(0.1, -0.1, environment.feature_dimension)
    corrected = corrected_center(theta, theta_hat, features, width=environment.width)
    tangent = tangent_center(theta, theta_hat, features, width=environment.width)
    means = scaled_tanh_mean(theta, features, environment.width)
    queries = scaled_tanh_gradient(theta, features, environment.width)

    np.testing.assert_allclose(
        corrected - tangent,
        means - queries @ theta,
        rtol=0.0,
        atol=2e-15,
    )
    beta, statistical, historical = corrected_confidence_radius(
        2.0,
        delta=0.05,
        ridge=1.0,
        reference_norm_bound=1.0,
        historical_error_energy=0.25,
        noise_proxy=0.25,
    )
    assert historical == 2.0
    assert beta == statistical + historical


def test_selected_history_frozen_metric_and_welford_q_are_dimension_general() -> None:
    history = SelectedHistory(dimension=5, ridge=2.0, noise_proxy=0.5)
    first_theta = np.asarray([0.1, 0.0, 0.0, 0.0, 0.0])
    second_theta = np.asarray([0.0, 0.2, 0.0, 0.0, 0.0])
    first_query = np.asarray([1.0, 0.0, 0.0, 0.0, 0.0])
    second_query = np.asarray([0.0, 1.0, 0.0, 0.0, 0.0])
    for theta, query in ((first_theta, first_query), (second_theta, second_query)):
        history.append(
            feature=query,
            collection_theta=theta,
            collection_query=query,
            pseudo_response=0.5,
            reward=0.5,
            linearization_envelope=0.1,
            misspecification_envelope=0.2,
        )
    expected = 2.0 * np.eye(5) + 4.0 * (
        np.outer(first_query, first_query) + np.outer(second_query, second_query)
    )
    np.testing.assert_allclose(history.frozen_metric, expected)
    current = np.asarray([0.1, 0.2, 0.0, 0.0, 0.0])
    direct_q = sum(
        np.linalg.norm(current - value) ** 2 for value in (first_theta, second_theta)
    )
    assert history.path_q(current) == pytest.approx(direct_q)
    assert history.historical_error_energy == pytest.approx(2.0 * 0.3**2)


def test_all_thirteen_methods_run_with_fixed_ties_and_separate_histories() -> None:
    environment = _toy_environment(REALIZABLE_TASK)
    stream = _toy_stream(environment, rounds=2)
    results = run_method_grid(environment, stream, _settings(prefixes=(1, 2)))
    config = load_config(
        "experiments/configs/realistic_transport_covtype.yaml", "smoke"
    )

    assert tuple(result.method for result in results) == EXPECTED_METHODS
    assert all(len(result.rounds) == 2 for result in results)
    for result in results:
        specification = method_spec(result.method)
        _validate_round_semantics(
            result.rounds,
            task=environment.task_name,
            method=result.method,
            feature_dimension=environment.feature_dimension,
            action_count=environment.action_count,
        )
        _validate_ratio_records(
            result.rounds,
            method=result.method,
            rounds=2,
            config=config,
            action_count=environment.action_count,
        )
        scores = np.asarray(result.rounds[0]["scores"])
        expected_action = int(np.flatnonzero(scores == np.max(scores))[0])
        assert result.rounds[0]["selected_action"] == expected_action
        assert result.rounds[0]["score_tie_count"] == int(
            np.count_nonzero(scores == np.max(scores))
        )
        for record in result.rounds:
            current = record["current_exact_widths"]
            assert current == record["current_widths"]
            if (
                specification.metric == "current_exact"
                and specification.solver == "cholesky"
            ):
                assert current is not None
                np.testing.assert_allclose(current, record["score_widths"])
            elif specification.solver == "cg":
                assert (current is not None) is record["diagnostic_checkpoint"]
            else:
                assert current is None
    for result in results:
        assert set(result.prefix_summaries) == {1, 2}
        assert not result.summary["floating_point_checks_are_verified_certificates"]
        assert not result.summary["post_selection_refinement"]
        assert result.rounds[-1]["action_oracle_error"] == 0.0
    cg_methods = [
        result for result in results if result.summary["cg_tolerance"] is not None
    ]
    assert len(cg_methods) == 6
    assert all(
        not result.rounds[-1]["solver_post_selection_refinement"]
        for result in cg_methods
    )
    approximate = [
        result for result in results if result.method.startswith("transport_nystrom_")
    ]
    assert len(approximate) == 5
    assert all(0.0 < result.rounds[-1]["kappa_minus"] <= 1.0 for result in approximate)


def test_controlled_misspecification_uses_uniform_historical_and_current_envelopes() -> (
    None
):
    environment = _toy_environment(CONTROLLED_MISSPECIFIED_TASK)
    result = run_policy_trajectory(
        environment,
        _toy_stream(environment, rounds=2),
        "transport_exact_corrected_cholesky",
        _settings(prefixes=(2,)),
    )
    first, second = result.rounds

    assert first["current_misspecification_envelope"] == environment.rho
    assert first["historical_error_energy_before"] == 0.0
    expected_energy = (first["current_linearization_envelope"] + environment.rho) ** 2
    assert first["historical_error_energy_after"] == pytest.approx(expected_energy)
    assert second["beta_historical"] == pytest.approx(
        np.sqrt(expected_energy) / environment.noise_proxy
    )
    assert first["current_taylor_envelope_valid"]
    assert first["current_misspecification_envelope_valid"]


def test_label_task_is_explicitly_an_uncertified_stress_diagnostic() -> None:
    environment = _toy_environment(LABEL_TASK)
    result = run_policy_trajectory(
        environment,
        _toy_stream(environment, rounds=2),
        "transport_exact_corrected_cholesky",
        _settings(prefixes=(2,)),
    )

    assert result.summary["confidence_role"] == "uncertified_stress_diagnostic"
    assert not result.summary["theorem_applicable"]
    assert result.summary["sharp_theorem_rhs"] is None
    assert 0.0 <= result.summary["action_accuracy"] <= 1.0
    assert all(
        round_record["historical_misspecification_envelope"] == 0.0
        for round_record in result.rounds
    )


class _RewardOrderGuard:
    def __init__(self, stream: PotentialOutcomeStream) -> None:
        self._stream = stream
        self.task_name = stream.task_name
        self.seed = stream.seed
        self.phase = stream.phase
        self.rounds = stream.rounds
        self.action_count = stream.action_count
        self._reward_observed = False

    def policy_round(self, round_index: int) -> PolicyRound:
        self._reward_observed = False
        return self._stream.policy_round(round_index)

    def observe(self, round_index: int, action: int) -> float:
        self._reward_observed = True
        return self._stream.observe(round_index, action)

    @property
    def means(self) -> np.ndarray:
        if not self._reward_observed:
            raise AssertionError("policy inspected truth before selecting an action")
        return self._stream.means

    @property
    def noises(self) -> np.ndarray:
        if not self._reward_observed:
            raise AssertionError("policy inspected noise before selecting an action")
        return self._stream.noises

    def evaluation_label(self, round_index: int) -> int:
        if not self._reward_observed:
            raise AssertionError("policy inspected label before selecting an action")
        return self._stream.evaluation_label(round_index)


def test_action_score_does_not_read_current_reward_truth_or_label() -> None:
    environment = _toy_environment(REALIZABLE_TASK)
    guarded = _RewardOrderGuard(_toy_stream(environment, rounds=2))
    result = run_policy_trajectory(
        environment,
        guarded,
        "transport_exact_corrected_cg_1e-4",
        _settings(prefixes=(2,)),
    )
    assert len(result.rounds) == 2


def test_uniform_random_tuning_is_deterministic_and_post_burn_in_only() -> None:
    environment = _toy_environment(REALIZABLE_TASK)
    stream = _toy_stream(environment, phase="tuning", rounds=4)
    optimizer = OptimizerSpec(learning_rate=1e-4, steps_per_round=1)
    first = run_tuning_trajectory(environment, stream, optimizer, burn_in=1)
    second = run_tuning_trajectory(environment, stream, optimizer, burn_in=1)

    assert [record["behavior_action"] for record in first.rounds] == [
        record["behavior_action"] for record in second.rounds
    ]
    assert first.summary == second.summary
    assert first.summary["post_burn_in_round_count"] == 3
    expected = np.mean(
        [
            record["prediction_mse_all_actions"]
            for record in first.rounds
            if record["included_after_burn_in"]
        ]
    )
    assert first.summary["mean_all_action_prediction_mse"] == pytest.approx(expected)


def test_tuning_rejects_evaluation_streams() -> None:
    environment = _toy_environment(REALIZABLE_TASK)
    with pytest.raises(ValueError, match="evaluation"):
        run_tuning_trajectory(
            environment,
            _toy_stream(environment, phase="evaluation", rounds=2),
            OptimizerSpec(learning_rate=1e-4, steps_per_round=1),
            burn_in=1,
        )


def test_nystrom_dense_diagnostics_run_only_at_frozen_checkpoints() -> None:
    environment = _toy_environment(REALIZABLE_TASK)
    settings = BenchmarkSettings(
        optimizer=OptimizerSpec(learning_rate=1e-4, steps_per_round=1),
        prefixes=(),
        diagnostic_checkpoints=(1,),
    )
    result = run_policy_trajectory(
        environment,
        _toy_stream(environment, rounds=3),
        "transport_nystrom_r16_cg_1e-2",
        settings,
    )

    assert result.rounds[0]["diagnostic_checkpoint"]
    assert not result.rounds[1]["diagnostic_checkpoint"]
    assert result.rounds[2]["diagnostic_checkpoint"]
    assert result.rounds[0]["d_Th"] is not None
    assert result.rounds[1]["d_Th"] is None
    assert result.rounds[2]["d_Th"] is not None
    assert result.rounds[1]["nystrom_operator_tail"] is None
    assert result.rounds[1]["solver_exact_width"] is None
    assert result.rounds[1]["exact_A_width_over_exact_V_width"] is None
    assert result.rounds[1]["operational_upper_width_over_exact_V_width"] is None
    assert result.rounds[1]["nystrom_operator_storage_bytes"] < (
        environment.feature_dimension**2 * 8
    )
    for record in (result.rounds[0], result.rounds[2]):
        assert record["solver_upper_over_exact"] == record["solver_upper_over_exact_A"]
        assert (
            record["solver_upper_over_exact_all_actions"]
            == record["solver_upper_over_exact_A_all_actions"]
        )
        if record["operational_upper_width_over_exact_V_width"] is not None:
            assert record[
                "operational_upper_width_over_exact_V_width"
            ] == pytest.approx(
                record["solver_upper_over_exact_A"]
                * record["exact_A_width_over_exact_V_width"]
            )
    assert all(
        record["operator_construction_seconds"]
        >= record["replay_gradient_construction_seconds"]
        for record in result.rounds
    )
    assert result.summary["analytic_certificate_valid_in_exact_arithmetic"]
    assert result.summary["float64_diagnostic_pass"]
    assert not result.summary["verified_numerical_certificate"]


def test_nystrom_replay_construction_is_charged_to_algorithm_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = SelectedHistory.current_replay_gradients

    def delayed_replay(
        self: SelectedHistory, theta: np.ndarray, width: float
    ) -> np.ndarray:
        time.sleep(0.01)
        return original(self, theta, width)

    monkeypatch.setattr(SelectedHistory, "current_replay_gradients", delayed_replay)
    environment = _toy_environment(REALIZABLE_TASK)
    result = run_policy_trajectory(
        environment,
        _toy_stream(environment, rounds=3),
        "transport_nystrom_r16_cg_1e-2",
        _settings(),
    )
    replay_seconds = sum(
        record["replay_gradient_construction_seconds"] for record in result.rounds
    )
    operator_seconds = sum(
        record["operator_construction_seconds"] for record in result.rounds
    )
    algorithm_seconds = sum(record["algorithm_seconds"] for record in result.rounds)
    assert replay_seconds >= 0.025
    assert operator_seconds >= replay_seconds
    assert algorithm_seconds >= operator_seconds
