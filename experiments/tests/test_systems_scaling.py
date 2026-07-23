from __future__ import annotations

import json

import numpy as np
import scipy.sparse.linalg as spla

from experiments.config import load_config
from experiments.run_systems_scaling import (
    ADVANCED_CPU_GRID,
    BENCHMARK_KIND,
    FULL_GRID,
    LAST_LAYER_RESTRICTION,
    METHODS,
    SMOKE_GRID,
    CurvatureOperator,
    advanced_systems_grid,
    batched_independent_cg,
    fixed_iteration_cg,
    main,
    run_systems_scaling,
    save_run,
    systems_grid,
)


def _config() -> dict[str, object]:
    return {
        "name": "systems_scaling_test",
        "profile": "smoke",
        "timing_repetitions": 1,
        "curvature": {"damping": 0.7},
        "scaling_grid": {"d": [8], "n": [12], "K": [2], "I": [4]},
        "last_layer_fraction": 0.25,
        "provenance": {"packages": ["numpy", "scipy"]},
    }


def _deterministic(record: dict[str, object]) -> dict[str, object]:
    ignored = {
        "wall_time_seconds",
        "wall_time_min_seconds",
        "wall_time_repetitions_seconds",
        "curvature_matvec_seconds",
        "dense_inverse_reference_seconds",
        "exact_reference_seconds",
        "rss_before_bytes",
        "rss_after_bytes",
        "rss_bytes",
        "rss_delta_bytes",
        "peak_host_memory_bytes",
    }
    return {key: value for key, value in record.items() if key not in ignored}


def test_required_feasible_grids() -> None:
    assert SMOKE_GRID == {
        "d": (32, 64),
        "n": (16, 64),
        "K": (3, 5),
        "I": (5, 15),
    }
    assert FULL_GRID == {
        "d": (32, 64, 128),
        "n": (32, 128, 512),
        "K": (5, 10),
        "I": (5, 15, 30),
    }
    assert len(systems_grid({"profile": "smoke"})) == 16
    assert len(systems_grid({"profile": "full"})) == 54
    assert systems_grid(
        {
            "profile": "smoke",
            "dimensions": [7],
            "buffer_sizes": [9],
            "action_counts": [2],
            "cg_iteration_budgets": [3],
        }
    ) == ((7, 9, 2, 3),)

    full_config = load_config(
        "experiments/configs/systems_scaling.yaml", profile="full"
    )
    advanced = advanced_systems_grid(full_config)
    assert {point[0] for point in advanced} == {512, 2048, 8192}
    assert ADVANCED_CPU_GRID["d"][-1] == 8192


def test_protocol_method_aliases_are_preserved_in_records() -> None:
    config = {
        **_config(),
        "methods": ["full_ggn_cg", "lanczos_ritz"],
    }
    run = run_systems_scaling(config, 5)

    assert [record["method"] for record in run.records] == [
        "full_ggn_cg",
        "lanczos_ritz",
    ]
    assert [record["method_implementation"] for record in run.records] == [
        "full_cg",
        "lanczos",
    ]


