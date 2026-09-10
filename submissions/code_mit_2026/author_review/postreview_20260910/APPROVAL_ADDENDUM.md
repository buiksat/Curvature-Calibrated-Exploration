# Approval addendum: post-review manuscript audit

Date: 2026-09-10

Status: **AUTH01 resolved; remaining author approvals pending.** This
record audits the current working copy of `submissions/code_mit_2026/main.tex`
(SHA-256
`582fc40fd849d16e6d7ab890e8c41ab83db524064a7836827b17d2c0bf2bc673`).
It does not approve publication or expand the authority granted by either
review packet.

## Exact-block adoption audit

The current manuscript adopts every requested packet-01 block without
substantive drift:

| Packet-01 item | Current `main.tex` location | Audit result |
| --- | --- | --- |
| `ABSTRACT` | lines 35--48 | Exact block adopted |
| `A02` | lines 54--67 | Exact block adopted |
| `A01` | lines 85--135 | Exact block adopted; direct Loewner sandwiches replace the selected-path premise as the theorem's certificate interface |
| `F02` | lines 136--140 | Exact block adopted |
| `F01` | line 143 | Exact selected-query definition adopted: `$q_s:=q_{\theta_s}(x_s,a_s)$` |
| `C01` | lines 169--181 | Exact near-linearity block adopted; this is packet-01 `C01`, not approval-ledger `C01` |
| `B01` | lines 184--196 | Exact block adopted, including exact-arithmetic and runtime qualifications |
| `B02` | lines 205--214 | Exact block adopted; the analytic inequality uses the exact selected-path length, not unenclosed quadrature |
| `D01` | lines 236--245 | Exact block adopted; the pre-existing coverage and bound statements remain after it |
| `CONCLUSION` | lines 248--254 | Exact block adopted |
| Citation completion | line 261 | Nussbaum page range `7:1649--1707` adopted |

These edits remain proposed manuscript text. Their presence in the working
copy records adoption for review, not author consent.

## AUTH01 and commit authorization

Direct author instruction on 2026-09-10 resolved AUTH01 as:

```text
Name:        Bahram Behzadian
Affiliation: Meta
```

The manuscript now renders this name and affiliation through `\author{}`. The obsolete
`[AUTHOR: supply final author order and affiliations]` line was removed. The line
`Proposed revision for author review.` remains exactly as required.

The author separately granted release authorization on 2026-09-10 to commit this exact
scoped candidate. This permission lifts only the prior no-commit gate. It does not
authorize a push, PR, merge, rebase, force operation, history rewrite, branch move,
publication, or conference submission.

## Decisions still open

The existing approval ledger remains controlling and unchanged:

- `AUTH02`: venue form requirements and anonymity instructions remain
  unresolved.
- Approval-ledger `C01`: author approval of the pooled
  $e^{D_Q/2}$ medians remains unresolved. This is distinct from packet-01
  block `C01`, the adopted analytic near-linearity paragraph.
- Approval-ledger `C02`: author approval of contribution positioning remains
  unresolved.

Packet-01 `E01` is not in the manuscript. Packet 02 verifies the aggregate
arithmetic needed for it, but inclusion remains an author decision. The
packet-02 paired standard errors are also verified but withheld from the
manuscript pending author approval. No bootstrap zero-exclusion claim was
restored.

Terminal inflation quantiles are out of scope for this revision. Packet 02 did
not complete the required 200-record terminal extraction. The values already
in Table 1 are pooled seed-round medians, correctly identified as such in the
caption; they are not terminal quantiles.

## Review-only bound wording

The following two alternatives are retained verbatim for author review. They
are **REVIEW-ONLY / AUTHOR INCLUSION PENDING** and are not part of the current
manuscript.

### Packet-01 `E01`

> A post-review same-trajectory attribution diagnostic sets every
> $D_{Q,t}$ in the evaluated RHS to zero while retaining the recorded
> history, $\beta_t$, $\gamma_T$, and $b_t$. At $T=1000$, the resulting
> conditionwise means remain about $5.0$--$5.3$ times the cap $2T$.
> The removed path increment accounts for about $2.0\%$--$16.3\%$
> of the mean RHS, using ratios of means. Thus most of the reported
> mean bound remains without the explicit path contribution.
> These no-path values are attribution diagnostics, not guarantees
> for the executed policy or results from a separately run linear policy.

Here the percentage is the removed path increment as a share of the full mean
RHS:

```math
100\frac{\overline{B_D}-\overline{B_0}}{\overline{B_D}}
=100\frac{\overline{I_T}}{\overline{B_D}}.
```

It gives the packet-01 range 2.0%--16.3%. It is a ratio of aggregate
means, not a mean or median of trajectory-level ratios.

### Packet-02 alternative bound paragraph

> In a post-review descriptive analysis of the locked evaluation, we set the explicit path factors to one while retaining each recorded Hessian-policy trajectory, including its confidence radii, information gain, and bias terms. At `T=1000`, the resulting mean zero-path expressions were 10,016.38, 10,093.72, 10,252.50, and 10,556.24 for `D_{\rm target}=0.25,0.5,1,2`, respectively. Explicit transport increased these means by 2.05%, 4.21%, 8.89%, and 19.44%. The zero-path means themselves remained 5.01–5.28 times the deterministic `2T` cap. Thus explicit transport inflation amplifies an already large expression; this same-trajectory calculation is neither a baseline-policy rerun nor a claimed guarantee with transport removed.

Here the percentages measure uplift relative to the zero-path mean:

```math
100\left(\frac{\overline{B_D}}{\overline{B_0}}-1\right)
=100\frac{\overline{I_T}}{\overline{B_0}}.
```

They are 2.05%, 4.21%, 8.89%, and 19.44%. This denominator differs from
packet-01 `E01`; the two percentage series are therefore consistent but not
interchangeable. These are also ratios of aggregate means. Neither paragraph
uses a pooled or terminal inflation median to reconstruct the cumulative
bound.

## Page budget and authority

**PAGE-BUDGET BLOCKED.** The retained build logs report:

- baseline: 3 pages (`build/baseline-main.log`, line 726);
- batch 1: 4 pages (`build/batch1-main.log`, line 726);
- final: 4 pages (`build/final-main.log`, line 727).
- AUTH01 rebuild: 4 pages (`build/auth01-main.log`).

The current draft therefore exceeds the three-page limit. No scientific
condition, qualification, citation, author-review marker, font, or margin may
be removed or weakened under this addendum to force a three-page fit.

This addendum is review documentation. It does not amend the historical approval ledger,
canonical theory, experiment code, locked evidence, or scientific provenance. Direct
author instruction permits committing this scoped candidate. It grants no authority to
submit, publish, push, mirror, move a branch, or resolve AUTH02, ledger:C01, ledger:C02,
E01 inclusion, paired-SE inclusion, or the page budget.
