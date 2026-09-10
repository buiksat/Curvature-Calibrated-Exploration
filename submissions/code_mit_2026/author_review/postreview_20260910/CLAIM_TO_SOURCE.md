# CODE@MIT post-review claim-to-source ledger

## Scope and status

`REVIEWED` is commit `5718995cae80f34b5b98b464f3d9090758be4871`.
Every scientific source below was read from that Git revision. The locked full
aggregate has SHA-256
`0ddebd4915dd2e264e24b7b25047d24f86c3cdf63930a1e6df77585e0b97de02`
and Git blob `aac10364c27b9a401dca78c50708c8f0d432628e`.

This ledger covers all retained numerical cells in the manuscript comparison
table and all proposed internal entries for the post-review Section 6 analysis.
The required label for every proposed internal entry is:

> Post-review descriptive analysis of the locked evaluation.

The proposed entries are descriptive checks on the locked controlled scaled-tanh
evaluation.
They are not new runs, theorem guarantees, or Covertype results. Author inclusion
of E01 and the paired standard errors remains pending. Terminal inflation
quantiles are excluded.

## Source registry

A source key in a claim record incorporates the revision, path, SHA-256, and Git
blob in this registry. Candidate blob IDs were computed from the exact bytes before
commit; those files do not exist at `REVIEWED`.

| Key | Revision | Path | SHA-256 | Git blob |
|---|---|---|---|---|
| M0 | `REVIEWED` | `submissions/code_mit_2026/main.tex` | `c5aaafdcb5049e5b91b1d92582cf149f50dc7a271d5a3d90175c6a62467cf1cc` | `da83925c52e22ba76f6338d959cc3152364f38f4` |
| S0 | `REVIEWED` | `review/transport_instantiation/aggregate/index.json` | `bcbc2504dd160ea780af48f1b6ecad7892fe641f797ed4ac44037fce57ef53d0` | `a703ff71a968d7faa7f75edb51d2df509b4d4e97` |
| S1 | `REVIEWED` | `review/transport_instantiation/aggregate/policy_outcomes.jsonl` | `17b7f69e66efec255c47cc2245e75e28dc8d4a0dcd4d055c0cdd51dd362f3e1e` | `2c08594fad86209c78fd5a37a37a86e8d3511e05` |
| S2 | `REVIEWED` | `review/transport_instantiation/aggregate/certificate_tightness.jsonl` | `562d0a065941817a14fab33c3f91a2070cd469e65b6e5d67f60e04e2880497fc` | `ba9739b440ad58be52af92cd6076278c68b4ed00` |
| S3 | `REVIEWED` | `review/transport_instantiation/aggregate/validity.jsonl` | `7cb3dcfbb79c4ccd9111934472d775d3320b53880d37dd4d4c0b52efbbffb815` | `d1392db89d95831a2759f60a43f5ffc97c8fdaee` |
| S4 | `REVIEWED` | `review/transport_instantiation/aggregate/bound_decomposition.part-000.jsonl` | `9979943a2025ff45f3cc8550332d14714a5f927ef41d26778ded11a4a8add2b3` | `1b751f12f3b62356885e4a09e1b6516463a1f5fb` |
| S5 | `REVIEWED` | `review/transport_instantiation/aggregate/bound_decomposition.part-001.jsonl` | `3dcd66047fabb9c21421ca859d1b833b6e25d548a6b28781b786c85d27af1aba` | `e7747120c18adece7e16f9fe3f1776dadcb66a78` |
| S6 | `REVIEWED` | `experiments/configs/transport_instantiation.yaml` | `d6f6c0de47651a7e6a291f63ba609654afd5cff6cc13d11722d9fae587e7abdd` | `2fcfa77fa5b69ba3e9111cc65c2f1d19a1078955` |
| S7 | `REVIEWED` | `experiments/TRANSPORT_INSTANTIATION_PROTOCOL.md` | `6aee823a2e4f11b02ae4144b8f7c8f2be07d8adadc8e44cfaac1ee10c0ca59f0` | `ca3ac59158d415dbb2ea770b2315246454c8acc8` |
| S8 | `REVIEWED` | `review/transport_instantiation/aggregate/top_level.json` | `832fc0478cfc6b17dc2e680926dd1047be72fbe8c9db6fa3b6d8886d58bf46ab` | `63dcbf9bded8edce9064fc9d27d95a20e06e684e` |
| P01 | candidate review artifact | `submissions/code_mit_2026/author_review/postreview_20260910/inputs/packet_01_received.md` | `f641a3eb244326fa2b45ea462170d6bf1938541a1981f3ddb8029b6a6404f569` | `1f9ef041c0707bceea2510fabe8f4318ac0efe5a` |
| P02 | candidate review artifact | `submissions/code_mit_2026/author_review/postreview_20260910/inputs/packet_02_received.md` | `a901db15a560f032c809e92e4ea3af1f128b9edb4fe722d1bc89ee032745fc05` | `97d89440867083a8d01b5c394ea7f737b9e309d1` |
| C1 | candidate review artifact | `submissions/code_mit_2026/author_review/postreview_20260910/calculate_postreview.py` | `04e7efdf6a5ddfa63d17f90a08ab9b3e69d377ee091f074f40d8cede44c3c3a2` | `a6e4ae35da7eb0d647d27936a2da172aaef76953` |
| C2 | candidate review artifact | `submissions/code_mit_2026/author_review/postreview_20260910/calculations.json` | `4b0d17ce08162eaad168c243c426306e1c024651e0a01bb48e394c352f885841` | `5f5185b0f4c45e5ab0dbcd91fde988f6e53598a9` |