def test_all_methods_are_deterministic_and_account_for_cvps() -> None:
    first = run_systems_scaling(_config(), 23)
    second = run_systems_scaling(_config(), 23)

    assert first.summary == second.summary
    assert len(first.records) == len(METHODS)
    assert {record["method"] for record in first.records} == set(METHODS)
    assert [_deterministic(record) for record in first.records] == [
        _deterministic(record) for record in second.records
    ]
    by_method = {record["method"]: record for record in first.records}
    assert by_method["dense_exact"]["max_relative_energy_error"] < 1e-13
    assert by_method["dense_exact"]["sample_cvp_count"] == 0
    assert by_method["diagonal"]["sample_cvp_count"] == 0
    assert by_method["last_layer_block"]["sample_cvp_count"] == 0
    assert by_method["full_cg"]["sample_cvp_count"] == (
        by_method["full_cg"]["operator_matvec_count"] * 12
    )
    assert by_method["lanczos"]["sample_cvp_count"] == (
        by_method["lanczos"]["operator_matvec_count"] * 12
    )
    assert by_method["full_cg"]["operator_matvec_count"] <= 2 * 4
    assert by_method["lanczos"]["operator_matvec_count"] <= 4
    for method in ("batched_cg", "batched_jacobi_cg"):
        record = by_method[method]
        assert record["batch_operator_call_count"] > 0
        assert record["operator_matvec_count"] == sum(
            record["per_action_operator_matvecs"]
        )
        assert record["equivalent_sample_cvp_count"] == (
            record["operator_matvec_count"] * 12
        )
        assert len(record["per_action_explicit_relative_residual"]) == 2
        assert record["max_explicit_relative_residual"] == max(
            record["per_action_explicit_relative_residual"]
        )
    assert by_method["batched_cg"]["preconditioner"] == "none"
    assert (
        by_method["batched_jacobi_cg"]["preconditioner"]
        == "symmetric_jacobi"
    )

    for record in first.records:
        assert record["width_sandwich_holds"] is True
        assert record["estimated_working_memory_bytes"] > 0
        assert record["peak_host_memory_bytes"] >= 0
        assert record["last_layer_restriction"] == LAST_LAYER_RESTRICTION

    restricted = by_method["last_layer_block"]
    assert restricted["last_layer_block_dimension"] == 2
    assert restricted["last_layer_block_start"] == 6
    assert "cross-block curvature" in restricted["last_layer_restriction"]
    assert first.summary["benchmark_kind"] == BENCHMARK_KIND
    assert first.summary["synthetic_cpu_parameter_vector_benchmark"] is True
    assert first.summary["accelerator_benchmark"] is False
    assert first.summary["foundation_model_benchmark"] is False


def test_batched_cg_matches_independent_scalar_cg_and_explicit_residuals() -> None:
    rng = np.random.default_rng(91)
    operator = CurvatureOperator(rng.normal(size=(9, 6)), damping=0.8)
    right_hand_sides = rng.normal(size=(3, 6))

    batched = batched_independent_cg(
        operator, right_hand_sides, 4, relative_tolerance=0.0
    )
    scalar = [
        fixed_iteration_cg(operator, right_hand_side, 4)
        for right_hand_side in right_hand_sides
    ]
    scalar_solutions = np.stack([result.solution for result in scalar])
    np.testing.assert_allclose(
        batched.solutions, scalar_solutions, rtol=2e-14, atol=2e-14
    )
    explicit = right_hand_sides - operator.matmat(batched.solutions)
    expected_relative = np.linalg.norm(explicit, axis=1) / np.linalg.norm(
        right_hand_sides, axis=1
    )
    np.testing.assert_allclose(
        batched.explicit_relative_residuals,
        expected_relative,
        rtol=2e-14,
        atol=2e-14,
    )
    assert batched.batch_operator_calls == 5
    assert batched.equivalent_operator_matvecs == 15
    np.testing.assert_array_equal(batched.per_action_operator_matvecs, [5, 5, 5])


def test_symmetric_jacobi_batched_cg_matches_scalar_scipy_pcg() -> None:
    rng = np.random.default_rng(109)
    operator = CurvatureOperator(rng.normal(size=(11, 7)), damping=0.6)
    right_hand_sides = rng.normal(size=(4, 7))
    budget = 5
    batched = batched_independent_cg(
        operator,
        right_hand_sides,
        budget,
        relative_tolerance=0.0,
        preconditioner="symmetric_jacobi",
    )

    linear_operator = spla.LinearOperator(
        operator.shape, matvec=operator.matvec, dtype=np.float64
    )
    inverse_diagonal = 1.0 / operator.diagonal()
    jacobi = spla.LinearOperator(
        operator.shape,
        matvec=lambda vector: inverse_diagonal * vector,
        dtype=np.float64,
    )
    scalar_solutions = []
    for rhs in right_hand_sides:
        solution, info = spla.cg(
            linear_operator,
            rhs,
            M=jacobi,
            maxiter=budget,
            rtol=0.0,
            atol=0.0,
        )
        assert info in {0, budget}
        scalar_solutions.append(solution)
    np.testing.assert_allclose(
        batched.solutions,
        np.asarray(scalar_solutions),
        rtol=3e-13,
        atol=3e-13,
    )
    explicit = right_hand_sides - operator.matmat(batched.solutions)
    np.testing.assert_allclose(
        batched.explicit_relative_residuals,
        np.linalg.norm(explicit, axis=1) / np.linalg.norm(right_hand_sides, axis=1),
        rtol=2e-14,
        atol=2e-14,
    )


