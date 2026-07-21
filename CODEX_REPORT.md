# Final Revision Report

Audit date: 2026-07-21

## Disposition

The acceptance-critical theory, predictable certificate implementation,
nonlinear execution, contextual sanity benchmark, phase diagram, paper build,
and anonymous release validation are complete. The revision is not described as
fully submission-ready because no external standard benchmark passes the sanity
gate, published neural-baseline implementations were not independently
validated, floating-point checks are not verified enclosures, and no
accelerator or trained-large-model systems experiment was run. The official
target-year AISTATS checklist is also absent.

No Git history operation, commit, or push was performed. The AISTATS style file
was not modified.

## Theory and implementation

- `experiments/path_certificates.py` implements the `O(d)` Welford path state,
  collection-residual energy, Taylor schedule, observable information surrogate,
  and pre-action `chi_bar`, `psi_bar`, and `beta_bar` computations.
- `tests/test_path_certificates.py` checks direct-history equality, numerical
  cancellation handling, transfer and mismatch domination, all-action centering,
  Taylor and information bounds, and filtration order.
- The manuscript adds the operational certificate lemma and corollary, the
  bounded-path near-linear rate, the exact tanh-link specialization, a
  rank-sensitive refresh/endpoint bound, and roundwise scalar-width invariance.
- `THEORY_AUDIT.md` inventories all 26 theorem-family results. It reports no open
  formal-correctness or proof-presentation gap. `THEORY_BLOCKERS.md` records how
  all former blockers were resolved.
- The central theorem and its sublinearity conditions are byte-for-byte unchanged:

  ```text
  R_T <= 2 sqrt((sigma^2 + G^2/lambda) Lambda_T^C S_T) + 2 E_T
  Lambda_T^C S_T = o(T^2),  E_T = o(T).
  ```

## Linear certification audit

The category is the same in fixed-reference and independently validation-tuned
configurations:

| Policy | Category | Reason |
|---|---|---|
| dense full Gram | `ex_ante_theorem_certified` | analytic `u_t=1`, exact-arithmetic dense-solve semantics |
| unrescaled window | `ex_ante_theorem_certified` | analytic subset relation gives `u_t=1` |
| stale refresh | `ex_ante_theorem_certified` | analytic factor used by this bounded linear construction |
| full-Gram CG | `posthoc_theorem_event_verified` | float64 `cond(C)` is not a verified upper enclosure |
| diagonal | `posthoc_theorem_event_verified` | generalized-eigenvalue point estimate is unenclosed |
| rescaled subsample | `posthoc_theorem_event_verified` | generalized-eigenvalue point estimate is unenclosed |
| Lanczos-Ritz | `posthoc_theorem_event_verified` | generalized-eigenvalue point estimate is unenclosed |

No primary linear row is classified `cg_solver_certified`. All 280 evaluation
traces passed the checked confidence, transfer, CG, determinant, width-sum, and
realized-regret events in float64. The exact policy ledger is
`results/derived/certification_audit.json`.

The confidence implementation is

```text
beta_base_t = sqrt(d log(1 + (t-1)G^2/(d lambda sigma^2))
                   + 2 log(1/delta)) + sqrt(lambda) S
bar_beta_t  = c_bonus * beta_base_t,  c_bonus >= 1.
```

Thus `c_bonus` multiplies the already valid complete base confidence radius,
including `sqrt(lambda) S`. It does not replace `beta_bar_t`, multiply `u_t`,
or multiply the CG factor separately. In this linear audit `psi_bar_t=0`.

## Primary Table 1

Table 1 is deliberately a mixture, identified in its caption:

- tanh rows: one fixed theoretical configuration;
- balanced rows: configurations selected by mean pseudo-regret on ten tuning
  seeds and rerun on 30 disjoint evaluation seeds.

Its columns are self-defining:

- Regret: mean cumulative pseudo-regret.
- `[95% CI]`: marginal Student-t interval; the displayed plus/minus in prose is
  its half-width.
- Event fail.: evaluation runs with any observed checked-event failure divided
  by evaluation runs.
- Time: seconds per complete run, including certificate and dense audit work
  where present.
- Status: post-hoc event verified or uncertified.

The former ambiguous `Viol.`, `Lambda_T^C`, `u_max`, and `CG/round` columns are
not in the revised primary table. The separately reported old full-Gram value is
therefore no longer juxtaposed with a different table configuration.

## Linear bound scale

