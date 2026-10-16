# Abstract revision and source guidance

Reviewed on 2026-10-15 (America/Los_Angeles). The sources below were opened and
read directly online before rewriting. The earlier cloud-access failure no
longer prevents this guidance check. The UNC candidate in the handoff was not
consulted; no recommendation is attributed to it.

## Guidance actually read

- [MIT EECS Communication Lab, Abstract](https://mitcommlab.mit.edu/eecs/commkit/abstract/):
  organize background, the specific gap, contribution, high-level approach and
  results, then implications. Explain essential terms and omit unnecessary
  methodological detail. Its suggested length is writing advice, not a TMLR rule.
- [Nature, How to construct a summary paragraph](https://www.nature.com/documents/nature-summary-paragraph.pdf):
  move from accessible context to the problem, principal result, contribution
  to understanding, and broader meaning. We use that narrative progression,
  without treating Nature's format or length advice as TMLR requirements.
- [TMLR author guidelines](https://jmlr.org/tmlr/author-guide.html):
  use the official LaTeX template for an anonymous PDF; place appendices after
  references. Anonymous PDF/ZIP supplements may total at most 100 MB. There is
  no fixed paper page limit, but length must be justified. Authors need complete
  OpenReview profiles and the required submission declarations.
- [Official TMLR template, main.tex](https://github.com/JmlrOrg/tmlr-style-file/blob/main/main.tex):
  the abstract must be one paragraph in the template's formatting. We found no
  abstract word limit in this template or the author guidelines. The revised
  abstract has 250 whitespace-delimited words; that is an editorial choice.
- [TMLR acceptance criteria](https://jmlr.org/tmlr/acceptance-criteria.html):
  claims need accurate, convincing evidence and clear communication. A result
  need not improve a benchmark to be of interest. This supports presenting the
  conditional theorem and adverse empirical findings without inflating either.
- [TMLR editorial policies](https://jmlr.org/tmlr/editorial-policies.html):
  the work must satisfy originality and concurrent-submission rules. All
  authors need sufficient submission quota and must take responsibility for
  the content; LLM assistance does not transfer that responsibility.
- [TMLR FAQ](https://jmlr.org/tmlr/faq.html):
  explicitly disclose LLM assistance in a first-page footnote. The existing
  Codex/Claude disclosure is retained. Papers exceeding 12 main-text pages may
  take longer to review; that threshold is not a page limit.
- [TMLR ethics guidelines](https://jmlr.org/tmlr/ethics.html) and
  [code of conduct](https://jmlr.org/tmlr/code.html): these linked author
  obligations were also read. The existing broader-impact statement remains;
  no new application, dataset or deployment is introduced by this revision.

These are current web requirements as retrieved on the review date. This check
is not an OpenReview submission or confirmation of author-specific eligibility.

## Editorial decisions and scientific scope

The first sentence explicitly names contextual-bandit policies and explains the
role of confidence estimates in exploration. The next sentence identifies the
specific gap: sequential confidence arguments do not automatically justify
confidence bands based on recomputed historical gradients.

The contribution connects a valid reference band to scores based on recomputed
gradients using certified bounds. The theorem remains conditional on explicit
statistical and computational assumptions. Detailed optimizer and corrected-center
constructions remain in the introduction and theory, with all their conditions.

The theoretical limitation fixes the history, center, radius and bias. Exact
**actionwise** transport recovers the reference width; the result does not order
regret across policies with different adaptive histories.

The experiment is explicitly one synthetic 29-parameter scaled-tanh model,
four policies, three conditions and 50 paired seeds per condition. All nine
pointwise paired 95% intervals favor the comparators over Hessian transport.
Transport inflation dominates its bounds, and both its bounds and the reference
policy's own bounds exceed a deterministic regret cap. Floating-point confidence
and optimism checks pass even for the uncertified control; they do not establish
universal validity or a practical advantage. No improved-performance claim is made.

The final sentence distinguishes conditional confidence validity, informative
regret bounds and improved decisions. The title already expresses the same
scope. Small introductory changes add the valid starting band, say retraining
*can* change representations, and attach the one-model scope to the early
experimental summary. Formal statements, proofs, measured results and experimental
settings are not revised.
