"""Pinned, metadata-only anonymization of the compact follow-up evidence.

Original experiments and raw logs are never modified. External-input inventories
retain hashes of the original, unshipped bytes under an explicitly external
namespace. This module does not turn their historical signatures into signatures
of an anonymous raw archive. Scientific observations and settings are immutable.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import tempfile
from typing import Any

DECLARATION_NAME = "FOLLOWUP_ANONYMIZATION.json"
REPLACEMENT_TOKEN = "withheld-for-double-blind-review"
FULL = "review/transport_review_followup/full-cce-full-local/"
INDEPENDENT = "review/post_full_fable/independent/"
RELATIVE = "review/transport_relative_diagnostics/full/"
EXTERNAL_ROOT = "original-external/followup"
INPUT_PATHS = tuple(sorted(
    [FULL + name for name in (
        "README.md", "aggregate_compact.json", "development_summaries.jsonl",
        "drift_and_reference_diagnostics.json", "execution_config.json",
        "export_manifest.json", "raw_input_inventory.jsonl", "round_drift_summaries.jsonl",
        "run_manifest.json", "seed_summaries.jsonl", "selection.json",
        "source_config.json", "terminal_bound_decomposition.json", "tuning_summaries.jsonl")]
    + [INDEPENDENT + name for name in ("analysis.json", "input_inventory.jsonl")]
    + [RELATIVE + name for name in (
        "analysis.json", "input_inventory.jsonl", "per_seed.jsonl", "ARTIFACTS.sha256")]
))

# Independent constants, never learned from the reviewer-editable declaration.
# PINNED_CONTRACT_START
FOLLOWUP_CONTRACT: dict[str, dict[str, Any]] = {'review/post_full_fable/independent/analysis.json': {'original_bytes': 139195,
                                                      'original_sha256': '914013bf6436e82a50865d5ce3570b4195e7cdc2e4f25b436eb5b28a9b99ece3',
                                                      'packaged_bytes': 139788,
                                                      'packaged_sha256': '7bcad2548bf5dc786c2bd30f2a3144a6f10e9e7a2ef1fa1256232793ce904b78'},
 'review/post_full_fable/independent/input_inventory.jsonl': {'original_bytes': 698492,
                                                              'original_sha256': 'cac69a473240fa30baa822da22fa2e6a9c64c8316fdd93f0bb1a476062b0b2da',
                                                              'packaged_bytes': 701500,
                                                              'packaged_sha256': '16dabd5b0ff59697f3776e77181e20535f1ebc973802e8286fd603bc38f5aee8'},
 'review/transport_relative_diagnostics/full/ARTIFACTS.sha256': {'original_bytes': 249,
                                                                 'original_sha256': '4c30d2911aa9bc4d5f9b2a71086b54237134314eb810d58854200145327f96bf',
                                                                 'packaged_bytes': 249,
                                                                 'packaged_sha256': 'a63fb3b7c1802897ec4ec26be1ec0327b872431155a4d268e059f2bddb462629'},
 'review/transport_relative_diagnostics/full/analysis.json': {'original_bytes': 198217,
                                                              'original_sha256': 'fd67cdc031c02876ed1e18ea0444a35348b4cb80bdd261b3fd3d75e6e920b29e',
                                                              'packaged_bytes': 198210,
                                                              'packaged_sha256': 'edb91ee36c4abd0005894e33bc94cf4e0b65bb81794fc819a18145871f85a69a'},
 'review/transport_relative_diagnostics/full/input_inventory.jsonl': {'original_bytes': 700464,
                                                                      'original_sha256': 'c905bdcd58aa9c827a141ac024c49cccdba1d97bf5ad8908889b15d3f471190a',
                                                                      'packaged_bytes': 703473,
                                                                      'packaged_sha256': '121ec1125f9b680acf37c08fba4639d548f9eb3eef9435f7feb3efd22ec58f90'},
 'review/transport_relative_diagnostics/full/per_seed.jsonl': {'original_bytes': 4913131,
                                                               'original_sha256': '9d7939364bfd7737df5daaf80d43c0673828505466ede181fe31f42fe2f98bea',
                                                               'packaged_bytes': 4913131,
                                                               'packaged_sha256': '9d7939364bfd7737df5daaf80d43c0673828505466ede181fe31f42fe2f98bea'},
 'review/transport_review_followup/full-cce-full-local/README.md': {'original_bytes': 801,
                                                                    'original_sha256': '432bd88c7f715693e1a94edba165dcf134aa030c8fbbdcba92e0f8674c18c950',
                                                                    'packaged_bytes': 1092,
                                                                    'packaged_sha256': 'b616530a8ea3c3b16f13de6a73436ff408c3d66d7dc81e071acd3a60b83b214f'},
 'review/transport_review_followup/full-cce-full-local/aggregate_compact.json': {'original_bytes': 64458,
                                                                                 'original_sha256': 'f28acc2d601d7524f5b30a55f396c5408a7f37a26fd36bde49a3477024bc6658',
                                                                                 'packaged_bytes': 64477,
                                                                                 'packaged_sha256': '93c7e41be403e4f9849ee395981e9b6e8c501488a63da0cbcb72073a84049085'},
 'review/transport_review_followup/full-cce-full-local/development_summaries.jsonl': {'original_bytes': 58225,
                                                                                      'original_sha256': '02832e6a618cd018c95ae92d639db7f3ee6d861f3f7c037260b0869366f43b68',
                                                                                      'packaged_bytes': 58225,
                                                                                      'packaged_sha256': '02832e6a618cd018c95ae92d639db7f3ee6d861f3f7c037260b0869366f43b68'},
 'review/transport_review_followup/full-cce-full-local/drift_and_reference_diagnostics.json': {'original_bytes': 11290,
                                                                                               'original_sha256': 'fb3293daacba3511ca5f3269d67e9aa0f0aca2708ad9876661ca062e197a59a4',
                                                                                               'packaged_bytes': 11290,
                                                                                               'packaged_sha256': 'fb3293daacba3511ca5f3269d67e9aa0f0aca2708ad9876661ca062e197a59a4'},
 'review/transport_review_followup/full-cce-full-local/execution_config.json': {'original_bytes': 11306,
                                                                                'original_sha256': 'be6e253b68970de29d2b18ca27413d3551f00d0dbca75eb168379ab3d9b0cae3',
                                                                                'packaged_bytes': 11306,
                                                                                'packaged_sha256': 'be6e253b68970de29d2b18ca27413d3551f00d0dbca75eb168379ab3d9b0cae3'},
 'review/transport_review_followup/full-cce-full-local/export_manifest.json': {'original_bytes': 2376,
                                                                               'original_sha256': 'adbf7ab8d401fa057999d4f98582a52f8ca5af71362efd05632345be4984eaca',
                                                                               'packaged_bytes': 2377,
                                                                               'packaged_sha256': '32cdd8607a1410a92ab526c301ef43aa92cb03b385bac537b011b0ea6b7ceacc'},
 'review/transport_review_followup/full-cce-full-local/raw_input_inventory.jsonl': {'original_bytes': 676673,
                                                                                    'original_sha256': '88320d1615f32764e21d6f32ae87bb127ff11032d2720fd101c9b092a8b1d2c4',
                                                                                    'packaged_bytes': 669707,
                                                                                    'packaged_input_set_sha256': '37165a44bcf6b8146ecf001fd8f9456ffda5bde6124872462173f52390d2abea',
                                                                                    'packaged_sha256': '983a09f252932777d27c9e0c448881009fcca0da5c5a2255126aa4029d528ad5'},
 'review/transport_review_followup/full-cce-full-local/round_drift_summaries.jsonl': {'original_bytes': 119880,
                                                                                      'original_sha256': '9b6bda78c88074e46e1ff3c4253b9623bb95f467f068b6339bee9d83e4e4fce1',
                                                                                      'packaged_bytes': 119880,
                                                                                      'packaged_sha256': '9b6bda78c88074e46e1ff3c4253b9623bb95f467f068b6339bee9d83e4e4fce1'},
 'review/transport_review_followup/full-cce-full-local/run_manifest.json': {'original_bytes': 6299,
                                                                            'original_sha256': '04bfe76614ec140b110da8149a42f15a3c3fbd2b38c76c67272f23e7ca7785af',
                                                                            'packaged_bytes': 6293,
                                                                            'packaged_sha256': '80c91ee53a41f6acaeb29cf29ef0bb92213f53f98b08ce57cdc4261a365d959a'},
 'review/transport_review_followup/full-cce-full-local/seed_summaries.jsonl': {'original_bytes': 1483678,
                                                                               'original_sha256': 'e1c4935f879df7418a2a115692113d90e50d6e50e3819cbe3ad29ce40a9afc60',
                                                                               'packaged_bytes': 1411678,
                                                                               'packaged_sha256': 'cb3b1c5b6a6cbdbb989859a579e7b7281d6d20a644a460b28ac3751e8e23ef81'},
 'review/transport_review_followup/full-cce-full-local/selection.json': {'original_bytes': 335042,
                                                                         'original_sha256': '4ec58fcac633b5ab28eae302b4a9695b411b378023836436a1ecfffbec942952',
                                                                         'packaged_bytes': 336385,
                                                                         'packaged_sha256': 'ebd57990b5a5fdb2faf6e0df3c51089c5d2c96b2cb55ab7faed9f5386207931c'},
 'review/transport_review_followup/full-cce-full-local/source_config.json': {'original_bytes': 12971,
                                                                             'original_sha256': 'caa289be9f6f95b4bf808af29238eccee4cebbbc4b2a6ac0f7f2a69edd46566d',
                                                                             'packaged_bytes': 12971,
                                                                             'packaged_sha256': 'caa289be9f6f95b4bf808af29238eccee4cebbbc4b2a6ac0f7f2a69edd46566d'},
 'review/transport_review_followup/full-cce-full-local/terminal_bound_decomposition.json': {'original_bytes': 1186,
                                                                                            'original_sha256': 'b1a6e9c5d8cfe70d3c3e3bb7cbd818502c21bb3b2f276426702cb016db323ecc',
                                                                                            'packaged_bytes': 1186,
                                                                                            'packaged_sha256': 'b1a6e9c5d8cfe70d3c3e3bb7cbd818502c21bb3b2f276426702cb016db323ecc'},
 'review/transport_review_followup/full-cce-full-local/tuning_summaries.jsonl': {'original_bytes': 225679,
                                                                                 'original_sha256': 'dd17ab420a4b394864fbbd4d25efc66177e505e0dfc2a87a1d4512bf59cfaf44',
                                                                                 'packaged_bytes': 225679,
                                                                                 'packaged_sha256': 'dd17ab420a4b394864fbbd4d25efc66177e505e0dfc2a87a1d4512bf59cfaf44'}}
# PINNED_CONTRACT_END

# PINNED_ARTIFACTS_START
ARTIFACT_PINS: dict[str, dict[str, Any]] = {'paper/figures/transport_explanatory_bounds.csv': {'bytes': 787,
                                                    'sha256': '523f691b7075a0544e3863ab63ae0795cf9fc81efd66e665e978a36cd47c74e1'},
 'paper/figures/transport_explanatory_bounds.tex': {'bytes': 2297,
                                                    'sha256': 'bee87dd7c6c536c1ee44249901d329867a5f7bbd5a25da497620bff1f86ad324'},
 'paper/figures/transport_explanatory_outcomes.csv': {'bytes': 841,
                                                      'sha256': '0779da05a7a0945531a1bff8c34bb4f88dcdf3829eebfffe79b3ae360307a7fe'},
 'paper/figures/transport_explanatory_outcomes.tex': {'bytes': 8626,
                                                      'sha256': 'a7c5d1303583be47e65b2140410f4c0a1bc7a604ce1b0d549352adc6b8bdb339'},
 'paper/figures/transport_explanatory_paired.csv': {'bytes': 1124,
                                                    'sha256': 'c5e92e0c7158419edfacc2b4b51576aa9c7197ba87958261d37beec44a032266'},
 'paper/figures/transport_explanatory_provenance.json': {'bytes': 3014,
                                                         'sha256': '7e8294965356fa113e7c8c67f8e0ceda6c21c85dcc44b14d5ef79489032067ea'},
 'paper/tables/transport_followup_drift_bounds.tex': {'bytes': 1884,
                                                      'sha256': '6130e0e66e34c6117f5e6d4bc0d1b4a574394a1b00dbf4b363b50062530bac2c'},
 'paper/tables/transport_followup_mechanism_variation.tex': {'bytes': 2402,
                                                             'sha256': '2725e1b7940683b696b5f93c90a1abbf7ba4c001915ce13cf43cf9dfadd8c851'},
 'paper/tables/transport_followup_outcomes.tex': {'bytes': 2219,
                                                  'sha256': 'cb87dee8d0d4ceb3bf9c64f7b9c86643cfa69d6176493428bd92177c06cfc288'},
 'paper/tables/transport_followup_provenance.json': {'bytes': 2612,
                                                     'sha256': 'd6c5a5a5ad0beebaf314a5be56ffaaa0d6876afec8167ec10ddd6205b2052327'},
 'paper/tables/transport_followup_relative_audit.tex': {'bytes': 2035,
                                                        'sha256': 'b7ff2a9c5d3fec423bf6811f0f444ea035c6115b7f91c36d6faca11b7a6626aa'},
 'paper/tables/transport_followup_same_history.tex': {'bytes': 2471,
                                                      'sha256': 'e3cbe9e68cf611f0ccf296fcee0e5c7adc34ff50b594933710be97e47d33105e'}}
# PINNED_ARTIFACTS_END

# Analytical illustrations are reviewed source material, not empirical outputs
# reconstructed from the experiment. Keep their provenance class explicit.
SCHEMATIC_PINS: dict[str, dict[str, Any]] = {'paper/figures/transport_conceptual_geometry.tex': {'bytes': 4104,
                                                     'sha256': '12f0039ce9c0c20f8d78aa46193b606042cac7015094837b6f3581d8b110fb5b'},
 'paper/figures/transport_conceptual_interfaces.tex': {'bytes': 2650,
                                                       'sha256': '6b1976da5525e1aa1aad47bb0775c37e4de0734617eacd17fefb0386b817e3e4'}}

README = """# Anonymous compact follow-up evidence

