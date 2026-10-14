# Focused literature and bibliography verification

Checked 2026-10-14 UTC against the working manuscript in `/workspace/cce-research`, based on commit `a459162ee0bc9b64996da6f9d6b2ac1857be1f3d` with concurrent scientific revisions. Scope: the corrected center, same-history width comparison, weighted/relative Gram certificates, and two flagged 2026 citations. This is a bounded primary-source check, not a novelty guarantee or a comprehensive literature review.

## Access and flagged records

Direct requests to arXiv, OpenReview, the ICLR 2026 program, and PMLR all failed before receiving an HTTP response body: `Tunnel connection failed: 403 Forbidden`. The exact six requests and failures are recorded in [retrieval-log.json](literature_retrieval_log.json). Public Git access to the official `mlresearch` publisher repositories succeeded, so the PMLR results below were checked using publisher metadata and published PDFs, not search snippets or recollection. No paid service was called.

| Existing bibliography key | Verification result | Manuscript action |
| --- | --- | --- |
| `granziol2026hessian` | The asserted arXiv identifier `2602.00816`, title, authors, and content could not be checked because the arXiv request was blocked. No evidence here establishes an error. | Removed the peripheral active claim about distributed HVP/Krylov infrastructure above `10^8` parameters. That scale claim was unverified and unnecessary to a dense experiment that asserts no matrix-free scalability. The historical BibTeX record is unchanged. |
| `wen2026revisiting` | The asserted ICLR 2026 publication and adaptive dyadic-block result could not be checked because OpenReview and ICLR requests were blocked. No evidence here establishes an error. | Removed the active citation and adaptive-dyadic claim. The heavy-spectrum limitation is supported directly by the verified 2019 paper, so it now receives that attribution. The historical BibTeX record is unchanged. |

The earlier [bibliography audit](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/6a9ea20c3f1bdd91738984160d707b808061aa1f/submissions/tmlr_2026/BIBLIOGRAPHY_APPENDIX_AUDIT.md) records additional blocked metadata routes. A citation key whose year differs from a publication year is not itself a metadata error; no correction to `pascanu2014revisiting` was inferred from its key.

## Publisher sources verified

Official PMLR repository snapshots:

- `mlresearch/v89`: `f3e37cbd49e372f3ada4886e479f53778178240c`.
- `mlresearch/v119`: `500846bfc432506177d62479931d030063010517`.

Only public publication metadata and published article/supplement PDFs were inspected. The three current BibTeX records below match the publisher's title, authors, venue/year, and page range.

