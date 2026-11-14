# Editorial port verification scope

Verification must be tied to the exact commit and its external release output.
The required gates are the strict research build, complete manifest comparison,
clean source-ZIP rebuild, clean supplement verification, the full retained suite
in a git-archive sandbox with the current `TMLR_OUT`, and literal, citation,
statement and anonymity comparisons against the approved editorial source.

The statement and proof environments must remain byte-identical to the approved
editorial revision. Current figure transformations must authenticate both their
original generated sources and the approved transformed bytes. Scientific input
hashes, seed grids, bootstrap settings and numerical tolerances are unchanged.

The numerical ledger retains unchanged selectors for historical values and maps
current prose declarations to the approved wording and source locations.
Historical manuscript literals are checked only in trees that retain those
sources; they are not represented as current submitted claims. Archive closure,
semantic-unit, occurrence-count, regeneration and anonymity gates remain active.

Use README.md for commands. Preserve full logs and exact pass/fail/skip counts
outside the checkout. The pre-existing CI failure requires its own evidence;
a red status alone does not establish a cause. No build constitutes an upload,
push, independent review, acceptance or submission.

## Current test inventory

These counts were obtained by collection in an external source-archive sandbox.
Collection is not evidence that a test ran or passed. Execution results belong
to the verification report for the exact source state.

| Inventory | Count |
|---|---|
| Release-package test collection | 568 collected |
| Repository suite collection | 768 collected |