This export contains the complete evaluation, tuning and development summaries,
the selected optimizer, exact configurations and derived statistics. Terminal
paired intervals can be independently recomputed with the supplied export
verifier. The separate analysis outputs describe exploratory fixed-history
diagnostics; their input inventories are retained original provenance.

Raw trajectories are not included. The original-external/followup namespace is
a label for original unshipped files, not a path to packaged data. Inventory
hashes describe those original bytes. Roundwise audits and optimizer replay
require the separately retained raw archive and its recorded runtime.

FOLLOWUP_ANONYMIZATION.json at the package root describes the exact metadata
transformations and original/packaged content digests. Original run signatures,
source inventories, timestamps and runtime records remain historical provenance;
they are not signatures of an anonymous raw archive. Scientific values are
unchanged. The export manifest binds the packaged files.
""".encode("utf-8")


class ContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _json(data: bytes) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(
                          ContractError("Nonfinite JSON constant")))


def _input_digest(rows: list[dict]) -> str:
    normalized = sorted(({"path": row["path"], "sha256": row["sha256"]}
                         for row in rows), key=lambda row: (row["path"], row["sha256"]))
    return _digest(_canonical(normalized))


def _external_path(value: str) -> str:
    """Rewrite only recognized typed original-input paths, never arbitrary text."""
    _require(type(value) is str and PurePosixPath(value).is_absolute(),
             "Expected an absolute original-input path")
    parts = PurePosixPath(value).parts
    _require(".." not in parts, "Traversal in original-input path")
    if "raw" in parts:
        index = parts.index("raw")
        _require(len(parts) > index + 2 and parts[index + 1] in
                 {"evaluation", "tuning", "development"}, "Unknown raw input scope")
        return EXTERNAL_ROOT + "/" + "/".join(parts[index:])
    if parts[-2:] == ("experiments", "transport_instantiation.py"):
        return "original-external/repository/experiments/transport_instantiation.py"
    _require(parts[-1] in {"run.json", "execution_config.json", "source_config.json",
                          "selection.json", "selection.json.provenance.json"},
             "Unknown supporting original-input path")
    return EXTERNAL_ROOT + "/" + parts[-1]


def _allowed_change(relative: str, path: tuple) -> bool:
    """Exact typed field whitelist; numeric observations are never on this list."""
    shape = tuple("*" if type(part) is int else part for part in path)
    if relative in {FULL + "raw_input_inventory.jsonl", INDEPENDENT + "input_inventory.jsonl",
                    RELATIVE + "input_inventory.jsonl"}:
        return shape == ("*", "path")
    allowed = {
        FULL + "selection.json": {("git_revision",), ("input_set_sha256",),
            ("inputs", "*", "path"), ("candidates", "*", "runs", "*", "summary_path")},
        FULL + "aggregate_compact.json": {("git_revision",), ("selection_path",),
            ("selection_sha256",), ("input_set_sha256",)},
        FULL + "run_manifest.json": {("git_revision",), ("output",), ("plan", "output"),
            ("selection_sha256",)},
        FULL + "seed_summaries.jsonl": {("*", "selection_sha256")},
        FULL + "export_manifest.json": {("files", "*", "sha256"), ("files", "*", "bytes")},
        INDEPENDENT + "analysis.json": {("run_source_revision",), ("raw_root",),
            ("input_inventory_sha256",), ("groups", "*", "input_raw_trajectories", "*")},
        RELATIVE + "analysis.json": {("source_run_revision",), ("raw_root",),
            ("selection_sha256",)},
    }
    return shape in allowed.get(relative, set())


def assert_scientific_values_unchanged(relative: str, original: Any, packaged: Any) -> None:
    """Reject all changes except exact metadata leaves, including schema/type edits."""
    def check(before, after, path):
        _require(type(before) is type(after), f"JSON type changed: {relative}:{path}")
        if isinstance(before, dict):
            _require(before.keys() == after.keys(), f"JSON fields changed: {relative}:{path}")
            for key in before:
                check(before[key], after[key], path + (key,))
        elif isinstance(before, list):
            _require(len(before) == len(after), f"JSON list changed: {relative}:{path}")
            for index, (left, right) in enumerate(zip(before, after)):
                check(left, right, path + (index,))
        elif before != after:
            _require(_allowed_change(relative, path), f"Scientific value changed: {relative}:{path}")
            size_field = relative == FULL + "export_manifest.json" and path[-1] == "bytes"
            _require((type(before) is int and size_field) or type(before) is str,
                     f"Non-metadata numeric value changed: {relative}:{path}")
    check(original, packaged, ())


def _transform_unpinned(relative: str, data: bytes) -> bytes:
    """Internal deterministic transform; public entry points enforce both pins."""
    if relative == FULL + "README.md":
        return README
    if relative == RELATIVE + "ARTIFACTS.sha256":
        return "".join(FOLLOWUP_CONTRACT[RELATIVE + name]["packaged_sha256"] + "  " + name + "\n"
                       for name in ("analysis.json", "input_inventory.jsonl", "per_seed.jsonl")).encode("ascii")
    changed = {FULL + name for name in ("selection.json", "aggregate_compact.json",
               "run_manifest.json", "seed_summaries.jsonl", "raw_input_inventory.jsonl", "export_manifest.json")}
    changed |= {prefix + name for prefix in (INDEPENDENT, RELATIVE)
                for name in ("analysis.json", "input_inventory.jsonl")}
    if relative not in changed:
        return data
    jsonl = relative.endswith(".jsonl")
    original = [_json(line) for line in data.splitlines()] if jsonl else _json(data)
    value = copy.deepcopy(original)
    if relative.endswith("input_inventory.jsonl"):
        for row in value:
            row["path"] = _external_path(row["path"])
    elif relative == FULL + "selection.json":
        value["git_revision"] = REPLACEMENT_TOKEN
        for candidate in value["candidates"]:
            for run in candidate["runs"]:
                run["summary_path"] = _external_path(run["summary_path"])
        for row in value["inputs"]:
            row["path"] = _external_path(row["path"])
        value["input_set_sha256"] = _input_digest(value["inputs"])
    elif relative == FULL + "aggregate_compact.json":
        value["git_revision"] = REPLACEMENT_TOKEN
        value["selection_path"] = FULL + "selection.json"
        value["selection_sha256"] = FOLLOWUP_CONTRACT[FULL + "selection.json"]["packaged_sha256"]
        value["input_set_sha256"] = FOLLOWUP_CONTRACT[FULL + "raw_input_inventory.jsonl"]["packaged_input_set_sha256"]
    elif relative == FULL + "run_manifest.json":
        value["git_revision"] = REPLACEMENT_TOKEN
        value["output"] = value["plan"]["output"] = EXTERNAL_ROOT
        value["selection_sha256"] = FOLLOWUP_CONTRACT[FULL + "selection.json"]["packaged_sha256"]
    elif relative == FULL + "seed_summaries.jsonl":
        for row in value:
            row["selection_sha256"] = FOLLOWUP_CONTRACT[FULL + "selection.json"]["packaged_sha256"]
    elif relative == FULL + "export_manifest.json":
        for row in value["files"]:
            pin = FOLLOWUP_CONTRACT[FULL + row["path"]]
            row["sha256"], row["bytes"] = pin["packaged_sha256"], pin["packaged_bytes"]
    elif relative == INDEPENDENT + "analysis.json":
        value["run_source_revision"], value["raw_root"] = REPLACEMENT_TOKEN, EXTERNAL_ROOT
        value["input_inventory_sha256"] = FOLLOWUP_CONTRACT[INDEPENDENT + "input_inventory.jsonl"]["packaged_sha256"]
        for group in value["groups"]:
            group["input_raw_trajectories"] = [_external_path(path) for path in group["input_raw_trajectories"]]
    elif relative == RELATIVE + "analysis.json":
        value["source_run_revision"], value["raw_root"] = REPLACEMENT_TOKEN, EXTERNAL_ROOT
        value["selection_sha256"] = FOLLOWUP_CONTRACT[FULL + "selection.json"]["packaged_sha256"]
    assert_scientific_values_unchanged(relative, original, value)
    if jsonl:
        return b"".join(_canonical(row) + b"\n" for row in value)
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def transform_bytes(relative: str | Path, data: bytes) -> bytes:
    relative = str(relative)
    _require(relative in FOLLOWUP_CONTRACT, f"Unknown follow-up evidence path: {relative}")
    pin = FOLLOWUP_CONTRACT[relative]
    _require(len(data) == pin["original_bytes"] and _digest(data) == pin["original_sha256"],
             f"Original evidence differs from pinned bytes: {relative}")
    result = _transform_unpinned(relative, data)
    _require(len(result) == pin["packaged_bytes"] and _digest(result) == pin["packaged_sha256"],
             f"Packaged evidence differs from pinned bytes: {relative}")
    return result


def declaration() -> dict:
    return {
        "schema_version": 1,
        "scope": "anonymous compact follow-up and exploratory fixed-history evidence",
        "replacement_token": REPLACEMENT_TOKEN,
        "files": [{"path": path, **FOLLOWUP_CONTRACT[path]} for path in INPUT_PATHS],
        "scientific_values": "All scientific JSON fields, observations, settings and numeric types are unchanged.",
        "external_inputs": {
            "included": False, "namespace": "original-external/",
            "meaning": "Original unshipped input files. Their hashes and byte counts are preserved; labels are anonymized and are not packaged paths.",
            "raw_replay": "NOT EXECUTED by this compact package; requires retained original raw trajectories and their recorded runtime.",
        },
        "original_provenance": {
            "run_signatures": "Historical hashes of original run identity, retained unchanged; not signatures of an anonymous raw archive.",
            "aggregate_hashes": "run_manifest.aggregate_sha256 and export_manifest.source.aggregate_sha256 describe the original unshipped full aggregate.",
            "source_inventories": "Recorded original source file hashes and source inventory digests are retained, not assertions about altered packaged tools.",
            "timestamps_and_runtime": "Original timestamps, Python build, dependency versions and measured runtimes are preserved as execution metadata.",
            "original_file_hashes": "Each original_sha256 binds the pre-transformation evidence; each packaged_sha256 binds the supplied copy.",
        },
        "rebound_metadata": "Packaged selection hashes, anonymized input-set digests, analysis inventory digest, export manifest and relative output checksums are updated deterministically.",
        "generated_artifact_provenance": "Generated table and chart headers retain original evidence digests. A generator may recover those digests only after the complete packaged contract and this declaration validate; original and packaged scientific JSON values are identical. Separately pinned analytical schematics are not measured evidence.",
    }


def _regular_file(root: Path, relative: str) -> Path:
    path = root / relative
    _require(path.is_file() and not path.is_symlink(), f"Missing regular file: {relative}")
    _require(path.resolve().is_relative_to(root.resolve()), f"Evidence escapes package root: {relative}")
    return path


def validate_packaged(root: str | Path) -> list[str]:
    root = Path(root)
    errors = []
    try:
        actual = _json(_regular_file(root, DECLARATION_NAME).read_bytes())
        _require(_canonical(actual) == _canonical(declaration()),
                 "Follow-up declaration differs from pinned contract")
    except (OSError, ValueError, TypeError, KeyError) as error:
        errors.append(str(error))
    for relative in INPUT_PATHS:
        try:
            pin = FOLLOWUP_CONTRACT[relative]
            data = _regular_file(root, relative).read_bytes()
            _require(len(data) == pin["packaged_bytes"] and _digest(data) == pin["packaged_sha256"],
                     f"Packaged follow-up evidence differs: {relative}")
        except (OSError, ValueError, TypeError, KeyError) as error:
            errors.append(str(error))
    errors.extend(_validate_artifacts(root))
    if not errors:
        try:
            _validate_bindings(root)
        except (OSError, ValueError, TypeError, KeyError) as error:
            errors.append(str(error))
    return errors


def _validate_bindings(root: Path) -> None:
    def read(relative):
        return _json(_regular_file(root, relative).read_bytes())
    selection_bytes = _regular_file(root, FULL + "selection.json").read_bytes()
    selection_hash = _digest(selection_bytes)
    selection = _json(selection_bytes)
    _require(selection["input_set_sha256"] == _input_digest(selection["inputs"]),
             "Selection input-set digest differs")
    aggregate, run = read(FULL + "aggregate_compact.json"), read(FULL + "run_manifest.json")
    inventory = [_json(line) for line in (root / (FULL + "raw_input_inventory.jsonl")).read_bytes().splitlines()]
    _require(aggregate["input_set_sha256"] == _input_digest(inventory),
             "Aggregate original-input inventory binding differs")
    _require(aggregate["selection_path"] == FULL + "selection.json", "Packaged selection path differs")
    for value in (aggregate, run, read(RELATIVE + "analysis.json")):
        _require(value["selection_sha256"] == selection_hash, "Packaged selection digest differs")
    for line in (root / (FULL + "seed_summaries.jsonl")).read_bytes().splitlines():
        _require(_json(line)["selection_sha256"] == selection_hash, "Seed selection binding differs")
    analysis = read(INDEPENDENT + "analysis.json")
    _require(analysis["input_inventory_sha256"] == _digest(
        (root / (INDEPENDENT + "input_inventory.jsonl")).read_bytes()), "Analysis inventory digest differs")
    export = read(FULL + "export_manifest.json")
    expected = {path[len(FULL):] for path in INPUT_PATHS
                if path.startswith(FULL) and path != FULL + "export_manifest.json"}
    _require(len(export["files"]) == len(expected) and {row["path"] for row in export["files"]} == expected,
             "Compact export file closure differs")
    for row in export["files"]:
        data = (root / (FULL + row["path"])).read_bytes()
        _require(row["sha256"] == _digest(data) and row["bytes"] == len(data),
                 "Compact export binding differs: " + row["path"])
    _require(export["raw_data_included"] is False, "Compact evidence must not claim raw inclusion")


def _validate_artifacts(root: Path) -> list[str]:
    errors = []
    for relative, pin in {**ARTIFACT_PINS, **SCHEMATIC_PINS}.items():
        try:
            data = _regular_file(root, relative).read_bytes()
            _require(len(data) == pin["bytes"] and _digest(data) == pin["sha256"],
                     f"Reviewed follow-up artifact differs: {relative}")
        except (OSError, ValueError, TypeError, KeyError) as error:
            errors.append(str(error))
    return errors


def validate_original(root: str | Path) -> list[str]:
    root = Path(root)
    errors = []
    for relative in INPUT_PATHS:
        try:
            transform_bytes(relative, _regular_file(root, relative).read_bytes())
        except (OSError, ValueError, TypeError, KeyError) as error:
            errors.append(str(error))
    errors.extend(_validate_artifacts(root))
    return errors


def original_digest(root: str | Path, relative: str | Path) -> str:
    relative = str(relative)
    _require(relative in FOLLOWUP_CONTRACT, f"Unknown follow-up evidence path: {relative}")
    errors = validate_packaged(root)
    _require(not errors, "Invalid anonymous follow-up package: " + "; ".join(errors))
    return FOLLOWUP_CONTRACT[relative]["original_sha256"]


def stage_transform(root: str | Path, source_repo: str | Path) -> list[str]:
    """Stage the exact closure from frozen originals; refuse source overwrite."""
    root, source_repo = Path(root).resolve(), Path(source_repo).resolve()
    _require(root != source_repo, "Cannot transform the source repository in place")
    outputs = {relative: transform_bytes(relative, _regular_file(source_repo, relative).read_bytes())
               for relative in INPUT_PATHS}
    _require(not _validate_artifacts(source_repo), "Original generated follow-up artifacts differ")
    outputs.update({relative: _regular_file(source_repo, relative).read_bytes()
                    for relative in (*ARTIFACT_PINS, *SCHEMATIC_PINS)})
    outputs[DECLARATION_NAME] = (json.dumps(declaration(), sort_keys=True, indent=2) + "\n").encode("ascii")
    for relative, data in outputs.items():
        destination = root / relative
        _require(not destination.is_symlink(), f"Refusing symlink destination: {relative}")
        _require(destination.resolve().is_relative_to(root), f"Destination escapes stage: {relative}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        try:
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    _require(not validate_packaged(root), "Staged follow-up contract failed")
    return sorted(outputs)