| Publication | Publisher metadata | Published source inspected |
| --- | --- | --- |
| Ilja Kuzborskij, Leonardo Cella, Nicolò Cesa-Bianchi. *Efficient Linear Bandits through Matrix Sketching*. AISTATS 2019, PMLR 89:177–185. | [Immutable metadata](https://github.com/mlresearch/v89/blob/f3e37cbd49e372f3ada4886e479f53778178240c/_posts/2019-04-11-kuzborskij19a.md) | [Immutable PDF](https://github.com/mlresearch/v89/blob/f3e37cbd49e372f3ada4886e479f53778178240c/kuzborskij19a/kuzborskij19a.pdf): introduction p. 2, Section 3, Proposition 1, Lemma 1, Theorem 2. |
| Tor Lattimore, Csaba Szepesvári, Gellért Weisz. *Learning with Good Feature Representations in Bandits and in RL with a Generative Model*. ICML 2020, PMLR 119:5662–5670. | [Immutable metadata](https://github.com/mlresearch/v119/blob/500846bfc432506177d62479931d030063010517/_posts/2020-11-21-lattimore20a.md) | [Main PDF](https://github.com/mlresearch/v119/blob/500846bfc432506177d62479931d030063010517/lattimore20a/lattimore20a.pdf): Section 4, Proposition 4.5, Section 5. [Supplement PDF](https://github.com/mlresearch/v119/blob/500846bfc432506177d62479931d030063010517/lattimore20a/lattimore20a-supp.pdf): Appendix E, equations (4)–(6), Theorem E.1. |
| Dongruo Zhou, Lihong Li, Quanquan Gu. *Neural Contextual Bandits with UCB-based Exploration*. ICML 2020, PMLR 119:11492–11502. | [Immutable metadata](https://github.com/mlresearch/v119/blob/500846bfc432506177d62479931d030063010517/_posts/2020-11-21-zhou20a.md) | [Immutable PDF](https://github.com/mlresearch/v119/blob/500846bfc432506177d62479931d030063010517/zhou20a/zhou20a.pdf): Algorithm 1, especially lines 7, 11, and 12. |

Retrieved PDF SHA-256 values (publisher links above; the PDFs and text extracts remain in the external local review cache, not this repository):

```text
b0f857c07a389b827ae68f2ed49bc6ebbc588135c81c520647a6714bd4c36d8e  kuzborskij19a.pdf
e7311ae0769bcd4a0e55adf550a9fe2660cb356774e43bf44afb6b95adbaf42c  lattimore20a.pdf
f3ac559ca4bcf2f4a3da0610e8574ad490b78113ae2453f64421c158fc7381c4  lattimore20a-supp.pdf
799242fcd6afe8644c5f24c4677a11bb094c5fd11321c4cb8aa983d57d2649f1  zhou20a.pdf
```

## Closest verified overlap and narrow positioning

**Misspecified linear regression is an existing ingredient.** Lattimore et al., Appendix E, explicitly permits contextual feature matrices to change between rounds. With observations `Y_s = <X_s, theta> + eta_s + Delta(X_s)`, bounded misspecification, and ridge Gram `G_t`, its equation (6) augments the LinUCB score by `epsilon * sum_s |a^T G_t^{-1} X_s|`. Theorem E.1 proves a misspecification-dependent regret bound, and the appendix shows a failure of the unmodified algorithm. This is a direct prior connection, not merely a title-level resemblance.

The current manuscript's `eq:pseudo-response-new` rewrites nonlinear observations as predictable linear observations with additive Taylor and misspecification residuals. Its proof uses the usual self-normalized noise control, ridge regularization, and a deterministic residual bound. The current affine offset maps the linear estimate back to the nonlinear prediction. The models and residual envelopes are not identical to Lattimore et al.'s constant-error model, and that paper does not establish the present replay-curvature transport result. Nonetheless, the construction should be positioned as an affine-offset reduction using established misspecified-regression ingredients, not as a new generic linear confidence method. The new related-work paragraph makes this explicit, using the already existing `lattimore2020learning` entry. The theorem owner confirmed this scope.

**Spectral error already connects to bandit confidence and regret.** Kuzborskij et al., Section 3 and Theorem 2, derive a sketched confidence ellipsoid whose radius depends on spectral error. The introduction explicitly states: “In the worst case of a spectrum with heavy tails, SOFUL may incur linear regret.” The limitation therefore does not need the unverified Wen record for support. Their estimator also uses a sketched inverse, whereas the present corrected center uses a frozen ridge reference; the algorithms should not be equated. The current distinction—an additional comparison from frozen confidence to current replayed curvature, followed by operator and solver comparisons—is appropriate. The existing disclaimer of novelty for the sandwich-to-regret reduction remains.

**Same-history width domination is a direct consequence, not policy dominance.** For the same center, confidence radius, bias envelope, and history, the manuscript's certified transport bonus is at least the frozen reference width: this follows from its endpoint sandwich and the upper solver certificate. It does not imply smaller actual regret for the frozen policy, since different action choices generate different histories. The `prop:frozen-width-ucb` comparison and width-floor discussion should retain these conditions. No external priority claim for this algebraic observation was verified or added.

**Weighted Gram and relative SPD comparisons need modest novelty language.** Lattimore et al., Proposition 4.5, already analyzes the design-weighted Gram `G(rho) = sum_a rho(a) aa^T`, a weighted least-squares estimator, and deterministic misspecification bias through the inverse Gram. That is a static experimental-design result, not a theorem for evolving likelihood curvature. In the present manuscript, `lem:factor-spd-path` uses the product rule for `V = lambda I + B^T B` and the bound `||B V^{-1/2}|| <= 1`; `cor:relative-endpoint-ucb` uses a two-sided SPD comparison directly. Such formulas are concrete sufficient conditions for the transport interface. The terms “weighted Gram” and “relative operator norm” alone do not establish novelty. A claim of priority for the particular weighted/replayed certificate would require further research beyond this bounded check.

**The NeuralUCB comparison is supported.** Zhou et al., Algorithm 1 line 11, adds the rank-one gradient outer product evaluated at the collection-time parameter; line 12 subsequently trains the network. Thus the existing statement that it stores collection-time gradient contributions rather than replaying every historical Jacobian is supported. Its NTK/training assumptions should remain distinct from the present conditional confidence model; the comparison is not evidence that NeuralUCB lacks a proof.

The main Lattimore PDF bibliography also names Ghosh, Chowdhury, and Gopalan, *Misspecified Linear Bandits*, AAAI 2017. This is secondary corroboration only: the original Ghosh paper and its precise page range were not independently retrieved in this check, and its existing entry was not changed.

## Changes and validation

The only repository file edited for this task is `paper/body_related.tex`:

1. Added the verified misspecified-linear/affine-offset connection.
2. Credited the heavy-spectrum limitation to Kuzborskij et al. directly.
3. Removed active Wen/adaptive-dyadic and Granziol/large-scale-HVP claims because their sources remain unverified and neither claim is necessary to the revised contribution.

The bibliography, scientific theorem/proof sources, mirrors, experiment data, and runtime code were not edited. No commits or pushes were made. `git diff --check -- paper/body_related.tex` passed. A focused static check confirmed all 29 related-work citation keys exist, the referenced pseudo-response equation label exists, both removed citations are absent from the related-work text, and both historical BibTeX records remain. The parent owns full manuscript compilation and source-mirror synchronization; this focused edit adds one existing citation key and references an existing equation label.

Remaining gaps are explicit: the two 2026 records are unverified rather than disproved; other cited methods were not all independently re-audited; this check does not establish optimality, priority, or a comprehensive novelty guarantee.
