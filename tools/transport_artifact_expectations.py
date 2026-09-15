#!/usr/bin/env python3
"""Regenerate the published tables, figures and CSVs from the locked aggregate.

This holds the single copy of the expectation logic.  It builds every declared
artifact *in memory* from the committed aggregate and returns the bytes; it
writes nothing, so it is safe to run against a working tree whose generated
artifacts are protected.

Two callers share it: the detached committed-evidence verifier and the
submission ledger shipped in the anonymous supplement.  It imports only the
experiment package, the standard library and the pinned anonymous-package
contract, so it carries no repository, host or author information and can be
shipped to reviewers as is.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

AGGREGATE_PATH = Path("results/derived/transport_instantiation/full_aggregate.json")

# An anonymous supplement ships modified copies of two evidence files with one
# metadata string replaced, and declares that in ANONYMIZATION.json at its root.
# The declaration is reviewer-editable and is therefore never the authority for
# what bytes are acceptable: tools/anonymous_package_contract.py pins the exact
# paths, digests, byte counts, token and sidecar text in code, and the
# declaration is validated against those constants.
#
# When the tree is a packaged one the artifacts must still be regenerated with
# the digest of the ORIGINAL evidence -- also pinned in the contract -- because
# that is the digest the published artifacts were stamped with and the one their
# provenance records name.  If the redaction had perturbed anything the
# artifacts depend on, they would then fail to reproduce, which is exactly the
# property worth checking.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import anonymous_package_contract as contract  # noqa: E402


class ArtifactExpectationError(RuntimeError):
    """Raised when the declared rendering stack cannot be imported."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_artifact_text(root: Path) -> tuple[dict[Path, str], str]:
    """Return {absolute path: expected text} and the aggregate SHA-256."""

    try:
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        import experiments.make_transport_instantiation_artifacts as maker
        from experiments.aggregate_transport_instantiation import METHODS
    except Exception as error:  # pragma: no cover - environment dependent
        raise ArtifactExpectationError(
            "the declared repository rendering stack is unavailable "
            f"({error.__class__.__name__}: {error})"
        ) from error

    aggregate_path = root / AGGREGATE_PATH
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    # Stamp the digest the published artifacts actually carry.  For an original
    # tree that is the file's own digest; for a packaged tree it is the pinned
    # digest of the evidence the artifacts were generated from -- taken from the
    # code contract, never from the shipped declaration.
    pinned_original = (
        contract.original_sha256(str(AGGREGATE_PATH))
        if contract.is_packaged_tree(root) else None
    )
    aggregate_sha = pinned_original or sha256_file(aggregate_path)
    source_comment = f"% Source aggregate SHA-256: {aggregate_sha}\n"
    figures = root / "paper/figures"
    tables = root / "paper/tables"
    targets = sorted(float(v) for v in aggregate["target_D"])
    token = maker._target_file_token

    regret_panel = {
        t: f"transport_instantiation_regret_D-{token(t)}.csv" for t in targets
    }
    path_panel = {
        t: f"transport_instantiation_tightness_D-{token(t)}.csv" for t in targets
    }
    bound_panel = {
        t: f"transport_instantiation_bound_D-{token(t)}.csv" for t in targets
    }

    regret_rows = sorted(
        maker._downsample_curve_records(aggregate["regret_curves"]),
        key=lambda i: (
            float(i["target_D"]),
            METHODS.index(str(i["method"])),
            int(i["round"]),
        ),
    )
    bound_rows = sorted(
        maker._downsample_curve_records(aggregate["bound_decomposition"]),
        key=lambda i: (float(i["target_D"]), int(i["round"])),
    )
    regret_csv_rows = [
        {
            **r,
            "method_index": METHODS.index(str(r["method"])),
            "aggregate_sha256": aggregate_sha,
        }
        for r in regret_rows
    ]
    path_csv_rows = [
        {**r, "aggregate_sha256": aggregate_sha}
        for r in maker._path_plot_records(aggregate)
    ]
    bound_csv_rows = [{**r, "aggregate_sha256": aggregate_sha} for r in bound_rows]

    regret_fields = (
        "target_D",
        "horizon",
        "method",
        "method_index",
        "round",
        "mean",
        "ci_low",
        "ci_high",
        "aggregate_sha256",
    )
    path_fields = (
        "target_D",
        "series_code",
        "x",
        "y",
        "count",
        "marker_size",
        "aggregate_sha256",
    )
    bound_fields = (
        "target_D",
        "horizon",
        "round",
        "statistical_bound_component",
        "historical_bound_component",
        "path_inflation_component",
        "current_bias_cumulative",
        "cumulative_pseudo_regret",
        "sharp_theorem_rhs",
        "aggregate_sha256",
    )

    expected: dict[Path, str] = {
        tables / "transport_instantiation_validity.tex": source_comment
        + maker.make_validity_table(aggregate),
        tables / "transport_instantiation_performance.tex": source_comment
        + maker.make_performance_table(aggregate),
        tables / "transport_instantiation_tightness.tex": source_comment
        + maker.make_tightness_table(aggregate),
        figures
        / "transport_instantiation_regret.csv": maker._csv_text(
            regret_fields, regret_csv_rows
        ),
        figures
        / "transport_instantiation_tightness.csv": maker._csv_text(
            path_fields, path_csv_rows
        ),
        figures
        / "transport_instantiation_bound.csv": maker._csv_text(
            bound_fields, bound_csv_rows
        ),
        figures / "transport_instantiation_regret.tex": source_comment
        + maker.make_regret_figure_tex(aggregate, regret_panel),
        figures / "transport_instantiation_tightness.tex": source_comment
        + maker.make_path_figure_tex(aggregate, path_panel),
        figures / "transport_instantiation_bound.tex": source_comment
        + maker.make_bound_figure_tex(aggregate, bound_panel),
    }
    for target in targets:
        expected[figures / regret_panel[target]] = maker._csv_text(
            regret_fields,
            [r for r in regret_csv_rows if float(r["target_D"]) == target],
        )
        expected[figures / path_panel[target]] = maker._csv_text(
            path_fields, [r for r in path_csv_rows if float(r["target_D"]) == target]
        )
        expected[figures / bound_panel[target]] = maker._csv_text(
            bound_fields, [r for r in bound_csv_rows if float(r["target_D"]) == target]
        )

    return expected, aggregate_sha


