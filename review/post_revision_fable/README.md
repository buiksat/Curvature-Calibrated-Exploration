# Fable review of the revised paper

Completed on 2026-10-14 using the exact API model **`claude-fable-5`**, with no
model substitution. The request was to review the newly revised paper as a
research scientist and give actionable feedback across theory, experiments,
writing, positioning and submission readiness.

Fable's recommendation is **“minor-to-moderate revise, then submit.”** It reports
no demonstrated central proof error and regards the theory/negative-study
narrative as substantially improved. This is the model's review judgment, not an
independent acceptance or readiness determination. Several interpretations and
proposed edits are incorrect or need narrower scope; read
[QUALIFICATIONS.md](QUALIFICATIONS.md) alongside the response.

## Review materials

- [Complete readable review](review.md).
- [Exact response text](verbatim_review.json), retained as a JSON string.
  The readable Markdown removes four trailing spaces and adds a terminal
  newline; no substantive wording is changed. Both versions have separate hashes
  in the review record.
- [Prompt](prompt.md), naming the exact revisions and current evidence limits.
- [Review record](review_record.json): model, immutable inputs, API completion,
  usage, bounds, and response hashes.
- [Actual source coverage](source_coverage.json): all 37 read-only calls,
  returned line ranges, result hashes and partial reads.
- [Source-checked interpretation and next steps](QUALIFICATIONS.md).

The review used manuscript commit
`fb95a696863326345be0823de399937fcbdb8af8` and research commit
`5f00be1b537eef476150c3115822f00cd95461ae`. It concerns the current 38-page TMLR
sources, including the completed follow-up and new relative-certificate audit.
It does not review the frozen historical `paper/main.pdf` as the new paper.

The API response completed with `end_turn` after 18 response turns and 37 source
inspection calls. Its tools returned all 838 theory lines, all 572 proof lines,
the active empirical sections and all five new tables. This is better source
coverage than the preceding review, but returned lines do not establish formal
proof verification. Implementation inspection was partial: only lines 200–359
of the 2,496-line scientific source and lines 1–120 of the 396-line follow-up
configuration were returned. The replay analyzer, table generator, full
protocol, per-seed audit data, raw trajectories and final validation document
were not inspected by Fable. JSON inspection sampled a few fields rather than
recomputing the full empirical record. The exact coverage file takes precedence
over the review's own coverage prose.

No shell execution, PDF viewing, external literature browsing, tests or new
experiments were available to Fable. Recorded test results and build facts were
provided as evidence, not represented as executions performed by the reviewer.
The external raw archive was not sent. API credentials and request/response
transcripts are not committed; transcripts remain in the local review workspace.

## Recommended interpretation

The useful next revision is small and focused:

1. Add a short abstract example illustrating why a narrower current width is
   not justified by reference confidence alone. State that it is an abstract
   confidence-band example, not a demonstrated failure trajectory in the
   scaled-tanh experiment or a new necessity theorem.
2. Reduce repeated caveats while keeping essential qualifications next to the
   relevant claims. Make the same-history width limitation easier to find, and
   retain certified-region/error assumptions and pointwise interval language.
3. Consider adding the already recorded context-free and best-fixed-action
   baselines as descriptive context. Do not label close sample means equivalent
   without an appropriate comparison.
4. Verify the suggested weighted/nonstationary-bandit literature before adding
   citations or priority claims. Pruning inactive unverified bibliography entries
   from a submission-only database is an editorial option, not proof that the
   entries are false or a newly established venue requirement.
5. Finish anonymous evidence packaging and a durable raw-data distribution path
   before claiming the reproducibility bundle is ready.

Do not adopt Fable's “all policies are width-dominated” statement, its causal
trajectory explanation, or its suggested performance-ceiling language. The
width-floor theorem does not order adaptive regret. Do not start a large new
CPU/GPU study solely on this review's proposed stress settings: the proposed
failure mechanism first needs justification, then a separate locked protocol
and fresh evaluation seeds if an experiment remains informative.

This commit preserves and evaluates the review. It changes no manuscript,
proof, experiment, configuration, recorded result or runtime implementation.
