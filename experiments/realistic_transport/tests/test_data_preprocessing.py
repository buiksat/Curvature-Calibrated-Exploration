from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest
from experiments.realistic_transport.data import (
    canonical_array_digest,
    DataPreparationError,
    load_prepared_dataset,
    prepare_loaded_dataset,
)
from experiments.realistic_transport.preprocessing import (
    deterministic_split,
    fit_preprocessing,
    PreprocessingError,
)


def _source_arrays() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(40101)
    features = rng.normal(size=(503, 24))
    features[:, -1] = 7.0
    labels = np.asarray([10, 20, 30, 40, 50, 60, 70] * 72)[:503]
    return features, labels


def test_prepared_artifact_is_byte_deterministic_and_portable(tmp_path) -> None:
    features, labels = _source_arrays()
    first = tmp_path / "first.npz"
    second = tmp_path / "second.npz"
    first_manifest = prepare_loaded_dataset(
        features,
        labels,
        dataset_name="fixture",
        destination=first,
        loader_metadata={"loader": "unit-test"},
        overwrite=False,
    )
    second_manifest = prepare_loaded_dataset(
        features,
        labels,
        dataset_name="fixture",
        destination=second,
        loader_metadata={"loader": "unit-test"},
        overwrite=False,
    )
    assert first.read_bytes() == second.read_bytes()
    assert first_manifest["artifact_sha256"] == second_manifest["artifact_sha256"]
    assert (
        first_manifest["array_content_sha256"]
        == second_manifest["array_content_sha256"]
    )
    manifest_text = first.with_suffix(".npz.manifest.json").read_text()
    assert str(tmp_path) not in manifest_text

    prepared = load_prepared_dataset(
        first,
        required_digest=first_manifest["array_content_sha256"],
    )
    assert prepared.features.dtype == np.float64
    assert prepared.labels.dtype == np.int64
    assert prepared.action_count == 7
    np.testing.assert_array_equal(np.unique(prepared.labels), np.arange(7))
    assert not prepared.features.flags.writeable
    assert not prepared.labels.flags.writeable


def test_prepared_artifact_rejects_digest_mismatch_and_tampering(tmp_path) -> None:
    features, labels = _source_arrays()
    artifact = tmp_path / "data.npz"
    manifest = prepare_loaded_dataset(
        features,
        labels,
        dataset_name="fixture",
        destination=artifact,
    )
    with pytest.raises(DataPreparationError, match="required_digest"):
        load_prepared_dataset(artifact, required_digest="0" * 64)

    content = bytearray(artifact.read_bytes())
    content[-1] ^= 1
    artifact.write_bytes(content)
    with pytest.raises(DataPreparationError, match="SHA-256"):
        load_prepared_dataset(
            artifact,
            required_digest=manifest["array_content_sha256"],
        )


def test_manifest_records_label_mapping_without_absolute_paths(tmp_path) -> None:
    features, labels = _source_arrays()
    artifact = tmp_path / "mapped.npz"
    prepare_loaded_dataset(
        features,
        labels,
        dataset_name="fixture",
        destination=artifact,
        cache_inventory=[
            {"relative_path": "covertype/covtype.data.gz", "sha256": "a" * 64}
        ],
    )
    manifest = json.loads(
        artifact.with_suffix(".npz.manifest.json").read_text(encoding="ascii")
    )
    assert manifest["original_classes"] == [10, 20, 30, 40, 50, 60, 70]
    assert manifest["source_cache_files"][0]["relative_path"] == (
        "covertype/covtype.data.gz"
    )
    assert not manifest["source_cache_files"][0]["relative_path"].startswith("/")


def test_sha_split_is_deterministic_disjoint_complete_and_near_target() -> None:
    digest = canonical_array_digest({"fixture": np.arange(1000, dtype=np.int64)})
    first = deterministic_split(10_000, digest)
    second = deterministic_split(10_000, digest)
    np.testing.assert_array_equal(first.development, second.development)
    np.testing.assert_array_equal(first.tuning, second.tuning)
    np.testing.assert_array_equal(first.evaluation, second.evaluation)
    expected_development = []
    prefix = f"realistic-transport-covtype-v1\0{digest}\0".encode("ascii")
    for row_index in range(10_000):
        bucket = (
            int.from_bytes(
                hashlib.sha256(prefix + str(row_index).encode("ascii")).digest()[:8],
                "big",
            )
            % 100
        )
        if bucket < 20:
            expected_development.append(row_index)
    np.testing.assert_array_equal(first.development, expected_development)
    combined = np.concatenate((first.development, first.tuning, first.evaluation))
    np.testing.assert_array_equal(np.sort(combined), np.arange(10_000))
    assert np.unique(combined).size == combined.size
    assert len(first.development) / 10_000 == pytest.approx(0.2, abs=0.015)
    assert len(first.tuning) / 10_000 == pytest.approx(0.2, abs=0.015)
    assert len(first.evaluation) / 10_000 == pytest.approx(0.6, abs=0.02)


def test_preprocessing_uses_only_development_rows_and_bounds_contexts() -> None:
    features, _ = _source_arrays()
    digest = canonical_array_digest({"features": features})
    split = deterministic_split(features.shape[0], digest)
    first = fit_preprocessing(
        features,
        split.development,
        prepared_data_digest=digest,
        rank=16,
    )
    modified = features.copy()
    modified[split.tuning] = 1e6
    modified[split.evaluation] = -1e6
    second = fit_preprocessing(
        modified,
        split.development,
        prepared_data_digest=digest,
        rank=16,
    )
    np.testing.assert_array_equal(first.mean, second.mean)
    np.testing.assert_array_equal(first.scale, second.scale)
    np.testing.assert_array_equal(first.projection, second.projection)
    np.testing.assert_array_equal(first.eigenvalues, second.eigenvalues)
    assert first.zero_variance[-1]
    assert first.scale[-1] == 1.0

    for component_index, component in enumerate(first.projection.T):
        pivot = int(np.argmax(np.abs(component)))
        assert first.sign_anchors[component_index] == pivot
        assert component[pivot] > 0.0
    transformed = first.transform(features)
    assert transformed.shape == (features.shape[0], 16)
    assert np.max(np.linalg.norm(transformed, axis=1)) <= 1.0 + 1e-14
    assert first.summary(transformed)["array_content_sha256"] == (
        canonical_array_digest({"contexts": transformed})
    )


def test_preprocessing_rejects_a_degenerate_pca_cutoff() -> None:
    features = np.asarray(
        [[1.0, 0.0], [-1.0, 0.0], [0.0, 1.0], [0.0, -1.0]],
        dtype=np.float64,
    )
    digest = canonical_array_digest({"features": features})
    with pytest.raises(PreprocessingError, match="degenerate eigenspace"):
        fit_preprocessing(
            features,
            np.arange(4),
            prepared_data_digest=digest,
            rank=1,
        )