def check(root: Path, *, require_package: bool | None = None
          ) -> list[tuple[str, bool, str]]:
    """Compare every expected artifact against disk, its sidecar and its provenance.

    With package mode required, a tree that carries no anonymization declaration
    fails outright instead of being checked with repository semantics.
    """

    required = contract.package_required(require_package)
    results: list[tuple[str, bool, str]] = []

    # When package mode is required, settle that before anything else: a missing
    # declaration means this is not the package it claims to be.
    if required and not contract.is_packaged_tree(root):
        name, ok, detail = contract.missing_declaration_result(root)
        return [(f"anonymous package: {name}", ok, detail)]

    expected, aggregate_sha = expected_artifact_text(root)

    # When the tree is a packaged one, check it against the pinned contract
    # before checking anything that depends on its bytes.  Every expectation
    # comes from shipped code; ANONYMIZATION.json only has to agree with it.
    if contract.is_packaged_tree(root):
        for name, ok, detail in contract.check(root, require_package=required):
            results.append((f"anonymous package (NOT original evidence bytes): "
                            f"{name}", ok, detail))
    for path, text in sorted(expected.items()):
        relative = str(path.relative_to(root))
        want = hashlib.sha256(text.encode("ascii")).hexdigest()
        if not path.is_file():
            results.append((relative, False, "artifact is missing from the tree"))
            continue
        got = sha256_file(path)
        sidecar = Path(str(path) + ".sha256")
        provenance = Path(str(path) + ".provenance.json")
        sidecar_value = (
            sidecar.read_text(encoding="ascii").split()[0] if sidecar.is_file() else ""
        )
        bound_ok = False
        if provenance.is_file():
            record = json.loads(provenance.read_text(encoding="utf-8"))
            bound_ok = record.get("artifact_sha256") == got and any(
                i.get("sha256") == aggregate_sha
                and i.get("path") == str(AGGREGATE_PATH)
                for i in record.get("inputs", [])
            )
        results.append((
            relative,
            want == got == sidecar_value and bound_ok,
            f"regen={want[:16]} disk={got[:16]} sidecar={sidecar_value[:16]} "
            f"bound_to_aggregate={bound_ok}",
        ))
    return results


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--require-package", action="store_true", default=None,
        help="fail if the tree is not an anonymous package; also implied by "
             f"{contract.ENV_REQUIRE_PACKAGE}=1")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        results = check(root, require_package=args.require_package)
    except ArtifactExpectationError as error:
        print(f"FAIL  {error}")
        return 1
    bad = 0
    for relative, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {relative}")
        if not ok:
            print(f"        -> {detail}")
            bad += 1

    # The declaration checks an anonymized supplement adds are not artifacts, so
    # they are counted separately.  Two things used to go wrong here when the
    # declaration was missing in required-package mode: the contract line
    # counted the checks that ran rather than the ones that passed, so a single
    # failure printed as "1 ... checks passed", and the source label was chosen
    # from that same count, so a tree with no declaration was still described as
    # a packaged aggregate while reporting "0 of 0 artifacts".  Both now come
    # from what actually happened.
    contract_results = [r for r in results
                        if r[0].startswith("anonymous package")]
    artifacts = [r for r in results
                 if not r[0].startswith("anonymous package")]
    contract_passed = sum(1 for _, ok, _ in contract_results if ok)
    good = sum(1 for _, ok, _ in artifacts if ok)
    packaged = contract.is_packaged_tree(root)
    source = "packaged (anonymized) aggregate" if packaged else "locked aggregate"
    print()
    if contract_results:
        print(f"{contract_passed} of {len(contract_results)} anonymous-package "
              "contract checks passed against constants pinned in shipped code")
    if artifacts:
        print(f"{good} of {len(artifacts)} generated artifacts regenerate "
              f"byte-identically from the {source}")
    else:
        print("no generated artifact was checked: the run stopped before "
              "reaching them")
    if bad:
        print(f"FAILED: {bad} of {len(results)} checks did not pass; "
              "this tree does not match the expectations")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
