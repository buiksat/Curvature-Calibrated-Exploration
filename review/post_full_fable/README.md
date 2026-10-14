# Research direction after the full follow-up

The authors requested a new Fable review of the paper and completed experiments,
with concrete advice on how to improve the research. The API review completed on
2026-10-14 UTC using **`claude-fable-5`**, without model substitution.

Start with [the revision plan](REVISION_PLAN.md) and
[the corrections to Fable's advice](QUALIFICATIONS.md). The recommended direction
is a focused theory and diagnostic paper that reports the negative study directly.
This is a research direction, not a finding that the current paper meets TMLR's
publication criteria. The immediate scientific questions fit the existing CPU
setup; large GPU benchmarks should follow a justified algorithmic question.

## Review and provenance

- [Fable's original response](review.md), preserved byte for byte.
- [The prompt](prompt.md), including the negative results and requests for proof
  obligations, minimal experiments, a rewritten abstract, and stop/go decisions.
- [Review record](review_record.json): model, pinned commits, response completion,
  usage, and content hashes.
- [Actual source coverage](source_coverage.json): all 26 read-only tool requests,
  returned line ranges, and result hashes. Completion of the API response does
  not mean exhaustive inspection of all scientific sources.
- [Independent mathematical note](independent/relative_certificate.md): the
  exact width comparison and a tighter certificate specific to the scaled-tanh
  model. It is a proposed research note, not an implemented or evaluated method.
- [Independent diagnostic evidence](independent/README.md): analysis of retained
  evaluation logs, with a reproducible script and compact output. These are
  exploratory analyses of existing histories, not additional adaptive runs.

The review inspected manuscript commit
`6a9ea20c3f1bdd91738984160d707b808061aa1f` and research commit
`739067b17f1f93b032263bf5fbada6d9910c4871`. The latter contains the
[full results](../transport_review_followup/FULL_RESULTS.md) from execution source
`707c8243ea6d5395369ed812a68cf7e27d700596`. At review time the full follow-up
had **not** been integrated into the LaTeX manuscript.

API request/response transcripts, credentials, and the full raw trajectories are
not included here. The original API artifacts remain in the local review
workspace; raw trajectories remain at `/workspace/cce-full-local`. The portable
experiment export supports terminal-summary/interval replay, not complete
roundwise reconstruction. Neither the model's review nor our targeted checks
constitute a complete proof audit or an external literature verification.