Fixed-reference RHS/regret ratios at `T={250,500,1000}` are:

| Policy | 250 | 500 | 1000 |
|---|---:|---:|---:|
| full dense | 361.5 | 422.4 | 461.7 |
| full CG | 375.7 | 438.1 | 479.3 |
| diagonal | 4120.8 | 7710.5 | 13456.0 |
| Lanczos-Ritz | 495.7 | 496.4 | 509.3 |
| subsample 64 | 339.7 | 373.1 | 396.6 |
| refresh 20 | 370.3 | 465.1 | 526.7 |
| window 64 | 252.0 | 255.3 | 260.2 |

`results/derived/linear_bound_metrics.json` also stores `R_T`, RHS, `R_T/T`,
and `RHS/T` for fixed and tuned rows. Every displayed RHS exceeds the exact
maximum possible pseudo-regret, so every bound is numerically vacuous. Full
Gram's normalized RHS decreases over the tested horizons, whereas window 64's
increases; this is a finite-trajectory observation, not asymptotic evidence.

## Predictable nonlinear execution

The tanh-link Gaussian policy ran 50 evaluation seeds per center, with disjoint
tuning seeds. Every theorem input was computed before selection from analytic
constants, path state, the exact objective-gradient norm, and an analytic CG
condition bound. No teacher or post-hoc quantity entered the score.

| Center | Mean regret [95% CI] | Observed failures | Mean RHS/regret | Category |
|---|---:|---:|---:|---|
| original | 7.86 [7.66, 8.07] | 0/50 | 6956.7 | `posthoc_theorem_event_verified` |
| corrected | 5.69 [5.46, 5.92] | 0/50 | 1328.9 | `posthoc_theorem_event_verified` |

The schedules are predictable, but ordinary float64 residual/dense checks are
not interval enclosures. The result therefore meets the observed-event gate but
is not called verified-enclosure theorem certification.

## Curvature and contextual results

- Phase map: 8 preregistered cells, 7 online methods, 30 evaluation seeds per
  cell, plus separately tagged common-trajectory diagnostics. Diagonal has lower
  regret than exact full in all eight cells; block diagonal in six with two
  unresolved. Exact full has lower regret than window and stale refresh in all
  eight and than rank-3 Lanczos in seven. Full CG matches exact full numerically.
- Balanced contextual task at `T=200`: full GGN-CG 21.94 [20.64,23.23],
  diagonal 16.11 [14.62,17.61], LinUCB 10.58 [9.82,11.33], NeuralLinear
  10.01 [9.33,10.68], frozen last-layer UCB 7.44 [6.90,7.99]. Context-free
  UCB1 and Thompson sampling have 90.35 and 89.40, so the contextual sanity
  prerequisite passes. The neural baselines are local matched implementations,
  not asserted reproductions of published packages.
- Systems: at `d=128,n=512,K=10`, row-batched CG is about 1.8x faster than
  separate solves; Jacobi does not help that cell. The matrix-free synthetic
  operator reaches `d=8192` without dense allocation. This is CPU operator
  evidence only.

## Covertype audit

The fixed test split has 116,203 targets:

| Label / arm | Count | Fraction |
|---|---:|---:|
| 1 / 0 | 42,267 | 0.363734 |
| 2 / 1 | 56,737 | 0.488258 |
| 3 / 2 | 7,221 | 0.062141 |
| 4 / 3 | 536 | 0.004613 |
| 5 / 4 | 1,902 | 0.016368 |
| 6 / 5 | 3,444 | 0.029638 |
| 7 / 6 | 4,096 | 0.035249 |

Uniform random has expected accuracy `1/7=0.142857` and expected regret
`{171.4,428.6,857.1,1285.7}`. The fixed test-majority arm is an undeployable
oracle diagnostic with accuracy `0.488258` and expected regret
`{102.35,255.87,511.74,767.61}` at `T={200,500,1000,1500}`.

The following intervals are marginal regret intervals. `Pair` is the paired
method-minus-full regret interval. Runtime is mean seconds per complete run.
All rows are `uncertified`; contextual rows use binary rewards through Gaussian
squared-loss curvature, and the context-free rows are outside Theorem 1.