`S0` binds every tracked aggregate part to its byte count and SHA-256. `C1`
reads scientific inputs with `git show REVIEWED:path`, verifies those bindings,
and writes `C2`. The calculator and its output are derivation records, not
independent scientific sources.

Each table row, its keyed source-registry row, and the common units and
aggregation paragraph immediately above that table form one complete claim
record. This avoids repeating a 64-character digest in every row without
dropping it from the record.

## Retained manuscript table cells

All manuscript locators refer to the retained table in `M0`. The current
post-review manuscript keeps the same cells. Each selector is a JSON object
predicate followed by the named field.

### Mean cumulative pseudo-regret, 16 cells

Units are cumulative pseudo-regret at `T=1000`. For every cell, the aggregation
order is: take the terminal cumulative pseudo-regret separately for each primary
trajectory, then take the arithmetic mean across the 50 evaluation seeds. No
bootstrap or cross-condition pooling enters these means.

| ID | Revision and source | Manuscript cell | Selector and field | Unrounded value | Display | Verification | Packet reference |
|---|---|---|---|---:|---:|---|---|
| R01 | `REVIEWED`; S1 | `D=0.25`, Hessian | `horizon=1000,target_D=0.25,method=transport_hessian`; `cumulative_pseudo_regret.mean` | `81.04956086155346` | `81.05` | exact field; decimal display matches | P02:11; P01:352-395 |
| R02 | `REVIEWED`; S1 | `D=0.25`, endpoint | `horizon=1000,target_D=0.25,method=transport_endpoint`; `cumulative_pseudo_regret.mean` | `79.05014331769655` | `79.05` | exact field; decimal display matches | P02:11; P01:352-395 |
| R03 | `REVIEWED`; S1 | `D=0.25`, frozen | `horizon=1000,target_D=0.25,method=frozen_reference`; `cumulative_pseudo_regret.mean` | `79.09451495804345` | `79.09` | exact field; decimal display matches | P02:11; P01:352-395 |
| R04 | `REVIEWED`; S1 | `D=0.25`, naive | `horizon=1000,target_D=0.25,method=naive_current`; `cumulative_pseudo_regret.mean` | `79.00345244889643` | `79.00` | exact field; decimal display matches | P02:11; P01:352-395 |
| R05 | `REVIEWED`; S1 | `D=0.5`, Hessian | `horizon=1000,target_D=0.5,method=transport_hessian`; `cumulative_pseudo_regret.mean` | `82.43554707309166` | `82.44` | exact field; decimal display matches | P02:11; P01:352-395 |
| R06 | `REVIEWED`; S1 | `D=0.5`, endpoint | `horizon=1000,target_D=0.5,method=transport_endpoint`; `cumulative_pseudo_regret.mean` | `79.48956224206864` | `79.49` | exact field; decimal display matches | P02:11; P01:352-395 |
| R07 | `REVIEWED`; S1 | `D=0.5`, frozen | `horizon=1000,target_D=0.5,method=frozen_reference`; `cumulative_pseudo_regret.mean` | `80.12874630744086` | `80.13` | exact field; decimal display matches | P02:11; P01:352-395 |
| R08 | `REVIEWED`; S1 | `D=0.5`, naive | `horizon=1000,target_D=0.5,method=naive_current`; `cumulative_pseudo_regret.mean` | `79.48956224206864` | `79.49` | exact field; decimal display matches | P02:11; P01:352-395 |
| R09 | `REVIEWED`; S1 | `D=1`, Hessian | `horizon=1000,target_D=1.0,method=transport_hessian`; `cumulative_pseudo_regret.mean` | `87.03849658563784` | `87.04` | exact field; decimal display matches | P02:11; P01:352-395 |
| R10 | `REVIEWED`; S1 | `D=1`, endpoint | `horizon=1000,target_D=1.0,method=transport_endpoint`; `cumulative_pseudo_regret.mean` | `80.05844072436543` | `80.06` | exact field; decimal display matches | P02:11; P01:352-395 |
| R11 | `REVIEWED`; S1 | `D=1`, frozen | `horizon=1000,target_D=1.0,method=frozen_reference`; `cumulative_pseudo_regret.mean` | `80.24924933522` | `80.25` | exact field; decimal display matches | P02:11; P01:352-395 |
| R12 | `REVIEWED`; S1 | `D=1`, naive | `horizon=1000,target_D=1.0,method=naive_current`; `cumulative_pseudo_regret.mean` | `80.09746167479669` | `80.10` | exact field; decimal display matches | P02:11; P01:352-395 |
| R13 | `REVIEWED`; S1 | `D=2`, Hessian | `horizon=1000,target_D=2.0,method=transport_hessian`; `cumulative_pseudo_regret.mean` | `93.98889075534275` | `93.99` | exact field; decimal display matches | P02:11; P01:352-395 |
| R14 | `REVIEWED`; S1 | `D=2`, endpoint | `horizon=1000,target_D=2.0,method=transport_endpoint`; `cumulative_pseudo_regret.mean` | `81.89305037555769` | `81.89` | exact field; decimal display matches | P02:11; P01:352-395 |
| R15 | `REVIEWED`; S1 | `D=2`, frozen | `horizon=1000,target_D=2.0,method=frozen_reference`; `cumulative_pseudo_regret.mean` | `81.67068627569212` | `81.67` | exact field; decimal display matches | P02:11; P01:352-395 |
| R16 | `REVIEWED`; S1 | `D=2`, naive | `horizon=1000,target_D=2.0,method=naive_current`; `cumulative_pseudo_regret.mean` | `81.88290235298888` | `81.88` | exact field; decimal display matches | P02:11; P01:352-395 |

