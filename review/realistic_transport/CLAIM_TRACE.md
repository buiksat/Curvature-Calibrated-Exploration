# Realistic transport equation-to-code trace

This trace binds the paper equations to the implementation that was exercised
by the smoke gate. Line numbers refer to the freeze candidate before the local
freeze commit.

| Object | Paper source | Planned implementation and audit |
|---|---|---|
| Frozen metric | `paper/transport_theory.tex`, reference update and three-width definitions | `benchmark.py:300-437` stores collection queries and updates `Vbar` by the selected rank-one term. |
| Exact current replay metric | Scalar factor path and Hessian certificate in `paper/transport_theory.tex` | `benchmark.py:394-400,1207-1245` replays selected features at current `theta`; dense construction is used by exact methods and checkpoint diagnostics. |
| Pseudo-response | `eq:pseudo-response-new` | `benchmark.py:1469-1492` stores `r-mu_theta+q.T@theta` and audits the controlled-task identity. |
| Frozen linearized estimator | `eq:frozen-ridge-new` | `benchmark.py:356-359` solves `Vbar theta_hat = sigma^-2 sum q*y`. |
| Corrected center | `eq:corrected-center-new` | `benchmark.py:514-534` implements the formula; `benchmark.py:1426-1456` audits its identity. |
| Historical Taylor envelope | `eq:lin-mis-envelopes-new` and scaled-tanh Hessian bound | `benchmark.py:488-512,1484-1492` uses `0.5*L_mu*(1+||theta_s||)^2`, never the realized remainder. |
| Current Taylor envelope | Same source | `benchmark.py:1180-1185` computes the same global pre-reward formula at `theta_t`. |
| Historical/current misspecification | Approximate-realizability and envelope definitions | Task C uses uniform `rho`; Task B uses zero; Task A uses a declared zero heuristic and records theorem inapplicability. |
| Corrected confidence radius | `eq:beta-corrected-new` | `benchmark.py:557-585` enforces sum-before-square and the outer `1/sigma`; `SelectedHistory` exposes the component diagnostics. |
| `Q_t` and Hessian certificate | `eq:Qt-new`, `eq:hessian-path-sandwich-new` | `benchmark.py:360-391,628-640` maintains Welford scatter and computes `2*L_g*sqrt(Q)/(sigma*sqrt(lambda))`. |
| Endpoint Thompson distance | Thompson-distance remark | `operators.py:1624-1645` implements the dense generalized eigensolve; `benchmark.py:1253-1299` confines it to the oracle score or frozen checkpoints. |
| Two-sided operator factors | `eq:operator-sandwich-new` | `operators.py:481-713` constructs the low-rank operator without dense `H`; `kappa_plus=1` and `kappa_minus=lambda/(lambda+trace_tail)`. Dense Loewner checks are checkpoint-only. |
| Solver upper-width map | `eq:solver-interface-new` | `operators.py:1327-1530` uses immutable operators, recomputed residuals, and the exact-arithmetic `n+e` upper width for every action. |
| Played-action sharpness | Same interface | `operators.py:1452-1530` returns one immutable all-action map; `benchmark.py:1578-1582` reads the selected factor without refinement. |
| Score and tie-breaking | `eq:transported-score-new`, finite enumeration corollary | `benchmark.py:648-657,1306-1319` enumerates actions, uses exact maxima, and takes the smallest tied index. |
| Regret bounds and empirical metrics | `eq:instantaneous-transport-new`, sharp/simple cumulative bounds | `benchmark.py:916-974,1536-1775` accumulates the frozen potential, sharp RHS, bias, coverage, optimism, nonvacuity, regret, timing, memory, CG, and operator diagnostics. `aggregate.py` treats seeds as the independent units. |

Float64 checks are recorded as numerical audits. They are not called verified
numerical certificates because `paper/transport_proofs.tex` requires an
enclosed residual or equivalent verified-numerics argument for that claim.
