# Reproducible independent post-full log analysis

This is an **exploratory analysis of already observed outcomes**, prepared before consulting the Fable review. No policy, optimizer, numerical solver, simulator, or new experiment was executed. The analysis left the scientific source and evaluation artifacts unchanged. The primary-only counts previously reported were reproduced exactly; there are no corrected primary counts.

`analysis.json` is the authoritative machine-generated result of `symmetric_scan.py`. It covers **600 trajectories and 600,000 rounds**: three W values, four behavior policies, 50 evaluation seeds per policy/W cell, and T=1000. Each of the 12 groups has 50,000 dependent rounds. The scan took 61.40767949399924 seconds. `input_inventory.jsonl` records **3,004 input hashes**: five files per trajectory (raw, manifest, summary, summary hash sidecar, completion receipt), the run/source/execution documents, and the scientific implementation. Raw trajectories total 3,715,685,774 bytes. All task receipts, raw hashes, config identities, method/seed coverage and actual selected-action/score consistency were checked.

Inputs remain under `/workspace/cce-full-local`; recorded scientific revision is `707c8243ea6d5395369ed812a68cf7e27d700596`. The source implementation hash is `68a93c4d774012338cb0a75f587a682721dd5548031b7d8dade85110cd0ef2a4`. The historical `KeyboardInterrupt` text is retained as metadata; the current run status is complete. This folder does not contain the full raw trajectories.

Definitions and source references:

- On each fixed logged state, Hessian scores are `c[a] + B*w[a] + b`, with `B=float(beta*logged_inflation)` and action-independent bias b. Score definitions and first-index selection: `experiments/transport_instantiation.py:1588–1605`; corrected centers: lines 207–231 and 1539–1568; logged inputs: lines 1974–2015.
- Every argmax chooses the smallest action index among exactly tied maxima. The report counts both first-index disagreement and membership outside the high-precision argmax set. It reports tied widths/scores, including initial ties, and separate post-first-round counts. Diagnostic count names inherited from the original scan (including `selected_not_exact_argmax_set`) refer to the **Hessian recommendation on the row's logged state**, which is the actually played action only for Hessian behavior rows.
- The sufficient width-dominance condition is `B*(w_largest-w_second)>max(c)-min(c)`. Both ordinary-float and Decimal evaluations are reported and agreed in every group. It is a same-state ranking statement, not a causal decomposition of adaptive regret.
- High-precision scores use `Decimal.from_float` on stored c, w, b, and the already float-rounded B, with precision 250. Both Decimal `Inexact` and `Rounded` flags were zero for all 600,000 final-score calculations. Thus these calculations were exact for these stored inputs and rounded B. They do **not** recover exact upstream states, matrix solves, exponentials, or the unrounded product beta*inflation. They are not an exact-arithmetic trajectory rerun or a verified numerical certificate.
- “All centers absorbed” means the stored Hessian score vector equals `B*w+b` componentwise. Zero centers at the first round are included; post-first-round counts are separately available. This equality does not by itself establish that an action ranking was corrupted.
- Confidence-radius ratios use the ordinary median over all 50,000 dependent rounds, including 50 initial zero historical/statistical ratios. Means below use ordinary sequential summation of logged one-step pseudo-regrets; tiny differences from separately summed trajectory means are floating-point summation effects.

On the 150 primary trajectories, width-argmax agreement is **49,691 / 49,981 / 49,991** out of 50,000 rounds at W=16/1/0.25. The strict sufficient condition holds **48,552 / 49,686 / 49,754** times. There are **5 / 5 / 6** stored-input high-precision ranking differences, all during rounds 2–10 and below 0.629 score ULP. All four behavior-history groups combined have 65 such differences out of 600,000 rows, also confined to rounds 2–10. No nonfinite Hessian score/coefficient, zero width, or score-reconstruction mismatch was observed. Rare early action differences can propagate into later histories; their adaptive impact was not tested.

The following table evaluates every score on **each behavior policy's own saved states**, making the comparison symmetric. Each entry is mean one-step pseudo-regret over 50,000 rounds. The diagonal corresponds to that behavior policy's realized mean terminal regret divided by 1000, up to summation rounding. **Off-diagonal entries are conditional recommendations, not counterfactual cumulative regrets of alternative adaptive policies.** No alternative action changes subsequent history in this analysis. Pairwise recommendation-disagreement counts are also preserved in `analysis.json`.

| W | Logged behavior history | Hessian recommendation | Endpoint recommendation | Frozen recommendation | Naive recommendation |
|---:|---|---:|---:|---:|---:|
| 16.0 | Hessian | 0.185101 | 0.029032 | 0.029066 | 0.029027 |
| 16.0 | Endpoint | 0.336227 | 0.152593 | 0.152155 | 0.151549 |
| 16.0 | Frozen | 0.337046 | 0.152483 | 0.151785 | 0.151323 |
| 16.0 | Naive | 0.336677 | 0.153759 | 0.153626 | 0.152746 |
| 1.0 | Hessian | 0.182900 | 0.049506 | 0.059206 | 0.048660 |
| 1.0 | Endpoint | 0.309781 | 0.173187 | 0.173884 | 0.167143 |
| 1.0 | Frozen | 0.311620 | 0.174602 | 0.173195 | 0.169051 |
| 1.0 | Naive | 0.310986 | 0.179028 | 0.177323 | 0.173052 |
| 0.25 | Hessian | 0.176439 | 0.101773 | 0.144606 | 0.097656 |
| 0.25 | Endpoint | 0.243915 | 0.172089 | 0.170811 | 0.164566 |
| 0.25 | Frozen | 0.232988 | 0.175617 | 0.171876 | 0.169862 |
| 0.25 | Naive | 0.249712 | 0.180425 | 0.174521 | 0.172584 |

The original primary-only scripts and the `primary_original_*` transcription/note are preserved for traceability. The authoritative symmetric results supersede any rounded prose descriptions, while reproducing the original integer counts.

To verify this analysis package without reading the raw data, from the repository root:

```sh
(cd review/post_full_fable/independent && sha256sum --check ARTIFACTS.sha256)
```

To reproduce from retained raw data, from the repository root, choose a **new** output directory (existing results are never overwritten). Substitute the raw-data location if it differs on your machine:

```sh
python3 review/post_full_fable/independent/symmetric_scan.py \
  --raw-root /workspace/cce-full-local \
  --repository . \
  --output-dir /workspace/cce-reviews/post-full-independent-recheck
```

Python's standard library suffices; the original interpreter was Python 3.12.14. Runtime, Python metadata, and absolute inventory paths can differ on another machine, so compare diagnostic counts/statistics and bound input hashes rather than expecting the entire JSON artifact to have the same hash. The independent `relative_certificate.md` is a separate mathematical note, not a generated analysis result. It is included in the enclosing review package's checksum inventory.