### Median path-curvature ratios, 4 cells

Units are dimensionless. For each target, compute `D_Q/D_path_quad` at the 100
every-10-round checkpoints in each of 50 primary trajectories for which
`D_path_quad > 1e-12`; pool the resulting 5,000 ratios; then take the linear
sample median. These are pooled checkpoint summaries, not ratios of medians.

| ID | Revision and source | Manuscript cell | Selector and field | Unrounded value | Display | Verification | Packet reference |
|---|---|---|---|---:|---:|---|---|
| P01-R | `REVIEWED`; S2 | `D=0.25` | `horizon=1000,target_D=0.25`; `D_Q_over_D_path_quad.median` | `1879974.5146315224` | `1.88 × 10^6` | exact field; 3-significant-digit display matches | P01:296-313; P02:11 |
| P02-R | `REVIEWED`; S2 | `D=0.5` | `horizon=1000,target_D=0.5`; `D_Q_over_D_path_quad.median` | `977279.9007821515` | `9.77 × 10^5` | exact field; 3-significant-digit display matches | P01:296-313; P02:11 |
| P03-R | `REVIEWED`; S2 | `D=1` | `horizon=1000,target_D=1.0`; `D_Q_over_D_path_quad.median` | `482181.52554807696` | `4.82 × 10^5` | exact field; 3-significant-digit display matches | P01:296-313; P02:11 |
| P04-R | `REVIEWED`; S2 | `D=2` | `horizon=1000,target_D=2.0`; `D_Q_over_D_path_quad.median` | `251089.28476730903` | `2.51 × 10^5` | exact field; 3-significant-digit display matches | P01:296-313; P02:11 |