def test_jacobi_pcg_energy_width_and_preconditioned_residual_certificates() -> None:
    rng = np.random.default_rng(110)
    operator = CurvatureOperator(rng.normal(size=(17, 8)), damping=0.75)
    right_hand_sides = rng.normal(size=(5, 8))
    result = batched_independent_cg(
        operator,
        right_hand_sides,
        4,
        relative_tolerance=0.0,
        preconditioner="symmetric_jacobi",
    )

    dense = operator.to_dense()
    diagonal = operator.diagonal()
    inverse_root = np.diag(1.0 / np.sqrt(diagonal))
    transformed = inverse_root @ dense @ inverse_root
    eigenvalues = np.linalg.eigvalsh(transformed)
    transformed_condition = float(eigenvalues[-1] / eigenvalues[0])
    inverse_diagonal = 1.0 / diagonal

    for rhs, approximate in zip(
        right_hand_sides, result.solutions, strict=True
    ):
        exact = np.linalg.solve(dense, rhs)
        error = exact - approximate
        exact_energy_squared = float(exact @ dense @ exact)
        relative_energy_error = float(
            np.sqrt((error @ dense @ error) / exact_energy_squared)
        )
        residual = rhs - dense @ approximate
        preconditioned_residual_ratio = float(
            np.sqrt(
                (residual @ (inverse_diagonal * residual))
                / (rhs @ (inverse_diagonal * rhs))
            )
        )
        assert relative_energy_error <= (
            np.sqrt(transformed_condition) * preconditioned_residual_ratio
            + 2e-13
        )

        exact_width_squared = float(rhs @ exact)
        approximate_width_squared = float(rhs @ approximate)
        assert abs(approximate_width_squared - exact_width_squared) <= (
            relative_energy_error * exact_width_squared + 2e-13
        )


def test_advanced_cpu_grid_uses_sample_space_reference_and_only_batched_methods() -> None:
    config = {
        **_config(),
        "methods": ["batched_cg"],
        "advanced_cpu_grid": {
            "enabled": True,
            "dimensions": [256],
            "sample_counts": [4],
            "action_counts": [2],
            "iteration_budgets": [3],
            "methods": ["batched_cg", "batched_jacobi_cg"],
        },
    }
    run = run_systems_scaling(config, 77)
    advanced = [
        record
        for record in run.records
        if record["benchmark_grid"] == "advanced_cpu_grid"
    ]

    assert len(advanced) == 2
    assert {record["method"] for record in advanced} == {
        "batched_cg",
        "batched_jacobi_cg",
    }
    for record in advanced:
        assert record["dimension"] == 256
        assert record["dense_diagnostic_reference_bytes"] == 0
        assert record["exact_reference_implementation"] == (
            "woodbury_float64_sample_space_cholesky"
        )
        assert len(record["per_action_explicit_relative_residual"]) == 2
        assert record["synthetic_cpu_parameter_vector_benchmark"] is True
        assert record["accelerator_benchmark"] is False
        assert record["foundation_model_benchmark"] is False


def test_save_run_writes_jsonl(tmp_path) -> None:
    run = run_systems_scaling(_config(), 31)
    destination = save_run(run, tmp_path / "systems", _config(), overwrite=True)

    manifest = json.loads(
        (destination / "manifest.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    raw = [
        json.loads(line)
        for line in (destination / "raw.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert manifest["config"]["execution"]["last_layer_restriction"] == (
        LAST_LAYER_RESTRICTION
    )
    assert manifest["config"]["execution"]["benchmark_kind"] == BENCHMARK_KIND
    assert len(raw) == len(METHODS)
    assert [record["round"] for record in raw] == list(range(len(METHODS)))
    summary = json.loads(
        (destination / "summary.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert summary["record_count"] == len(METHODS)


def test_cli_accepts_documented_config_flag(tmp_path) -> None:
    assert (
        main(
            [
                "--config",
                "experiments/configs/systems_scaling.yaml",
                "--profile",
                "smoke",
                "--seed-set",
                "evaluation",
                "--output-root",
                str(tmp_path),
                "--overwrite",
            ]
        )
        == 0
    )
    destination = tmp_path / "systems_scaling" / "smoke" / "evaluation" / "seed-140"
    assert (destination / "raw.jsonl").is_file()