| Policy | T | Regret [95% CI] | Accuracy | Pair [95% CI] | Time |
|---|---:|---:|---:|---:|---:|
| full GGN-CG | 200 | 163.3 [149.3,177.3] | 0.183 | reference | 0.223 |
| full GGN-CG | 500 | 399.0 [364.8,433.2] | 0.202 | reference | 0.865 |
| full GGN-CG | 1000 | 794.3 [730.3,858.3] | 0.206 | reference | 2.745 |
| full GGN-CG | 1500 | 1189.7 [1097.5,1281.9] | 0.207 | reference | 5.665 |
| frozen Gram | 200 | 164.0 [150.4,177.6] | 0.180 | 0.7 [-0.8,2.2] | 0.030 |
| frozen Gram | 500 | 401.1 [366.4,435.8] | 0.198 | 2.1 [-1.0,5.2] | 0.075 |
| frozen Gram | 1000 | 797.5 [732.5,862.5] | 0.202 | 3.2 [-0.1,6.5] | 0.150 |
| frozen Gram | 1500 | 1193.0 [1098.7,1287.3] | 0.205 | 3.3 [-3.4,10.0] | 0.225 |
| diagonal full | 200 | 166.4 [151.3,181.5] | 0.168 | 3.1 [-0.4,6.6] | 0.025 |
| diagonal full | 500 | 407.7 [370.7,444.7] | 0.185 | 8.7 [0.5,16.9] | 0.095 |
| diagonal full | 1000 | 807.2 [737.9,876.5] | 0.193 | 12.9 [-2.7,28.5] | 0.295 |
| diagonal full | 1500 | 1204.4 [1103.1,1305.7] | 0.197 | 14.7 [-3.2,32.6] | 0.602 |
| last-layer full | 200 | 170.7 [164.8,176.6] | 0.146 | 7.4 [-1.7,16.5] | 0.012 |
| last-layer full | 500 | 420.9 [403.7,438.1] | 0.158 | 21.9 [2.5,41.3] | 0.029 |
| last-layer full | 1000 | 849.4 [813.1,885.7] | 0.151 | 55.1 [23.2,87.0] | 0.057 |
| last-layer full | 1500 | 1273.1 [1221.7,1324.5] | 0.151 | 83.4 [39.6,127.2] | 0.086 |
| last-layer diagonal | 200 | 171.1 [164.6,177.6] | 0.144 | 7.8 [-0.5,16.1] | 0.014 |
| last-layer diagonal | 500 | 426.0 [405.8,446.2] | 0.148 | 27.0 [9.3,44.7] | 0.029 |
| last-layer diagonal | 1000 | 851.6 [810.3,892.9] | 0.148 | 57.3 [29.4,85.2] | 0.051 |
| last-layer diagonal | 1500 | 1274.9 [1213.4,1336.4] | 0.150 | 85.2 [46.9,123.5] | 0.073 |
| greedy | 200 | 162.3 [148.8,175.8] | 0.189 | -1.0 [-6.6,4.6] | 0.008 |
| greedy | 500 | 393.9 [360.7,427.1] | 0.212 | -5.1 [-14.7,4.5] | 0.023 |
| greedy | 1000 | 781.9 [715.8,848.0] | 0.218 | -12.4 [-32.7,7.9] | 0.043 |
| greedy | 1500 | 1166.2 [1067.8,1264.6] | 0.223 | -23.5 [-52.1,5.1] | 0.063 |
| UCB1 | 200 | 145.4 [138.6,152.2] | 0.273 | -17.9 [-35.3,-0.5] | 0.001 |
| UCB1 | 500 | 332.5 [319.8,345.2] | 0.335 | -66.5 [-100.3,-32.7] | 0.002 |
| UCB1 | 1000 | 616.2 [597.9,634.5] | 0.384 | -178.1 [-241.6,-114.6] | 0.005 |
| UCB1 | 1500 | 895.6 [871.4,919.8] | 0.403 | -294.1 [-388.1,-200.1] | 0.007 |
| Beta-Bernoulli TS | 200 | 124.7 [119.7,129.7] | 0.376 | -38.6 [-53.0,-24.2] | 0.002 |
| Beta-Bernoulli TS | 500 | 284.9 [276.5,293.3] | 0.430 | -114.1 [-144.2,-84.0] | 0.004 |
| Beta-Bernoulli TS | 1000 | 544.0 [533.1,554.9] | 0.456 | -250.3 [-312.8,-187.8] | 0.013 |
| Beta-Bernoulli TS | 1500 | 802.6 [788.2,817.0] | 0.465 | -387.1 [-479.3,-294.9] | 0.017 |