### Median endpoint run maxima, 4 cells

Units are dimensionless Thompson distance. For each primary trajectory, take the
maximum endpoint Thompson distance across its 1,000 rounds; then take the median
of the 50 seed-level maxima. These are not pooled round-level medians.

| ID | Revision and source | Manuscript cell | Selector and field | Unrounded value | Display | Verification | Packet reference |
|---|---|---|---|---:|---:|---|---|
| EP01 | `REVIEWED`; S3 | `D=0.25` | `horizon=1000,target_D=0.25`; `max_endpoint_Thompson_distance.median` | `1.30941908229401e-07` | `1.31 × 10^-7` | exact field; 3-significant-digit display matches | P01:296-313; P02:11 |
| EP02 | `REVIEWED`; S3 | `D=0.5` | `horizon=1000,target_D=0.5`; `max_endpoint_Thompson_distance.median` | `5.229555849116956e-07` | `5.23 × 10^-7` | exact field; 3-significant-digit display matches | P01:296-313; P02:11 |
| EP03 | `REVIEWED`; S3 | `D=1` | `horizon=1000,target_D=1.0`; `max_endpoint_Thompson_distance.median` | `2.0954005637393623e-06` | `2.10 × 10^-6` | exact field; 3-significant-digit display matches | P01:296-313; P02:11 |
| EP04 | `REVIEWED`; S3 | `D=2` | `horizon=1000,target_D=2.0`; `max_endpoint_Thompson_distance.median` | `8.739094191260115e-06` | `8.74 × 10^-6` | exact field; 3-significant-digit display matches | P01:296-313; P02:11 |

### Median pooled inflation multipliers, 4 cells

Units are dimensionless multipliers. For each target, pool `exp(D_Q/2)` over all
50 primary seeds and all 1,000 rounds, then take the median of the 50,000 values.
This statistic is not terminal, per-seed, or a median of seed medians.

| ID | Revision and source | Manuscript cell | Selector and field | Unrounded value | Display | Verification | Packet reference |
|---|---|---|---|---:|---:|---|---|
| I01-R | `REVIEWED`; S2 | `D=0.25` | `horizon=1000,target_D=0.25`; `exp_D_Q_over_2.median` | `1.0205263637773605` | `1.02` | exact field; decimal display matches; author approval C01 remains pending | P02:104-115 |
| I02-R | `REVIEWED`; S2 | `D=0.5` | `horizon=1000,target_D=0.5`; `exp_D_Q_over_2.median` | `1.0409388460308655` | `1.04` | exact field; decimal display matches; author approval C01 remains pending | P02:104-115 |
| I03-R | `REVIEWED`; S2 | `D=1` | `horizon=1000,target_D=1.0`; `exp_D_Q_over_2.median` | `1.085454149598788` | `1.09` | exact field; decimal display matches; author approval C01 remains pending | P02:104-115 |
| I04-R | `REVIEWED`; S2 | `D=2` | `horizon=1000,target_D=2.0`; `exp_D_Q_over_2.median` | `1.1785579103036254` | `1.18` | exact field; decimal display matches; author approval C01 remains pending | P02:104-115 |

