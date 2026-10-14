# Bibliography and appendix audit

This audit starts from `main` at
`846987748046a372458b6cadcda352263469e486`. It separates source checks from
publication metadata that this environment could not retrieve. It does not
re-audit the mathematical correctness of the legacy results.

## Flagged references

The bibliography has 41 distinct keys and no duplicate keys. Each of the three
flagged keys exists exactly once and was used by the inspected baseline. No externally
corroborated bibliographic error was established, so their fields and citation
keys have been preserved.

| Key | Metadata currently asserted | Verification outcome |
| --- | --- | --- |
| `granziol2026hessian` | Diego Granziol and Khurshid Juarev; *Hessian Spectral Analysis at Foundation Model Scale*; arXiv:2602.00816; 2026 | The [arXiv record](https://arxiv.org/abs/2602.00816) could not be retrieved. The identifier's date prefix is consistent with 2026, but that does not verify its title or authors. |
| `wen2026revisiting` | Dongxie Wen, Hanyan Yin, Xiao Zhang, Peng Zhao, Lijun Zhang, Zhewei Wei; *Revisiting Matrix Sketching in Linear Bandits: Achieving Sublinear Regret via Dyadic Block Sketching*; ICLR; 2026 | Exact-title queries to both OpenReview API versions and the [official ICLR 2026 program](https://iclr.cc/virtual/2026/papers.html) could not be retrieved. Venue, acceptance status, year, and author list remain externally unverified. |
| `pascanu2014revisiting` | Razvan Pascanu and Yoshua Bengio; *Revisiting Natural Gradient for Deep Networks*; arXiv:1301.3584; 2013 | The [arXiv record](https://arxiv.org/abs/1301.3584) could not be retrieved. The cited preprint identifier is consistent with a 2013 initial posting; the internal key's `2014` suffix does not control the rendered year and is not evidence of an error. |

All attempts failed with `Tunnel connection failed: 403 Forbidden` before a
publication record was returned. The blocked hosts were `arxiv.org`,
`export.arxiv.org`, `api.openreview.net`, `api2.openreview.net`, `iclr.cc`,
`dblp.org`, and `api.crossref.org`. The latter two were independent catalog
cross-checks; they supplied no evidence either. The API attempts used arXiv's
`/api/query?id_list=2602.00816,1301.3584`, OpenReview's
`/notes?content.title=<exact title>&limit=10`, DBLP's publication search, and
Crossref's title search.

Consequently, these references must not be described as either verified or
fabricated based on this audit. Recheck the two arXiv records and the Wen
OpenReview record when these hosts are available; change publication fields
only if the returned metadata establishes a discrepancy. A preprint can retain
its original year even when a later conference version exists. Rename the
Pascanu key only if a consistent internal-key cleanup is desired, not as a
substitute for checking the publication record.

## Appendix dependency finding

The confidence-transport proof file `transport_proofs.tex` references theorem
and equation labels in `transport_theory.tex`; it does not reference labels in
the legacy appendix cluster. Likewise,
`transport_experiment_appendix.tex` references the main experiment and its own
diagnostic artifacts. These two appendices directly support the headline
theorem, solver interface, and reported controlled study.

The legacy cluster comprises `legacy_dynamic.tex`, `appendix_rates.tex`,
`appendix_deferred.tex`, `appendix_protocol.tex`,
`appendix_onesided_proof.tex`, `appendix_cg.tex`,
`appendix_twosided.tex`, `appendix_ggn.tex`, and `appendix_expfam.tex`.
These files are mutually dependent: the fallback theorem uses assumptions and
certificates in `appendix_deferred.tex`; that file uses the protocol,
conditional rates, CG appendix, and two-sided corollary; the protocol in turn
uses the GGN and exponential-family appendices. Deleting only the longest
files would leave unresolved definitions, theorem prerequisites, and proofs.

The inspected baseline has two explicit references from the main text into
this cluster:

- `transport_theory.tex` points to `app:one-sided-fallback` when the lower
  operator factor is unavailable.
- `body_related.tex` points to `thm:spectral-distortion` when describing the
  legacy approximate-curvature result.

`body_conclusion.tex` also asserts the availability of the one-sided fallback
without a label reference. The source dependency scan removed comments and
the disabled `\iflegacyextras` blocks before matching labels and references.
The existing `\legacyextrasfalse` setting disables only two optional blocks
inside `appendix_deferred.tex`; it does not remove the legacy cluster.

**Chosen revision scope: remove the whole legacy cluster from the active
TMLR manuscript, while preserving its files in Git.** This is coherent with the
dependency finding provided that the main text retires both legacy references
and the unlinked fallback claim. Retain `transport_proofs.tex` and
`transport_experiment_appendix.tex` as the appendices supporting the main
claims, with a short scope note identifying the excluded material. This is
preferable to selectively cutting prerequisite or proof files. The dependency
audit itself does not edit `main.tex` or delete source files.

The corresponding source archive must omit the nine inactive files and
`tables/growing_window_pareto.tex`, the legacy conditional-rate table. The
baseline `build.sh` archives every `.tex` and `.csv` file below the submission
directory, so removing `\input` commands alone would still ship that material.
Build and verify a clean extraction of the revised archive after changing its
membership. Pascanu's natural-gradient citation occurs only in the excluded
`appendix_protocol.tex`; its database entry can remain available for the
retained historical sources without appearing in the active bibliography.

The implementation branch's more elaborate `package.py` is not the packaging
entry point on `main`. Its `stage()` copies `paper/*.tex`, while `closure()`
packages actual `main.fls` inputs, so an updated active entry point would
automatically exclude inactive legacy files from its source archive. Porting
this revision to that branch still requires updating the independent
`COMPILED_CLOSURE` contract in `tools/anonymous_package_contract.py` and the
supplement's `SUPPLEMENT_SYMBOLIC_ARTIFACTS`, which explicitly includes
`growing_window_pareto.tex`. Repin that contract only after auditing a rebuilt
source closure; the old pins describe the old manuscript. Those research-branch
contracts were inspected but not changed by this audit.


## Follow-up disposition on 2026-10-14

The full-study revision removes the active Wen/adaptive-dyadic and
Granziol/large-scale-HVP claims. Their historical BibTeX records are retained;
the blocked retrievals establish neither correctness nor fabrication. Publisher
repositories supplied primary sources for Kuzborskij et al. (2019), Lattimore
et al. (2020), and Zhou et al. (2020). The related-work section now credits the
verified heavy-spectrum limitation and misspecified-linear confidence
connection directly. The bounded source check, retrieval outcomes and PDF
hashes are recorded in the research branch's
[literature audit](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/cce-review-revisions/review/post_full_revision/LITERATURE_CHECK.md).
It is not a comprehensive novelty review.

The current manuscript adds the full-study appendix and new transport proofs
while retaining the earlier exclusion of the legacy cluster. The main-branch
source archive is generated from the new active compiler closure. Its successful
build does not update or certify the research branch's stricter anonymous
supplement contract; see [REVISION_STATUS.md](REVISION_STATUS.md).
