"""Portable bootstrap checks must reject incomplete or inconsistent seed evidence."""
import copy
import hashlib
import json

import pytest

from experiments.aggregate_transport_instantiation import _bootstrap_counts, _bootstrap_interval
from experiments.config import config_digest
from experiments.logging_utils import derive_seed
from tools.verify_review_experiment_export import ExportError, verify_export


@pytest.fixture
def compact_export(tmp_path):
    config = {
        "seed_sets": {"evaluation": [5, 2, 17]},
        "methods": ["transport_hessian", "transport_endpoint", "frozen_reference", "naive_current"],
        "horizons": [3, 5], "target_D": [0.1, 0.2],
        "reporting": {"primary_horizon": 5},
        "statistics": {"paired_bootstrap_resamples": 150, "paired_bootstrap_level": 0.95},
    }
    digest = config_digest(config)

    def put(name, value):
        (tmp_path / name).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")

    put("execution_config.json", config)
    put("selection.json", {"selected": "synthetic test fixture"})
    selection_sha = hashlib.sha256((tmp_path / "selection.json").read_bytes()).hexdigest()
    rows = []
    for horizon in config["horizons"]:
        for target in config["target_D"]:
            for index, method in enumerate(config["methods"]):
                for seed in config["seed_sets"]["evaluation"]:
                    rows.append({
                        "horizon": horizon, "target_D": target, "method": method, "seed": seed,
                        "phase": "evaluation", "config_digest": digest,
                        "selection_sha256": selection_sha,
                        "cumulative_pseudo_regret": seed ** 2 / 17 + index * (seed % 3 - 1) + target * horizon,
                    })
    aggregate = {
        "config_digest": digest, "selection_sha256": selection_sha,
        "evaluation_seeds": config["seed_sets"]["evaluation"], "methods": config["methods"],
        "horizons": config["horizons"], "target_D": config["target_D"],
        "expected_run_count": len(rows), "completed_run_count": len(rows), "full_grid_complete": True,
        "paired_bootstrap": {"resamples": 150, "level": 0.95, "child_seeds": []},
        "policy_outcomes": [],
    }
    for target in config["target_D"]:
        child = derive_seed(int(digest[:16], 16), "transport_instantiation", "bootstrap", 5, target)
        aggregate["paired_bootstrap"]["child_seeds"].append({"horizon": 5, "target_D": target, "seed": child})
        counts = _bootstrap_counts(child, 3, 150)

        def values(method):
            return [row["cumulative_pseudo_regret"] for row in rows
                    if row["horizon"] == 5 and row["target_D"] == target and row["method"] == method]

        reference = values("transport_hessian")
        for method in config["methods"]:
            regrets = values(method)
            outcome = {"horizon": 5, "target_D": target, "method": method, "run_count": 3}
            for name, series in (("cumulative_pseudo_regret", regrets),
                                 ("paired_difference_from_transport_hessian",
                                  [value - baseline for value, baseline in zip(regrets, reference)])):
                interval = _bootstrap_interval(series, counts, 0.95)
                outcome[name] = {"mean": interval["mean"], "bootstrap_mean_interval": interval}
            aggregate["policy_outcomes"].append(outcome)

    def save(new_rows=None, new_aggregate=None):
        # Deliberately reverse physical row order: pairing uses declared seed order.
        selected_rows = rows if new_rows is None else new_rows
        (tmp_path / "seed_summaries.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in reversed(selected_rows)))
        put("aggregate_compact.json", aggregate if new_aggregate is None else new_aggregate)
        files = [{"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "bytes": path.stat().st_size}
                 for path in tmp_path.iterdir() if path.name != "export_manifest.json"]
        put("export_manifest.json", {"schema_version": 1, "files": files, "source": {
            "execution_sha256": hashlib.sha256((tmp_path / "execution_config.json").read_bytes()).hexdigest()}})

    save()
    return tmp_path, rows, aggregate, save


def test_independent_draws_match_aggregator_with_nontrivial_pairing(compact_export):
    root, rows, _, _ = compact_export
    report = verify_export(root)
    assert report["seed_summaries"] == len(rows)
    assert report["terminal_intervals_recomputed"] == 16
    assert "not independently verified" in report["raw_trajectories"]


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "changed_regret", "wrong_seed"])
def test_semantic_tampering_fails_even_with_updated_file_hashes(compact_export, mutation):
    root, rows, aggregate, save = compact_export
    rows, aggregate = copy.deepcopy(rows), copy.deepcopy(aggregate)
    if mutation == "duplicate":
        rows.append(rows[0])
    elif mutation == "missing":
        rows.pop()
    elif mutation == "changed_regret":
        next(row for row in rows if row["horizon"] == 5)["cumulative_pseudo_regret"] += 0.25
    else:
        aggregate["paired_bootstrap"]["child_seeds"][0]["seed"] += 1
    save(rows, aggregate)
    with pytest.raises(ExportError):
        verify_export(root)


def test_changed_export_bytes_fail_before_numerical_replay(compact_export):
    root, _, _, _ = compact_export
    with (root / "seed_summaries.jsonl").open("a") as handle:
        handle.write("\n")
    with pytest.raises(ExportError, match="hash/size mismatch"):
        verify_export(root)