## Proposed internal Section 6 entries

Material label for B01-B04, HN01-HN04, and W01-W04: **Post-review descriptive analysis of the locked evaluation.** The selectors beginning with `/calculations`
address `C2`; the adjacent source selector identifies the locked input row.

### B0 decomposition and derived ratios, 4 rows

Units for `S`, `H`, `I`, `C`, `B_D`, and `B_0` are cumulative bound units at
`T=1000`. `I/B_0`, `I/B_D`, `B_0/(2T)`, and `B_0/mean_regret` are dimensionless;
the first two are displayed as percentages. Stored decomposition fields are
means over 50 primary trajectories after the nonlinear bound is evaluated on
each trajectory. Derive `B_0 = B_D - I = S + H + C` from those stored means;
then form each reported ratio from aggregate means. The ratios are not means of
seed-level ratios and do not attribute causal regret.

| ID | Revision and sources | Locked source selector; C2 selector | Unrounded values | Proposed display | Verification | Packet reference |
|---|---|---|---|---|---|---|
| B01 | `REVIEWED`; S4, C1, C2 | `horizon=1000,target_D=0.25,round=1000` (`S4 line 1000`); `/calculations/terminal_mean_decomposition_t1000/by_target_D/0.25` | `S=9948.391361206572`; `H=66.05459519427838`; `I=205.38908832279935`; `C=1.9367067527638477`; `B_D=10221.771751476412`; `B_0=10016.382663153612`; `I/B_0=2.050531566434133%`; `I/B_D=2.009329628135488%`; `B_0/(2T)=5.008191331576806`; `B_0/mean_regret=123.58342915963865` | `9948.39, 66.05, 205.39, 1.94, 10221.77, 10016.38, 2.05%, 2.01%, 5.0082, 123.5834` | identities and `B_0` equality pass; calculator result matches packet; E01 inclusion pending | P01:352-395; P02:25-100,201-215 |
| B02 | `REVIEWED`; S4, C1, C2 | `horizon=1000,target_D=0.5,round=1000` (`S4 line 2000`); `/calculations/terminal_mean_decomposition_t1000/by_target_D/0.5` | `S=9957.147286491123`; `H=132.67635729272513`; `I=425.15876066935584`; `C=3.8933116078600483`; `B_D=10518.875716061064`; `B_0=10093.716955391708`; `I/B_0=4.212112966395898%`; `I/B_D=4.0418650447612885%`; `B_0/(2T)=5.046858477695854`; `B_0/mean_regret=122.443743188143` | `9957.15, 132.68, 425.16, 3.89, 10518.88, 10093.72, 4.21%, 4.04%, 5.0469, 122.4437` | identities and `B_0` equality pass; calculator result matches packet; E01 inclusion pending | P01:352-395; P02:25-100,201-215 |
| B03 | `REVIEWED`; S5, C1, C2 | `horizon=1000,target_D=1.0,round=1000` (`S5 line 608`); `/calculations/terminal_mean_decomposition_t1000/by_target_D/1` | `S=9979.499569487705`; `H=265.23925932188837`; `I=911.4669289154597`; `C=7.760095416530552`; `B_D=11163.965853141588`; `B_0=10252.498924226129`; `I/B_0=8.890192875433623%`; `I/B_D=8.164365073357592%`; `B_0/(2T)=5.126249462113065`; `B_0/mean_regret=117.79269319224301` | `9979.50, 265.24, 911.47, 7.76, 11163.97, 10252.50, 8.89%, 8.16%, 5.1262, 117.7927` | identities and `B_0` equality pass; calculator result matches packet; E01 inclusion pending | P01:352-395; P02:25-100,201-215 |
| B04 | `REVIEWED`; S5, C1, C2 | `horizon=1000,target_D=2.0,round=1000` (`S5 line 1608`); `/calculations/terminal_mean_decomposition_t1000/by_target_D/2` | `S=10009.834477049892`; `H=530.9353493748229`; `I=2051.7384427760844`; `C=15.473126415086492`; `B_D=12607.981395615883`; `B_0=10556.242952839799`; `I/B_0=19.43625636452535%`; `I/B_D=16.273330189791732%`; `B_0/(2T)=5.2781214764199`; `B_0/mean_regret=112.31373056969217` | `10009.83, 530.94, 2051.74, 15.47, 12607.98, 10556.24, 19.44%, 16.27%, 5.2781, 112.3137` | identities and `B_0` equality pass; calculator result matches packet; E01 inclusion pending | P01:352-395; P02:25-100,201-215 |

