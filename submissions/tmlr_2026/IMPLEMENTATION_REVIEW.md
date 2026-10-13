# Initial implementation-branch inspection

Inspected `cce-experiments` at `7bd8e4d78b62e1ea510da51deac7cc2c4624637d`
on 2026-10-13 using Git objects, without switching away from local `main`.
This is source and artifact inspection, not a fresh test or experiment run.

## Confirmed

- `experiments/transport_instantiation.py` implements the controlled
  29-parameter scaled-tanh study with dense matrices, Cholesky solves,
  endpoint eigenvalue diagnostics, and factor-path quadrature.
- The locked aggregate records 2,400 runs, including 600 primary-policy runs
  across 12 cells. Those are recorded outcomes, not experiments rerun here.
- The aggregate blob is 77,035,403 bytes and independently hashes to
  `0ddebd4915dd2e264e24b7b25047d24f86c3cdf63930a1e6df77585e0b97de02`.
  The 1,282,446-byte selection blob hashes to
  `8c16bec7cc220109df3fd7173c3d06ae6c6e1b95e9db5bc5b8c3377b3564f6f4`.
  Both match their committed SHA-256 sidecars.
- Existing generated tables, figures, bibliography, and transport proofs
  match the original main revision. The newer manuscript separately clarifies
  computational costs and describes the endpoint-certificate ratio.
- The research branch already includes numerical-verification tools and a
  TMLR packaging workflow. Its previous test counts and release artifacts
  were produced on another state/host and have not been revalidated here.

## Remaining checks

1. Raw per-run trajectories are not tracked. Full raw-provenance verification
   and paired-bootstrap recomputation cannot be completed from the committed
   aggregate alone; do not synthesize the missing per-seed data.
2. `experiments/requirements.txt` pins SciPy 1.15.2, while a bundled wheel is
   1.13.1. Establish the intended reproducible runtime before testing.
3. The host-specific Buck setup expects `/data/repos/fbsource` and is documented
   as broken. Verify the portable Python route independently; do not claim the
   native build works from the existence of its configuration.
4. Two selection-time source files differ from their original recorded
   digests: the renderer and `experiments/BUCK`. The current verifier pins both
   divergences explicitly; older prose describing one divergence is stale.
5. The Covertype/Nyström extension remains excluded and uncleared. Its fixture
   tests are not evidence of a completed realistic-data study.
6. The older source-package manifest describes the research branch's release.
   It cannot certify this new main-branch snapshot, disclosure, or caption
   changes without a new build and relevant checks.

## Next implementation validation

These commands are documented on the research branch, not executed as part of
this inspection. Run them from a prepared research checkout after resolving
the runtime requirements:

```bash
python -m pytest -q tests experiments/tests
python tools/verify_tmlr_submission_numbers.py
python tools/transport_artifact_expectations.py --root .
python tools/verify_transport_committed_evidence.py
TMLR_OUT=/tmp/cce-tmlr-release bash submissions/tmlr_2026/build.sh
TMLR_OUT=/tmp/cce-tmlr-release python -m pytest -q tests/test_tmlr_release_package.py
```

The research branch's `build.sh` builds its full release package; the main
branch script in this directory builds the manuscript and its LaTeX source
archive only. The full controlled study is a separate multi-hour run.
