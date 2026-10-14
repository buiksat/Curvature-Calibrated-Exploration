# Exploratory relative-weight endpoint audit

This is a post-outcome analysis of the existing full follow-up study, not a new
adaptive experiment or a prespecified evaluation of a new policy. The source
study has 600 evaluation histories: 50 seeds for each of four behavior policies
and W = 16, 1, 0.25, each with 1,000 rounds. Existing behavior actions and selected
rewards remain fixed throughout the audit. See the full study's
[results](../transport_review_followup/FULL_RESULTS.md) and the independent
[endpoint derivation](../post_full_fable/independent/relative_certificate.md).

## Reproduction and files

From the repository root, using the study's pinned Python environment:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /workspace/cce-research-env/bin/python tools/analyze_relative_transport.py --self-test
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /workspace/cce-research-env/bin/python tools/analyze_relative_transport.py \
  --raw-root /workspace/cce-full-local --workers 4 \
  --output-dir /tmp/cce-relative-reproduction
cd review/transport_relative_diagnostics/full
sha256sum -c ARTIFACTS.sha256
```

The raw root can point to a transferred complete raw archive. A reproduction
output directory must be new. Kernel timings and elapsed times vary between
runs; scientific counts and summary statistics are the relevant reproducibility
targets. Checking `ARTIFACTS.sha256` only verifies transferred output bytes; it
does not independently replay the raw data.

- [analysis.json](full/analysis.json): provenance, aggregate diagnostics and
  variation across the 50 seed fractions in each cell.
- [per_seed.jsonl](full/per_seed.jsonl): one compact record per behavior/W/seed,
  with counts, widths, recommendations, consistency checks and fixed-state
  timing measurements.
- [input_inventory.jsonl](full/input_inventory.jsonl): SHA-256 and byte count
  for every consumed raw log, summary, receipt and supporting input.
- [analyzer](../../tools/analyze_relative_transport.py): standalone driver;
  imports the original scientific implementation without modifying it.

## Pre-action reconstruction and checks

The raw records contain parameter norms rather than parameter vectors. The
audit starts from the original zero vector and replays the unchanged
representation optimizer using only the logged action and logged selected
reward. It uses the recorded optimizer, including its 20 gradient steps and
single projection at the end of each round. This is an optimizer replay on
fixed observed data; it does not simulate alternative actions or rewards.
The original source hash, Python build, NumPy/SciPy versions, configuration,
selection hash, task receipts and single-thread worker settings are checked.

Before action t, category c has count N_c and collection weight
F_c = sum over s<t in c of a(theta_s,c)^2, where
a(theta,c) = sech²(phi_c' theta / sqrt(W)). The current weight is
G_c = N_c a(theta_t,c)^2. The current round's query/weight is appended only
after all diagnostics for the pre-action state, then its reward enters the
original update. Squaring the sum of the multipliers would be incorrect.

Every round checks recorded pre-/post-update norms, update displacement,
projection indicator, pseudo-response, logged behavior selection and the
width/endpoint inequalities. At the fixed rounds 1, 2, 10, 100, 500 and 1,000
of every trajectory, it independently rebuilds the frozen Gram using grouped
category weights and compares it with direct per-observation rank-one updates.
It also recomputes current/frozen widths, corrected centers and endpoint
generalized eigenvalues, and checks both category PSD sandwiches. All these
checks use the original algebra tolerance, including its operator-norm scale;
there is no tolerance increase or silent clipping. The four synthetic
`--self-test` cases compare literal per-sample Grams with grouped ones and cover
the empty prefix. These are numerical consistency tests, not proof validation.

## Certificates and diagnostic definitions

With ratios r_c = G_c/F_c for observed categories, set
m = min(1, min r_c), M = max(1, max r_c). For an empty prefix use m=M=1.
Including 1 preserves the unchanged positive ridge. Exact arithmetic gives
m V_frozen <= V_current <= M V_frozen in PSD order. The symmetric certificate
is D_cat = max(-log m, log M). The uniform certificate is
D_uniform = 4 log cosh(BR/sqrt(W)), using the declared B=R=1.

Seven score rules are evaluated symmetrically on each of the four behavior
histories. They share the saved corrected center, confidence radius and bias.
The existing four are Hessian/Q, dense endpoint, frozen and naive current.
The added conditional scores multiply the current width by exp(D_uniform/2),
exp(D_cat/2), or sqrt(M). The last uses the sharper asymmetric endpoint
comparison. This endpoint certificate is not a bound on the length of the
recorded synthetic interpolation path. Its use requires the endpoint
corollary, not relabeling the saved path certificate.

Width overhead is effective bonus width / direct frozen width for every
candidate action. Per-seed statistics use 5,000 action/round ratios, then cell
statistics summarize the 50 seed means. Valid conversions cover the frozen
width on the same state. Naive current width is included as a diagnostic and
need not do so. No ordering is assumed between the asymmetric category width
and the symmetric dense endpoint width.

The width-argmax fraction compares the score recommendation with the smallest
index maximizing the *unscaled* current width (frozen width for the frozen
rule). The sufficient-dominance fraction counts rounds when
B_t (largest width - second largest width) exceeds the full range of corrected
centers, where B_t is the rule's rounded scalar exploration coefficient.
It is a sufficient one-step ranking condition, not a causal decomposition of
cumulative regret. Widths themselves depend on context and adaptive history.

The action-constant bias cancels in real-arithmetic rankings but is retained
in float score calculations to match implementation. All ties use the first
maximum index. Exact float ties and changes under normalized float scoring
are reported. This audit performs no high-precision replay. The earlier
[stored-input arithmetic analysis](../post_full_fable/independent/README.md)
used exact Decimal representations of stored doubles, including an already
rounded beta-times-inflation coefficient; it was not exact arithmetic for
upstream parameters, matrix solves or exponentials. Tiny early ranking changes
can affect future adaptive histories, so they cannot simply be dismissed.

All alternate recommendations are conditional one-step diagnostics. Averaging
their one-step regrets over saved histories does not estimate their adaptive
cumulative regret. The data were already observed when these diagnostics were
chosen; no fresh test set or multiplicity-adjusted inference is claimed.

## Cost comparison and research decision

Timing uses seed 30200, rounds 100/500/1,000, in each of the 12 cells, with five
batches of repeated calls. Category timings distinguish precomputed current
multipliers from recomputing all 80 projections. Dense endpoint timing receives
both metrics already assembled and includes the original symmetric generalized
eigensolve and its validation. Timings occur under parallel audit load. They
measure these fixed-state kernels only, excluding metric assembly, estimator
construction, learning, storage and all other policy costs. No measured kernel
ratio establishes an end-to-end speedup.

The new certificate exploits fixed feature directions and positive scalar
reweighting. It removes excess conversion overhead; it does not create a
narrower interval than the already available frozen interval on that same
state. A computational follow-up would need a concrete setting where frozen
width evaluation is costly, together with a full cost accounting that includes
the frozen estimator required by the corrected center. Arbitrary factor
clipping is not licensed by this proof. Intersections require additional valid
information; taking the minimum of the frozen width and its valid transported
upper bound simply returns the frozen width.

Final numeric results and the go/no-go decision are recorded separately in
[RESULTS.md](RESULTS.md) after the complete audit has passed. No fresh adaptive
experiment is launched by this analysis.