UCB1 and Beta-Bernoulli Thompson sampling beat every contextual method at every
horizon. Covertype is therefore an appendix-only failed baseline check, not
external validation of curvature-aware exploration.

## Manuscript changes and layout

- Abstract: removes the eight-cell Spearman headline; leads with operational
  certificates, the bounded-path rate, zero observed tanh event failures, and
  the negative curvature comparison.
- Conclusion: treats full GGN as a reference operator and states that Covertype
  is not evidence about curvature choice.
- The unrecovered oracle-selected legacy section is removed from the evidentiary
  chain.
- Source/rendered locations:

  | Item | Source | PDF page |
  |---|---:|---:|
  | Algorithm 1 | `paper/main.tex:303` | 3 |
  | Figure 1 | `paper/main.tex:610` | 6 |
  | Table 1 | `paper/main.tex:625` | 7 |
  | References | `paper/main.tex:726` | 8 |

The main text ends on page 7. The PDF has 38 pages total.

## Validation

- `pytest`: 143 passed.
- Clean `latexmk -C` then PDF build: passed.
- `git diff --check`: passed.
- Cross-references/citations: resolved.
- Overfull boxes: zero content-generated; one known style-generated abstract
  warning remains isolated.
- PDF metadata: blank title and author; anonymous author text.
- Fonts: all embedded; zero Type 3.
- Final PDF SHA-256:
  `1cdaf5fd07a78f8b5ec0fa8805372b6209d0cea6372ece9d5b6104a7cdad7453`.

## Anonymous releases

| Tier | Files | Bytes | MiB | Manifest SHA-256 |
|---|---:|---:|---:|---|
| archival `release/` | 11,370 | 527,542,915 | 503.1 | `b6818ebcad1fc1c820ccccf14182a3619fcb2c77cb92396c87b54557b22ab599` |
| review `release_review/` | 201 | 94,120,259 | 89.8 | `d50516d310a1cdbeffca0a2d2e85c3c3e8c1a4a0675653e805f7986c9a8efe4e` |

Both releases use anonymous source-tree hash
`df93d7794dc36706bccf861a1ade9f9ae172e2423eccaece031c727424e6adc3`.
All manifest hashes/sizes, 3,748 zstd streams, 42 provenance sidecars, 5 paper
references, and source-reference inventories verify. The review tier retains
10 representative raw runs and hash-indexes all 11,211 source raw files.

Identity checks passed with no allowlist exception: dynamic local identity,
fixed path/URL/name patterns via `rg -a`, plain-text email regex, decompressed
zstd scan, `strings`, ExifTool, PDF metadata, and PNG metadata. A permissive
regex over compressed bytes produced entropy false positives only; none survived
decompression. There are no ZIP or Parquet files, so `zipinfo` and Parquet
metadata checks are not applicable.

## Remaining scientific scope

- No Wheel, Mushroom, or balanced real-data benchmark has been executed.
- Local NeuralLinear/NeuralUCB/NeuralTS implementations are not independently
  validated published implementations; NN-UCB/TS, EKF, LMC-TS, KFAC, and
  block-Laplace remain unrun.
- No matched-wall-clock retuning, nonzero representation-drift phase cell,
  verified interval arithmetic, KFAC/block preconditioner, accelerator run, or
  trained `10^5`-`10^7` parameter model benchmark is reported.
- The official target-year style/checklist package must still be supplied by
  the venue. `paper/aistats2026.sty` was intentionally left unchanged.

## Unresolved legacy records

The complete raw records and exact construction code for the old
oracle-selected matched-coverage study were not recovered. Its 18 point
estimates and 11 intervals were not altered or regenerated and are not used to
support the revised claims.

## Reproduction commands

Run from the repository root:

```sh
.venv/bin/pytest -q
.venv/bin/python -m experiments.make_certification_audit
.venv/bin/python -m experiments.make_linear_bound_artifact
.venv/bin/python -m experiments.make_covertype_horizon_artifact
.venv/bin/python -m experiments.make_revision_paper_artifacts
(cd paper && latexmk -C)
(cd paper && latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex)
git diff --check
pdfinfo paper/main.pdf
pdffonts paper/main.pdf
pdftotext -layout paper/main.pdf paper/main.txt
.venv/bin/python tools/build_anonymous_supplement.py --tier full --output release --overwrite
.venv/bin/python tools/build_anonymous_supplement.py --tier review --output release_review --overwrite
```

Exact experiment execution and aggregation commands are in
`experiments/README.md`.
