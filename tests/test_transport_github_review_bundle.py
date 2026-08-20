"""Tests for the GitHub-only review bundle exporter and detached verifier.

These exercise the auditability tooling, not the study.  They must pass in a
checkout where `results/raw/` is absent, so nothing here reads a raw file.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

import export_transport_github_review_bundle as exporter  # noqa: E402
import verify_transport_committed_evidence as verifier  # noqa: E402


# --------------------------------------------------------------------------
# canonical serialization
# --------------------------------------------------------------------------


def test_canonical_json_sorts_keys_and_is_compact():
    assert exporter.canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_canonical_json_is_ascii_only():
    assert exporter.canonical_json({"k": "é"}) == '{"k":"\\u00e9"}'


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_canonical_json_rejects_nonfinite(value):
    with pytest.raises(ValueError):
        exporter.canonical_json({"k": value})


def test_load_json_strict_rejects_duplicate_keys(tmp_path):
    path = tmp_path / "dup.json"
    path.write_text('{"a": 1, "a": 2}', encoding="utf-8")
    with pytest.raises(exporter.ReviewBundleError, match="duplicate JSON key"):
        exporter.load_json_strict(path)


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_load_json_strict_rejects_nonfinite_literals(tmp_path, literal):
    path = tmp_path / "nan.json"
    path.write_text(f'{{"a": {literal}}}', encoding="utf-8")
    with pytest.raises(exporter.ReviewBundleError, match="non-finite JSON literal"):
        exporter.load_json_strict(path)


def test_load_json_strict_rejects_malformed_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"a": ', encoding="utf-8")
    with pytest.raises(exporter.ReviewBundleError, match="cannot parse"):
        exporter.load_json_strict(path)


def test_assert_all_finite_reports_location():
    with pytest.raises(exporter.ReviewBundleError, match=r"root\.a\[1\]\.b"):
        exporter.assert_all_finite({"a": [0.0, {"b": float("inf")}]}, where="root")


# --------------------------------------------------------------------------
# chunking
# --------------------------------------------------------------------------


def _records(count: int, payload: str = "x" * 100):
    return [{"i": i, "payload": payload} for i in range(count)]


def test_chunking_preserves_every_record(tmp_path):
    writer = exporter.BundleWriter(tmp_path)
    records = _records(5000)
    parts = writer.emit_jsonl_parts("data", records, semantic_source="test")
    assert sum(p["record_count"] for p in parts) == len(records)
    replayed = []
    for part in parts:
        for line in (tmp_path / part["path"]).read_text(encoding="utf-8").splitlines():
            replayed.append(json.loads(line))
    assert replayed == records


def test_chunking_respects_the_size_ceiling(tmp_path):
    writer = exporter.BundleWriter(tmp_path)
    parts = writer.emit_jsonl_parts("data", _records(20000), semantic_source="test")
    assert len(parts) > 1
    assert all(p["bytes"] <= exporter.MAX_PART_BYTES for p in parts)


def test_chunking_is_deterministic(tmp_path):
    records = _records(3000)
    first = exporter.BundleWriter(tmp_path / "a")
    second = exporter.BundleWriter(tmp_path / "b")
    a = first.emit_jsonl_parts("data", records, semantic_source="test")
    b = second.emit_jsonl_parts("data", records, semantic_source="test")
    assert [x["sha256"] for x in a] == [y["sha256"] for y in b]


def test_chunking_emits_one_part_for_an_empty_collection(tmp_path):
    writer = exporter.BundleWriter(tmp_path)
    parts = writer.emit_jsonl_parts("empty", [], semantic_source="test")
    assert len(parts) == 1 and parts[0]["record_count"] == 0
    assert (tmp_path / parts[0]["path"]).read_bytes() == b""


def test_single_record_above_the_ceiling_is_an_error(tmp_path):
    writer = exporter.BundleWriter(tmp_path)
    with pytest.raises(exporter.ReviewBundleError, match="cannot be split"):
        writer.emit_jsonl_parts(
            "huge", [{"blob": "y" * (exporter.MAX_PART_BYTES + 10)}], semantic_source="t"
        )


def test_emit_rejects_an_oversize_single_file(tmp_path):
    writer = exporter.BundleWriter(tmp_path)
    with pytest.raises(exporter.ReviewBundleError, match="rendering ceiling"):
        writer.emit(
            "big.txt",
            b"z" * (exporter.MAX_PART_BYTES + 1),
            record_count=1,
            semantic_source="t",
        )


# --------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------


def test_clopper_pearson_matches_the_locked_interval():
    interval = exporter.clopper_pearson(50, 50, 0.95)
    assert interval["ci_low"] == 0.9288782635358024
    assert interval["ci_high"] == 1.0
    assert interval["method"] == "exact_clopper_pearson"


def test_clopper_pearson_degenerate_endpoints():
    zero = exporter.clopper_pearson(0, 50, 0.95)
    assert zero["ci_low"] == 0.0
    assert zero["ci_high"] == pytest.approx(1.0 - 0.025 ** (1 / 50), abs=1e-15)


def test_clopper_pearson_interior_matches_the_beta_definition():
    # I_x(a, b) evaluated at the returned limits must hit alpha/2 and 1-alpha/2.
    interval = exporter.clopper_pearson(30, 50, 0.95)
    low = exporter.regularized_incomplete_beta(30, 21, interval["ci_low"])
    high = exporter.regularized_incomplete_beta(31, 20, interval["ci_high"])
    assert low == pytest.approx(0.025, abs=1e-10)
    assert high == pytest.approx(0.975, abs=1e-10)


@pytest.mark.parametrize(
    "successes,total,level", [(0, 0, 0.95), (51, 50, 0.95), (5, 50, 1.5)]
)
def test_clopper_pearson_rejects_invalid_inputs(successes, total, level):
    with pytest.raises(exporter.ReviewBundleError):
        exporter.clopper_pearson(successes, total, level)


def test_describe_matches_numpy_linear_quantiles():
    numpy = pytest.importorskip("numpy")
    values = [float(v) for v in (3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5)]
    got = exporter.describe(values)
    array = numpy.asarray(values)
    assert got["n"] == array.size
    assert got["median"] == pytest.approx(float(numpy.median(array)), abs=1e-15)
    for key, q in (("q10", 0.10), ("q25", 0.25), ("q75", 0.75), ("q90", 0.90)):
        assert got[key] == pytest.approx(float(numpy.quantile(array, q)), abs=1e-15)
    assert got["standard_deviation"] == pytest.approx(
        float(numpy.std(array, ddof=1)), rel=1e-12
    )
    assert got["minimum"] == float(numpy.min(array))
    assert got["maximum"] == float(numpy.max(array))


def test_describe_rejects_empty_and_nonfinite():
    with pytest.raises(exporter.ReviewBundleError):
        exporter.describe([])
    with pytest.raises(exporter.ReviewBundleError):
        exporter.describe([1.0, float("nan")])


def test_input_set_sha256_is_order_independent():
    a = [{"path": "b", "sha256": "2"}, {"path": "a", "sha256": "1"}]
    b = [{"path": "a", "sha256": "1"}, {"path": "b", "sha256": "2"}]
    assert exporter.input_set_sha256(a) == exporter.input_set_sha256(b)


def test_input_set_sha256_matches_the_repository_helper():
    sys.path.insert(0, str(REPO_ROOT))
    from experiments.artifact_utils import input_set_sha256 as reference

    inputs = [{"path": f"p{i}", "sha256": f"{i:064x}"} for i in range(25)]
    assert exporter.input_set_sha256(inputs) == reference(inputs)


# --------------------------------------------------------------------------
# committed evidence
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def selection():
    return exporter.load_json_strict(REPO_ROOT / exporter.SELECTION_PATH)


@pytest.fixture(scope="module")
def aggregate():
    return exporter.load_json_strict(REPO_ROOT / exporter.AGGREGATE_PATH)


def test_locked_inputs_hash_to_the_recorded_values():
    observed = exporter.verify_locked_inputs(REPO_ROOT)
    assert observed[str(exporter.SELECTION_PATH)] == exporter.LOCKED_SELECTION_SHA256
    assert observed[str(exporter.AGGREGATE_PATH)] == exporter.LOCKED_AGGREGATE_SHA256
    assert observed[str(exporter.PDF_PATH)] == exporter.LOCKED_PDF_SHA256


def test_aggregate_input_set_digest_recomputes(aggregate):
    assert (
        exporter.input_set_sha256(aggregate["inputs"])
        == exporter.LOCKED_AGGREGATE_INPUT_SET_SHA256
    )


def test_selection_winner_replays_exactly(selection):
    means = {}
    for candidate in selection["candidates"]:
        values = [
            float(r["mean_all_action_prediction_mse"]) for r in candidate["runs"]
        ]
        means[candidate["candidate_id"]] = math.fsum(values) / len(values)
        assert means[candidate["candidate_id"]] == float(
            candidate["aggregate_mean_all_action_prediction_mse"]
        )
    eligible = [c for c in selection["candidates"] if c["eligible"]]
    winner = min(
        eligible,
        key=lambda c: (
            means[c["candidate_id"]],
            int(c["steps_per_round"]),
            float(c["learning_rate"]),
        ),
    )
    assert winner["candidate_id"] == "candidate-008"
    assert float(winner["learning_rate"]) == 0.0003
    assert int(winner["steps_per_round"]) == 20
    assert means["candidate-008"] == 0.00666914978044266


def test_tie_rule_prefers_fewer_steps_then_smaller_learning_rate():
    # Two candidates with an identical score: the rule must be deterministic.
    means = {"a": 1.0, "b": 1.0, "c": 1.0}
    candidates = [
        {"candidate_id": "a", "steps_per_round": 20, "learning_rate": 1e-4},
        {"candidate_id": "b", "steps_per_round": 5, "learning_rate": 3e-4},
        {"candidate_id": "c", "steps_per_round": 5, "learning_rate": 1e-4},
    ]
    winner = min(
        candidates,
        key=lambda c: (
            means[c["candidate_id"]],
            int(c["steps_per_round"]),
            float(c["learning_rate"]),
        ),
    )
    assert winner["candidate_id"] == "c"


def test_selection_grid_and_cells_are_exact(selection):
    assert selection["candidate_count"] == exporter.EXPECTED_CANDIDATE_COUNT
    assert len(selection["candidates"]) == exporter.EXPECTED_CANDIDATE_COUNT
    for candidate in selection["candidates"]:
        assert len(candidate["runs"]) == exporter.EXPECTED_CANDIDATE_CELLS
        cells = {
            (r["seed"], r["horizon"], r["target_D"]) for r in candidate["runs"]
        }
        assert len(cells) == exporter.EXPECTED_CANDIDATE_CELLS


def test_tuning_and_evaluation_seeds_are_disjoint(selection):
    assert set(selection["tuning_seeds"]).isdisjoint(selection["evaluation_seeds"])
    assert tuple(selection["tuning_seeds"]) == exporter.EXPECTED_TUNING_SEEDS
    assert tuple(selection["evaluation_seeds"]) == exporter.EXPECTED_EVALUATION_SEEDS


def test_duplicate_cell_detection_rejects_a_repeated_key():
    rows = [{"horizon": 250, "target_D": 0.25, "method": None}] * 2
    with pytest.raises(exporter.ReviewBundleError, match="duplicate cell"):
        exporter._require_unique_cells("validity", rows)


def test_path_views_filter_checkpoints_and_group_run_maxima():
    aggregate = {
        "path_points": [
            {"horizon": 250, "target_D": 0.25, "seed": 1, "round": 1,
             "D_Q": 0.0, "d_Th": 0.0, "D_path_quad": None},
            {"horizon": 250, "target_D": 0.25, "seed": 1, "round": 2,
             "D_Q": 2.0, "d_Th": 1.0, "D_path_quad": 0.5},
            {"horizon": 250, "target_D": 0.25, "seed": 1, "round": 3,
             "D_Q": 4.0, "d_Th": 2.0, "D_path_quad": None},
        ],
        "certificate_tightness": [
            {
                "horizon": 250,
                "target_D": 0.25,
                "D_Q_over_d_Th": {"n": 2, "median": 2.0},
                "D_Q_over_D_path_quad": {"n": 1, "median": 4.0},
                "D_path_quad_over_d_Th": {"n": 1, "median": 0.5},
                "d_Th_at_or_below_ratio_tolerance_count": 1,
                "D_path_quad_at_or_below_ratio_tolerance_count": 0,
                "d_Th_at_or_below_tolerance_with_path_count": 0,
            }
        ],
    }
    maxima, checkpoints, summaries = exporter._path_views(aggregate)

    # only the round with a present D_path_quad becomes a checkpoint
    assert [c["round"] for c in checkpoints] == [2]
    assert checkpoints[0]["D_Q_over_d_Th"] == 2.0
    assert checkpoints[0]["D_Q_over_D_path_quad"] == 4.0

    assert len(maxima) == 1
    group = maxima[0]
    assert group["round_count"] == 3
    assert group["quadrature_checkpoint_count"] == 1
    assert group["max_D_Q"] == 4.0
    assert group["max_d_Th"] == 2.0
    assert group["max_D_path_quad"] == 0.5
    # the round-one zero denominator is counted, never silently dropped
    assert group["d_Th_at_or_below_tolerance_count"] == 1

    assert len(summaries) == 1
    entry = summaries[0]
    assert entry["D_Q_over_d_Th"]["recomputed_n"] == 2
    assert entry["D_Q_over_d_Th"]["n_matches"] is True
    assert entry["d_Th_at_or_below_ratio_tolerance_count"]["matches"] is True


def test_zero_denominator_rounds_are_excluded_from_ratios():
    aggregate = {
        "path_points": [
            {"horizon": 250, "target_D": 0.25, "seed": 1, "round": 1,
             "D_Q": 7.0, "d_Th": 0.0, "D_path_quad": 0.0},
        ],
        "certificate_tightness": [
            {
                "horizon": 250,
                "target_D": 0.25,
                "D_Q_over_d_Th": None,
                "D_Q_over_D_path_quad": None,
                "D_path_quad_over_d_Th": None,
                "d_Th_at_or_below_ratio_tolerance_count": 1,
                "D_path_quad_at_or_below_ratio_tolerance_count": 1,
                "d_Th_at_or_below_tolerance_with_path_count": 1,
            }
        ],
    }
    _, checkpoints, summaries = exporter._path_views(aggregate)
    assert checkpoints and "D_Q_over_d_Th" not in checkpoints[0]
    entry = summaries[0]
    assert entry["D_Q_over_d_Th"]["recomputed_n"] == 0
    assert entry["d_Th_at_or_below_ratio_tolerance_count"]["recomputed"] == 1
    assert entry["D_path_quad_at_or_below_ratio_tolerance_count"]["recomputed"] == 1
    assert entry["d_Th_at_or_below_tolerance_with_path_count"]["recomputed"] == 1


def test_committed_path_summaries_agree_with_the_published_tightness(aggregate):
    _, _, summaries = exporter._path_views(aggregate)
    assert len(summaries) == 12
    for entry in summaries:
        for field in (
            "D_Q_over_d_Th",
            "D_Q_over_D_path_quad",
            "D_path_quad_over_d_Th",
        ):
            if entry[field]["recomputed_median"] is not None:
                assert entry[field]["n_matches"] is True
                assert entry[field]["median_absolute_difference"] == 0.0
        for field in (
            "d_Th_at_or_below_ratio_tolerance_count",
            "D_path_quad_at_or_below_ratio_tolerance_count",
            "d_Th_at_or_below_tolerance_with_path_count",
        ):
            assert entry[field]["matches"] is True


# --------------------------------------------------------------------------
# bundle regeneration
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    target = tmp_path_factory.mktemp("bundle") / "out"
    manifest = exporter.export_bundle(REPO_ROOT, target)
    return target, manifest


def test_export_is_byte_identical_on_a_second_run(exported, tmp_path):
    first, _ = exported
    second = tmp_path / "again"
    exporter.export_bundle(REPO_ROOT, second)
    a = {p.relative_to(first): p.read_bytes() for p in first.rglob("*") if p.is_file()}
    b = {p.relative_to(second): p.read_bytes() for p in second.rglob("*") if p.is_file()}
    assert a.keys() == b.keys()
    assert a == b


def test_export_is_idempotent_when_rerun_in_place(exported):
    target, manifest = exported
    before = {p.relative_to(target): p.read_bytes() for p in target.rglob("*") if p.is_file()}
    again = exporter.export_bundle(REPO_ROOT, target)
    after = {p.relative_to(target): p.read_bytes() for p in target.rglob("*") if p.is_file()}
    assert before == after
    assert again["bundle_inventory_digest"] == manifest["bundle_inventory_digest"]


def test_every_output_is_within_the_rendering_ceiling(exported):
    _, manifest = exported
    assert manifest["max_output_bytes"] <= exporter.MAX_PART_BYTES
    for entry in manifest["outputs"]:
        assert entry["bytes"] <= exporter.MAX_PART_BYTES


def test_manifest_inventory_matches_disk(exported):
    target, manifest = exported
    for entry in manifest["outputs"]:
        path = target / entry["path"]
        payload = path.read_bytes()
        assert hashlib.sha256(payload).hexdigest() == entry["sha256"]
        assert len(payload) == entry["bytes"]


def test_manifest_records_the_structural_limitations(exported):
    _, manifest = exported
    limits = manifest["limitations"]
    assert limits["raw_input_bytes_verified"] is False
    assert limits["raw_results_tree_committed"] is False
    assert limits["structural_pass_is_not_full_provenance"] is True
    assert limits["float64_diagnostics_are_verified_certificates"] is False
    assert limits["paired_bootstrap_recomputable_from_committed_aggregate"] is False
    assert "experiments/make_transport_instantiation_artifacts.py" in (
        limits["known_study_source_divergences"]
    )


def test_bundle_inventory_digest_recomputes(exported):
    _, manifest = exported
    digest = hashlib.sha256(
        exporter.canonical_json(
            [
                {
                    "path": i["path"],
                    "sha256": i["sha256"],
                    "bytes": i["bytes"],
                    "record_count": i["record_count"],
                }
                for i in sorted(manifest["outputs"], key=lambda x: x["path"])
            ]
        ).encode("ascii")
    ).hexdigest()
    assert digest == manifest["bundle_inventory_digest"]


def test_no_record_is_lost_between_source_and_bundle(exported, aggregate, selection):
    target, manifest = exported
    counts = {entry["path"]: entry["record_count"] for entry in manifest["outputs"]}

    def total(prefix):
        return sum(v for k, v in counts.items() if k.startswith(prefix))

    assert total("aggregate/regret_curves") == len(aggregate["regret_curves"])
    assert total("aggregate/bound_decomposition") == len(aggregate["bound_decomposition"])
    assert total("aggregate/input_inventory") == len(aggregate["inputs"])
    assert total("selection/inputs") == len(selection["inputs"])
    assert counts["aggregate/validity.jsonl"] == len(aggregate["validity"])
    assert counts["selection/candidates.jsonl"] == len(selection["candidates"])
    assert total("selection/runs") == sum(
        len(c["runs"]) for c in selection["candidates"]
    )


def test_committed_bundle_matches_a_fresh_export(exported):
    fresh, _ = exported
    committed = REPO_ROOT / "review/transport_instantiation"
    if not committed.is_dir():
        pytest.skip("review bundle has not been generated in this checkout")
    for path in fresh.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(fresh)
        assert (committed / relative).read_bytes() == path.read_bytes(), relative


# --------------------------------------------------------------------------
# verifier
# --------------------------------------------------------------------------


def test_status_labels_keep_structural_pass_distinct():
    structural = verifier.STATUS_LABELS[verifier.STATUS_STRUCTURAL]
    assert verifier.STATUS_STRUCTURAL != verifier.STATUS_PASS
    assert structural.startswith("STRUCTURAL PASS")
    # the label must state the limitation, not read as a plain pass
    assert "raw bytes absent" in structural
    assert verifier.STATUS_LABELS[verifier.STATUS_PASS].startswith("PASS")
    assert "recomputed" in verifier.STATUS_LABELS[verifier.STATUS_RECOMPUTED]
    assert "requires raw data" in verifier.STATUS_LABELS[verifier.STATUS_NOT_EXECUTED]


def test_structural_status_is_never_emitted_as_a_plain_pass():
    report = verifier.Report()
    report.expect("s", "structural thing", True, status=verifier.STATUS_STRUCTURAL)
    assert report.checks[0]["status"] == verifier.STATUS_STRUCTURAL
    assert report.checks[0]["status"] != verifier.STATUS_PASS
    assert not report.failures


def test_report_marks_a_failed_expectation():
    report = verifier.Report()
    report.expect("s", "true", True, status=verifier.STATUS_PASS)
    report.expect("s", "false", False, status=verifier.STATUS_PASS)
    assert len(report.failures) == 1
    assert report.counts()[verifier.STATUS_FAIL] == 1


def test_prose_normalization_ignores_only_whitespace():
    assert verifier._normalize_prose("a\n  b\tc") == "a b c"
    assert verifier._normalize_prose("2400") != verifier._normalize_prose("2 400")


def test_detached_verifier_passes_without_the_raw_tree():
    report = verifier.run(
        REPO_ROOT, REPO_ROOT / "review/transport_instantiation", skip_bundle=True
    )
    assert report.failures == [], [c["check"] for c in report.failures]
    counts = report.counts()
    assert counts.get(verifier.STATUS_STRUCTURAL, 0) >= 2
    assert counts.get(verifier.STATUS_NOT_EXECUTED, 0) >= 3
    assert counts.get(verifier.STATUS_RECOMPUTED, 0) >= 10


def test_verifier_reports_absent_raw_inputs_as_not_executed():
    report = verifier.run(
        REPO_ROOT, REPO_ROOT / "review/transport_instantiation", skip_bundle=True
    )
    not_executed = {
        c["check"] for c in report.checks if c["status"] == verifier.STATUS_NOT_EXECUTED
    }
    assert "tuning input file bytes" in not_executed
    assert "evaluation input file bytes" in not_executed
    assert "full provenance validation" in not_executed
    assert "deterministic paired bootstrap intervals" in not_executed


def test_verifier_pins_the_known_study_source_divergence():
    report = verifier.run(
        REPO_ROOT, REPO_ROOT / "review/transport_instantiation", skip_bundle=True
    )
    diverged = [
        c for c in report.checks if c["status"] == verifier.STATUS_KNOWN_DIVERGENCE
    ]
    assert len(diverged) == len(exporter.KNOWN_STUDY_SOURCE_DIVERGENCES)
    assert "make_transport_instantiation_artifacts.py" in diverged[0]["check"]
    # the pin must carry both hashes and the causing commit
    assert exporter.IMPLEMENTATION_COMMIT in diverged[0]["detail"]


def test_pdf_sidecar_validates_against_the_locked_pdf():
    sidecar = REPO_ROOT / "paper/main.pdf.sha256"
    assert sidecar.is_file()
    fields = sidecar.read_text(encoding="ascii").strip().split()
    assert len(fields) == 2
    assert fields[1] == "main.pdf"
    assert fields[0] == exporter.LOCKED_PDF_SHA256
    assert fields[0] == exporter.sha256_file(REPO_ROOT / exporter.PDF_PATH)


def test_pdf_page_count_uses_object_stream_inflation():
    assert exporter.pdf_page_count(REPO_ROOT / exporter.PDF_PATH) == 63


def test_generated_artifacts_match_the_aggregate():
    pytest.importorskip("numpy")
    pytest.importorskip("scipy")
    report = verifier.Report()
    verifier.check_generated_artifacts(report, REPO_ROOT)
    statuses = {c["status"] for c in report.checks}
    assert verifier.STATUS_FAIL not in statuses
    assert verifier.STATUS_NOT_EXECUTED not in statuses
    recomputed = [
        c for c in report.checks if c["status"] == verifier.STATUS_RECOMPUTED
    ]
    assert len(recomputed) == len(exporter.GENERATED_ARTIFACT_PATHS)


def test_locked_artifact_hash_table_covers_every_locked_file():
    for relative, expected in verifier.LOCKED_ARTIFACT_HASHES.items():
        assert exporter.sha256_file(REPO_ROOT / relative) == expected