Here `I/B_0` is the path uplift relative to the no-path bound and `I/B_D` is
the path component's share of the reported bound. `B_0/(2T)` is a scale check
against the deterministic `2T` regret cap. `B_0/mean_regret` compares two means;
it is not a seedwise statistic or a coverage statement.

### Paired Hessian-minus-naive statistics, 4 rows

Regret quantities and their standard deviation and standard error use cumulative
pseudo-regret units at `T=1000`; relative excess is dimensionless and displayed
as a percentage. Match Hessian and naive outcomes by the same 50 evaluation seed
IDs, compute `Hessian - naive` per seed, then take its mean and sample standard
deviation; `SE = SD/sqrt(50)`. The stored aggregate comparison uses
`naive - Hessian`, so the calculator negates the mean and reverses and negates
the interval endpoints. The comparisonwise paired-bootstrap interval is reused,
not replayed. No simultaneous or significance claim is made.

| ID | Revision and sources | Locked source selector; C2 selector | Unrounded values | Proposed display | Verification | Packet reference |
|---|---|---|---|---|---|---|
| HN01 | `REVIEWED`; S1, C1, C2 | `S1 lines=1,4`; `/calculations/paired_hessian_minus_naive_t1000/by_target_D/0.25` | `mean_H=81.04956086155346`; `mean_N=79.00345244889643`; `H-N=2.0461084126570315`; `SD=5.312015140750025`; `SE=0.751232385557991`; `95% CI=[0.5841057013488111,3.511933768875755]`; `relative_excess=2.58989746553236%` | `81.05, 79.00, 2.05, 5.312015, 0.751232, [0.584106, 3.511934], 2.59%` | 50-seed pairing, sign reversal, interval order, and SE check pass; paired SE inclusion pending | P02:142-187,216-220 |
| HN02 | `REVIEWED`; S1, C1, C2 | `S1 lines=5,8`; `/calculations/paired_hessian_minus_naive_t1000/by_target_D/0.5` | `mean_H=82.43554707309166`; `mean_N=79.48956224206864`; `H-N=2.945984831023014`; `SD=4.681694036627014`; `SE=0.6620915201479164`; `95% CI=[1.676612459409258,4.207852282222003]`; `relative_excess=3.7061278838744145%` | `82.44, 79.49, 2.95, 4.681694, 0.662092, [1.676612, 4.207852], 3.71%` | 50-seed pairing, sign reversal, interval order, and SE check pass; paired SE inclusion pending | P02:142-187,216-220 |
| HN03 | `REVIEWED`; S1, C1, C2 | `S1 lines=9,12`; `/calculations/paired_hessian_minus_naive_t1000/by_target_D/1` | `mean_H=87.03849658563784`; `mean_N=80.09746167479669`; `H-N=6.941034910841148`; `SD=4.654294462001184`; `SE=0.6582166351440062`; `95% CI=[5.680469619725013,8.235519009728673]`; `relative_excess=8.665736423736385%` | `87.04, 80.10, 6.94, 4.654294, 0.658217, [5.680470, 8.235519], 8.67%` | 50-seed pairing, sign reversal, interval order, and SE check pass; paired SE inclusion pending | P02:142-187,216-220 |
| HN04 | `REVIEWED`; S1, C1, C2 | `S1 lines=13,16`; `/calculations/paired_hessian_minus_naive_t1000/by_target_D/2` | `mean_H=93.98889075534275`; `mean_N=81.88290235298888`; `H-N=12.105988402353873`; `SD=5.7668863179995205`; `SE=0.8155608843578763`; `95% CI=[10.506209898311521,13.701437775604242]`; `relative_excess=14.784513072297054%` | `93.99, 81.88, 12.11, 5.766886, 0.815561, [10.506210, 13.701438], 14.78%` | 50-seed pairing, sign reversal, interval order, and SE check pass; paired SE inclusion pending | P02:142-187,216-220 |

