# Development plan (written before any development run)

Date: 2026-11-21. This file fixes what development may change and how the
secondary configuration is selected. The evaluation protocol is written after
development, in `PROTOCOL.md`, and hashed before any evaluation seed runs.

## Primary study (scalar scaled tanh, delayed update)

- Candidate P1 is the specified configuration: W = 6.25, R = 1, lambda = 1,
  sigma = 0.25, theta_star = -R, delta = 0.05, block n = 8192, horizon
  T = n + 1, frozen-reference behavior policy with the corrected center, new
  certified-envelope variant (`sharp_envelope`) for the primary comparison and
  the manuscript's envelope as a separately labeled comparison on the same
  histories.
- Development seeds: 50000-50015 (16 seeds), plus the deterministic
  mean-reward sanity run.
- P1 is kept unless development shows a crash, a failed internal check, or no
  naive-current failure on any development seed. Only then may further
  configurations be tried (valid model parameters, block length,
  initialization or predictable schedules), at most 12 configurations in total
  across both studies, each preserved with its result.

## Secondary study (six-dimensional model of `experiments/transport_v3.py`)

- Fixed: d = 6, K = 3, teacher seed 1729, sigma = 0.25, lambda = 1, R = 1,
  delta = 0.05, T = 20,000, optimizer learning rate 3e-6 with 5 steps per
  round (the selection recorded in `review/v3_results/tuning_selection.json`),
  corrected center, new certified-envelope variant in beta_t and b_t(a).
  Policies: frozen reference, naive current, endpoint transport, each on its
  own history; context and potential-outcome streams shared within a seed.
- Candidate widths S1-S3: W in {1, 10, 100}. Development seeds 51000-51015.
- Selection rule: choose the smallest candidate W at which, on every
  development seed, the frozen-reference policy's own-history
  determinant-potential bound (Proposition "Frozen-width UCB on its own
  trajectory") is below the regret cap 2T min(1, sqrt W), and no development
  run at that W crashed or failed a replay check. If no candidate qualifies,
  use W = T = 20,000 (S4, the manuscript's design cell). The rule uses no
  regret difference between policies and no coverage outcome.

## Seeds

Fresh ranges, disjoint from every range recorded in the repository
(20000-20201, 30000-30249, 41000-41009, 41100-41109, 41200-41249):
primary development 50000-50015, primary evaluation 50100-50355 (256);
secondary development 51000-51015, secondary evaluation 51100-51163 (64).
Seeds 50990-50999 and 51990-51999 are used only by unit tests.

## Budget

At most four worker processes, one BLAS thread each, eight CPU core-hours in
total, measured from per-run runtimes.
