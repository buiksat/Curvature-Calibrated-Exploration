# Development record

All development candidates and results, in the order they were run. Raw
outputs are under `RUNS/primary_deterministic`, `RUNS/primary_dev` and
`RUNS/secondary_dev` (see `artifacts.md`); summaries are in
`development_outputs/`.

Configurations investigated: 4 in total (P1, S1, S2, S3), within the limit of 12.
Development compute: about 0.05 core-hours (primary) and 0.78 core-hours (secondary).

## Deterministic algebraic check (P1, mean rewards, sigma = 0.25 retained)

Post-update query (round 8193, theta_new = 0 exactly):

| Quantity | Computed | Expected |
|---|---:|---:|
| current/reference width ratio | 0.85564 | 0.856 |
| absolute corrected-center error | 0.27038 | 0.270 |
| frozen-reference half-width | 0.28711 | 0.287 |
| naive-current half-width | 0.25290 | 0.253 |
| endpoint-transport half-width | 0.28711 | (equals frozen; see below) |

With the manuscript's envelope on the same history: beta = 228.14,
b = 0.15396, frozen half-width 0.89042, naive half-width 0.78410; the center
error 0.27038 is below both.

In one dimension with V_t >= Vbar_t, exp(d_Th / 2) s = sqrt(V_t / Vbar_t) |q| /
sqrt(V_t) = sbar, so endpoint transport reproduces the reference width
exactly. Endpoint and frozen coverage are therefore identical in this example.

## P1 on development seeds 50000-50015 (16 seeds)

Runtime 2.6 s per seed (one worker). No crash.

| Envelope | Naive failures | Frozen failures | Endpoint failures |
|---|---:|---:|---:|
| new certified variant | 16/16 | 0/16 | 0/16 |
| manuscript's original | 0/16 | 0/16 | 0/16 |

Every naive failure is at round 8193 and is an upper failure at the
suboptimal action phi = +1, where mu* exceeds the naive upper bound m + r_naive, together with a lower failure (mu* < m - r_naive) at the optimal action phi = -1;
no naive upper failure occurs at the optimal action phi = -1. The
post-update parameter lies in [-0.0024, 0.0025]. Interval length / span at
round 8193: naive 0.266, frozen and endpoint 0.302 (new envelope); naive
0.826, frozen and endpoint 0.938 (original envelope).

One analysis defect was found and fixed in development: the Thompson
cross-check against SciPy used a pure relative tolerance, which failed when
both values were about 1e-14 during the block. It now uses
1e-12 + 1e-9 |value|, matching the unit test. No run record changed. The
analysis also gained a feasible-span column and an expected-seed-count check.

Decision: keep P1. No other primary configuration was tried.

## Secondary candidates S1-S3 (W = 1, 10, 100) on seeds 51000-51015

144 runs (16 seeds x 3 policies x 3 widths), 0 crashes, 0 replay-check
failures, about 19-20 s per run, 940 s wall on 3 workers. The selection rule
of `DEVELOPMENT_PLAN.md` was applied with
`analyze_relin_coverage select-width` before any other development output was
summarized:

| W | max frozen potential bound / cap | qualifies |
|---|---:|---|
| 1 | 4.70 | no |
| 10 | 1.03 | no |
| 100 | 0.558 | yes |

Selected: W = 100 (S3).

Development outputs, recorded after the selection (descriptive, 16 seeds):

| W | frozen mean regret | naive minus frozen | endpoint minus frozen | own-coverage failures (any policy) | s/sbar range | max d_Th | frozen bound, direct sum (median) | frozen bound, potential (median) | cap |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 1 | 604.94 | -0.01 [-2.91, 3.03] | 4.03 [0.57, 7.35] | 0 | 0.991-1.249 | 0.444 | 26,081 | 185,467 | 40,000 |
| 10 | 92.95 | -0.47 [-2.57, 2.04] | -0.81 [-3.26, 1.62] | 0 | 0.999-1.022 | 0.0433 | 5,585 | 40,777 | 40,000 |
| 100 | 50.21 | 0.13 [-1.57, 1.95] | -0.79 [-3.37, 1.76] | 0 | 0.9998-1.0022 | 0.0043 | 2,995 | 22,227 | 40,000 |

Brackets are 95% seed-bootstrap intervals. At the selected W = 100 the
current and reference widths differ by at most 0.22%, so this cell is not
expected to separate the three policies. The rule was not revisited.
With the manuscript's envelope, the second study's frozen mean regret at
W = 1 was 1,902.1 (Table "descriptive cells"); the new certified envelope gives
604.9 here, on different seeds.