### Analytic near-linearity values, 4 rows

`W` is the dimensionless design scale from the locked configuration. The bound
`1/(3W)` is a dimensionless relative inflation. There is no empirical
aggregation: substitute `T=1000` and each configured target `D` into the locked
design rule, obtaining `W = 151552/D^2`, then evaluate the exact rational
`1/(3W)`. Decimal values are binary64 presentations of exact fractions, not
claims of floating-point exactness.

| ID | Revision and sources | Locked source selector; C2 selector | Unrounded/exact values | Proposed display | Verification | Packet reference |
|---|---|---|---|---|---|---|
| W01 | `REVIEWED`; S6, C1, C2 | `/base/model/W_rule`, `/base/horizons`, `/base/target_D`; `/calculations/analytic_near_linearity_t1000/by_target_D/0.25` | `W=2424832`; `W_exact=2424832/1`; `1/(3W)=1/7274496`; `float64=1.3746656813063063e-07` | `2,424,832`; `1.3746656813 × 10^-7` | exact rational identity and configured-design substitution pass; manuscript endpoint rounds to `1.375 × 10^-7` | P01:189-246 |
| W02 | `REVIEWED`; S6, C1, C2 | `/base/model/W_rule`, `/base/horizons`, `/base/target_D`; `/calculations/analytic_near_linearity_t1000/by_target_D/0.5` | `W=606208`; `W_exact=606208/1`; `1/(3W)=1/1818624`; `float64=5.498662725225225e-07` | `606,208`; `5.4986627252 × 10^-7` | exact rational identity and configured-design substitution pass | P01:189-246 |
| W03 | `REVIEWED`; S6, C1, C2 | `/base/model/W_rule`, `/base/horizons`, `/base/target_D`; `/calculations/analytic_near_linearity_t1000/by_target_D/1` | `W=151552`; `W_exact=151552/1`; `1/(3W)=1/454656`; `float64=2.19946509009009e-06` | `151,552`; `2.1994650901 × 10^-6` | exact rational identity and configured-design substitution pass | P01:189-246 |
| W04 | `REVIEWED`; S6, C1, C2 | `/base/model/W_rule`, `/base/horizons`, `/base/target_D`; `/calculations/analytic_near_linearity_t1000/by_target_D/2` | `W=37888`; `W_exact=37888/1`; `1/(3W)=1/113664`; `float64=8.79786036036036e-06` | `37,888`; `8.7978603604 × 10^-6` | exact rational identity and configured-design substitution pass; manuscript endpoint rounds to `8.798 × 10^-6` | P01:189-246 |

## Pending and excluded material

- **E01 is author-inclusion pending.** The B0 decomposition and its derived
  ratios are verified internal records, but this ledger does not authorize their
  addition to the manuscript.
- **Paired SE is author-inclusion pending.** The four SE values pass
  `SD/sqrt(50)` checks, but this ledger does not authorize manuscript inclusion.
- **Terminal quantiles are excluded.** No per-seed terminal
  `exp(D_Q(T)/2)` quartile, median, or terminal-range value is a claim record in
  this ledger. The retained inflation cells are the pooled 50,000-round medians
  documented above. See P02:104-140.
- The B0 rows are algebraic decompositions of locked aggregate means, not
  counterfactual reruns with the path term removed.
- The paired intervals are existing comparisonwise bootstrap intervals after a
  sign transform. The bootstrap was not replayed, and the ledger makes no
  multiple-comparison or confirmatory-inference claim.
