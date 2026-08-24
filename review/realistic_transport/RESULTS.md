# Realistic confidence-transport benchmark results

Profile: `smoke`

Accepted cells: 39 / 39

Raw-input inventory SHA-256: `2de4bcb43bb10aec4cc9d7d4a16966696e5cb028dd954eddcb3f9a5c96705e81`

This result is not publication evidence. It uses a smoke or pilot profile and cannot answer the preregistered Covertype acceptance question.

| Task | Method | n | Mean regret | SE | Coverage | Optimism | Algorithm s | Peak MiB |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| covtype_label_bandit | frozen_reference_corrected_cholesky | 1 | 24.8 | 0 | 1.000 | 1.000 | 1.28 | 453.70 |
| covtype_label_bandit | greedy_corrected | 1 | 22.4 | 0 | 1.000 | 0.000 | 0.7851 | 406.38 |
| covtype_label_bandit | linucb_fixed_features | 1 | 20.8 | 0 | 0.000 | 0.000 | 0.9336 | 412.14 |
| covtype_label_bandit | naive_current_corrected_cholesky | 1 | 23.2 | 0 | 1.000 | 1.000 | 1.756 | 448.02 |
| covtype_label_bandit | transport_endpoint_corrected_cholesky | 1 | 23.2 | 0 | 1.000 | 1.000 | 2.074 | 456.77 |
| covtype_label_bandit | transport_exact_corrected_cg_1e-4 | 1 | 23.2 | 0 | 1.000 | 1.000 | 1.634 | 436.18 |
| covtype_label_bandit | transport_exact_corrected_cholesky | 1 | 23.2 | 0 | 1.000 | 1.000 | 1.747 | 421.54 |
| covtype_label_bandit | transport_exact_uncorrected_tangent_cholesky | 1 | 23.2 | 0 | 1.000 | 1.000 | 1.774 | 408.72 |
| covtype_label_bandit | transport_nystrom_r16_cg_1e-2 | 1 | 22.4 | 0 | 1.000 | 1.000 | 1.128 | 406.91 |
| covtype_label_bandit | transport_nystrom_r16_cg_1e-6 | 1 | 22.4 | 0 | 1.000 | 1.000 | 1.301 | 416.99 |
| covtype_label_bandit | transport_nystrom_r32_cg_1e-4 | 1 | 24.8 | 0 | 1.000 | 1.000 | 1.231 | 431.61 |
| covtype_label_bandit | transport_nystrom_r64_cg_1e-2 | 1 | 24 | 0 | 1.000 | 1.000 | 1.15 | 441.79 |
| covtype_label_bandit | transport_nystrom_r64_cg_1e-6 | 1 | 24 | 0 | 1.000 | 1.000 | 1.276 | 437.44 |
| covtype_semisynthetic_misspecified | frozen_reference_corrected_cholesky | 1 | 3.26861 | 0 | 1.000 | 1.000 | 1.254 | 426.20 |
| covtype_semisynthetic_misspecified | greedy_corrected | 1 | 3.18672 | 0 | 1.000 | 0.000 | 0.7622 | 424.73 |
| covtype_semisynthetic_misspecified | linucb_fixed_features | 1 | 3.33307 | 0 | 1.000 | 1.000 | 0.9408 | 430.52 |
| covtype_semisynthetic_misspecified | naive_current_corrected_cholesky | 1 | 2.89307 | 0 | 1.000 | 1.000 | 1.691 | 433.73 |
| covtype_semisynthetic_misspecified | transport_endpoint_corrected_cholesky | 1 | 3.13921 | 0 | 1.000 | 1.000 | 2.024 | 488.98 |
| covtype_semisynthetic_misspecified | transport_exact_corrected_cg_1e-4 | 1 | 2.94338 | 0 | 1.000 | 1.000 | 1.732 | 442.84 |
| covtype_semisynthetic_misspecified | transport_exact_corrected_cholesky | 1 | 3.13921 | 0 | 1.000 | 1.000 | 1.709 | 535.19 |
| covtype_semisynthetic_misspecified | transport_exact_uncorrected_tangent_cholesky | 1 | 3.13921 | 0 | 1.000 | 1.000 | 1.631 | 429.68 |
| covtype_semisynthetic_misspecified | transport_nystrom_r16_cg_1e-2 | 1 | 2.95093 | 0 | 1.000 | 1.000 | 1.242 | 436.29 |
| covtype_semisynthetic_misspecified | transport_nystrom_r16_cg_1e-6 | 1 | 3.23157 | 0 | 1.000 | 1.000 | 1.25 | 440.97 |
| covtype_semisynthetic_misspecified | transport_nystrom_r32_cg_1e-4 | 1 | 3.25218 | 0 | 1.000 | 1.000 | 1.287 | 465.25 |
| covtype_semisynthetic_misspecified | transport_nystrom_r64_cg_1e-2 | 1 | 3.32547 | 0 | 1.000 | 1.000 | 1.211 | 457.35 |
| covtype_semisynthetic_misspecified | transport_nystrom_r64_cg_1e-6 | 1 | 3.43357 | 0 | 1.000 | 1.000 | 1.399 | 447.14 |
| covtype_semisynthetic_realizable | frozen_reference_corrected_cholesky | 1 | 2.8643 | 0 | 1.000 | 1.000 | 1.273 | 445.20 |
| covtype_semisynthetic_realizable | greedy_corrected | 1 | 3.12182 | 0 | 1.000 | 0.000 | 0.7614 | 417.24 |
| covtype_semisynthetic_realizable | linucb_fixed_features | 1 | 3.31364 | 0 | 1.000 | 1.000 | 1.02 | 426.05 |
| covtype_semisynthetic_realizable | naive_current_corrected_cholesky | 1 | 2.99269 | 0 | 1.000 | 1.000 | 1.709 | 436.28 |
| covtype_semisynthetic_realizable | transport_endpoint_corrected_cholesky | 1 | 3.12703 | 0 | 1.000 | 1.000 | 2.087 | 474.56 |
| covtype_semisynthetic_realizable | transport_exact_corrected_cg_1e-4 | 1 | 3.19298 | 0 | 1.000 | 1.000 | 1.701 | 452.37 |
| covtype_semisynthetic_realizable | transport_exact_corrected_cholesky | 1 | 3.11038 | 0 | 1.000 | 1.000 | 1.813 | 490.70 |
| covtype_semisynthetic_realizable | transport_exact_uncorrected_tangent_cholesky | 1 | 3.10263 | 0 | 1.000 | 1.000 | 1.752 | 427.34 |
| covtype_semisynthetic_realizable | transport_nystrom_r16_cg_1e-2 | 1 | 3.2395 | 0 | 1.000 | 1.000 | 1.199 | 426.08 |
| covtype_semisynthetic_realizable | transport_nystrom_r16_cg_1e-6 | 1 | 2.93741 | 0 | 1.000 | 1.000 | 1.278 | 424.24 |
| covtype_semisynthetic_realizable | transport_nystrom_r32_cg_1e-4 | 1 | 3.08058 | 0 | 1.000 | 1.000 | 1.409 | 455.05 |
| covtype_semisynthetic_realizable | transport_nystrom_r64_cg_1e-2 | 1 | 3.24212 | 0 | 1.000 | 1.000 | 1.173 | 450.04 |
| covtype_semisynthetic_realizable | transport_nystrom_r64_cg_1e-6 | 1 | 3.15957 | 0 | 1.000 | 1.000 | 1.414 | 436.55 |

Float64 residual and Loewner checks are exact-arithmetic certificate diagnostics, not verified numerical certificates.
