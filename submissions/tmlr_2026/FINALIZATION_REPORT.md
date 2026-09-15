# TMLR finalization report

**Internal. Not uploaded.** `package.py` refuses to place this file in
`source.zip` or `supplement.zip`, and a test enforces that.

Written 2026-09-15, last revised 2026-09-16.
Baseline `b99b682ecc8f69552a3f57b1b85333378ed12ac1` on
`cce-experiments`, re-resolved against `origin/cce-experiments` after a fetch.
Nothing was submitted, uploaded, pushed, merged or rebased; no experiment ran;
no authentic data was prepared; no project F or L commit was created.

---

## 1. What this is and is not

This closes one scientific workstream: confidence transport from collection-time
features to current relinearized curvature, its corrected-center construction,
and the completed dense controlled audit. It does not close the project. The
realistic Covertype/Nyström extension is deferred and excluded, and nothing in
this submission depends on it.

The organizing claim is that the paper establishes a conditional route from
collection-time confidence to action scores based on current relinearized
curvature, and that a controlled dense audit shows validity of an analytic
transport certificate does not by itself deliver a useful regret bound or lower
sample-mean regret. Both halves are in the abstract, the results and the
conclusion, and the negative half is not softened anywhere.

## 2. Venue requirements as actually read

All five TMLR pages and the style repository were fetched through the site's
own HTTPS endpoints on **2026-09-15**. The fetched bytes are kept outside the
repository at `/home/buiksat/cce-tmlr-work/venue/`.

| Source | SHA-256 of the fetched HTML |
|---|---|
| <https://jmlr.org/tmlr/author-guide.html> | `117ed02f6791f8167c861560a36d6efe3f12811a55ed416b84c4bf4c483055f1` |
| <https://jmlr.org/tmlr/editorial-policies.html> | `196a8803d48d6ba713b31e9ae8637827f6c1261a6a8023861c2df1501399c346` |
| <https://jmlr.org/tmlr/acceptance-criteria.html> | `14acb90e1530e6f318164e6f6e1ac2d954a8fba7f65ac58a7dca125bbebf8be7` |
| <https://jmlr.org/tmlr/submissions.html> | `6dbc3f785bbcf30efcce0293bce6ba4d942a1927ba5d49e5a331ba95c02bd9f9` |
| <https://jmlr.org/tmlr/ethics.html> | `e0f3ad62ed3f77e54e8d629f07d093569b722d75d54eebe55a1455d2e6f80113` |
| <https://ide.mit.edu/events/2026-conference-on-digital-experimentation-mit-codemit/> | `03fc3e1c863fedc57ec558171716f396d740f065ab8ce54e6256d5424f91b826` |

Requirements the build actually satisfies, quoting what the pages say:

- **Double-blind.** "TMLR uses a double blind review process and submissions
  must be anonymized." `tmlr.sty` is loaded without `[accepted]` and without
  `[preprint]`, which is what suppresses the author block; the verifier now
  fails if either option appears.
- **Mandatory unmodified template.** "The Author Guidelines page contains a
  LaTeX stylefile and template; these are mandatory. Any changes to the
  stylefile or template that alters the formatting, font, or layout of the
  manuscript may result in rejection without review." Nothing in
  `paper/tmlr_style/` is edited; the build puts it on `TEXINPUTS`/`BSTINPUTS`.
- **No page limit.** "Submissions may be any length, but a paper's length
  should be justified by its content and papers that are unusually long (not
  counting any Appendices) are likely to result in reviewing delays." Main text
  through the references is 19 pages (1--19); the appendix is 49 (20--68).
- **No shrinking to fit.** The same page says not to change the font size or the
  margins. Nothing the submission compiles reduces a font size, reduces
  `\tabcolsep` or `\arraystretch`, scales a box, or alters the text block; a
  build gate enforces it and fails the build otherwise (section 9d).
- **Supplement.** "Authors may submit up to 100MB of supplementary material …
  all supplementary materials must be in PDF or ZIP format … supplementary
  material must be anonymized." `supplement.zip` is 84,190,529 bytes, ZIP,
  84.2% of the limit, and passes both the anonymity scrub and the
  revision/identity scan.
- **Rolling submissions.** No deadline; nothing was rushed to meet one.
- **Licensing.** CC BY 4.0 applies from submission onward, copyright retained by
  the authors. No action was needed at build time; it is flagged in `PORTAL.md`
  because it binds from the moment of submission.
- **LLM policy.** "LLMs may be used as general-purpose assistive tools …
  authors are fully responsible for content … LLMs are not eligible for
  authorship." No disclosure field is mandated. A draft disclosure is in
  `PORTAL.md`; it claims mathematical review and proof exposition,
  experimental-methodology review, code and test work, and result
  interpretation, and it explicitly does not claim that every proof line was
  human-checked or that the experiments were independently reproduced.

### Official template revision and hashes

Downloaded 2026-09-15 from
`https://github.com/JmlrOrg/tmlr-style-file/archive/refs/heads/main.zip`.
Upstream `main` head, from the GitHub commits API:
`7bf90efe3a0debbba703c05c43f3ff7e4d4a2992`, committed 2023-06-30, "Removed
duplicated line in tmlr.sty".

```
816214ff5919aa457b6b443bee52b15d9561421417b7f8a50cc84651519f0002  tmlr.sty
306fd454cf40771bee01293eeb98d2c1cd5f4e11ed0cd7296b335f354fc45206  tmlr.bst
3d2922548e0e5f1a6c5676eda6ebb6dc20d7d305b4d8c2be5f1c833fb1084e6d  fancyhdr.sty
c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4  LICENSE
```

The repository LICENSE is Apache-2.0; the bundled `fancyhdr.sty` carries its own
LPPL 1.3 header (Copyright 1994-2021 Pieter van Oostrum) and is redistributed
under that license. Both obligations are recorded in
`paper/tmlr_style/PROVENANCE.md`, which ships inside `source.zip` as
`LICENSE-tmlr-style` plus the style files themselves.

### One template interaction, documented rather than patched

`tmlr.sty` defines a global `\AND` as its multi-author separator, so
`algorithmic.sty` then refuses to define its own and the build dies. The entry
point parks tmlr's meaning under `\tmlrAND` and hands `\AND` to `algorithmic`.
Neither style file is touched. A de-anonymized camera-ready with several authors
must separate them with `\tmlrAND`; that is noted in the entry point itself.

## 3. CODE@MIT overlap: unresolved, and why

TMLR's rule: "There should not be any reuse of written text, figures or results
between the submitted paper and any paper which has been published, accepted for
publication, or submitted in parallel at another archival, peer-reviewed venue.
It is acceptable for a submission to overlap with the author's previous work if
it was shared at venues or tracks that are publicly declared, in writing, to be
non-archival."

What the repository actually records:

- `submissions/code_mit_2026/README.md`: "Current status: technical three-page
  CODE@MIT candidate, not submitted" and "Nothing has been uploaded or
  submitted." The portal returned HTTP 401 and was never reached.
- `HANDOFF_2026-09-13.md`: "prepared for submission but NOT submitted", and
  then, explicitly, "**Whether the abstract was actually uploaded is not
  recorded here.** Confirm before assuming."

What the live venue page says, fetched 2026-09-15: nothing. The page now
advertises the November conference and early-bird tickets. It carries no call
for papers, no submission instructions, and **no statement of archival or
non-archival status in either direction**. The earlier reading recorded in the
handoff — "accepted abstracts distributed as informal working notes" — is not
reproducible from the live page, and in any case "informal working notes" is not
the written non-archival declaration TMLR's exception requires.

Disposition:

- If the abstract was never submitted, which is what two independent records
  state, TMLR's dual-submission rule is not engaged at all and the overlap is
  simply the authors' own unpublished derivative.
- If it *was* submitted, the authors need either a written non-archival
  declaration from the CODE organizers or a disclosure to the TMLR action
  editor. Resolving it by omission is not an option: TMLR retracts for
  undisclosed redundant publication.

This is an author action, stated precisely in `PORTAL.md`. It is **not**
concealed: the paragraph in `PORTAL.md` names CODE@MIT, the date and the
relationship. No AISTATS or other parallel submission was prepared.

The CODE abstract and its PDF are excluded from every upload, and the anonymity
scrub fails the build if anything from that directory leaks.

## 4. Deliverables

Built by `bash submissions/tmlr_2026/build.sh` into
`/home/buiksat/cce-tmlr-work/release/` (outside the repository).

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `main.pdf` | 931,804 | `4ef4ef3b9aa5436249101ea3b3e098dc9de73a0bac0f89dbc0568251b1784a14` |
| `source.zip` | 3,420,977 | `24f30b27a06eafc7d395e6149d9111f557c3d48f8360a1ba6fa30d8f3ceab868` |
| `supplement.zip` | 84,190,529 | `ea89c150b0db68ecd73020fd22226f01e8eae7be83f4e53fa3ddfcc038fcedd5` |
| `release_manifest.json` | 95,432 | SHA-256 `76a6dc89d5dfe2a5b0abf491dfe83508cf5293a8509a272cee0dd85b7063c107`; recorded in the repo at `submissions/tmlr_2026/release_manifest.json`; never hashes itself |

Both archives now **store** their members rather than deflating them, which is
why the two ZIP sizes jumped while nothing inside them changed; see section 9h.

`main.pdf`: 68 pages, US Letter, PDF 1.5, all fonts embedded subsets (Latin
Modern, the family `tmlr.sty` selects). Zero unresolved references, zero
unresolved citations, **zero overfull hboxes and zero overfull vboxes**, five
underfull hboxes and two underfull vboxes from float and line placement.
Deterministic: two independent builds of the same source produced identical
bytes. Every one of the 68 pages was rendered and inspected.

The page count rose from 66 and the byte count fell, both for the same reason:
the three generated evidence tables are no longer set at `\scriptsize` and
scaled down. They are landscape floats at the body font size now (section 9d),
which costs three float pages and stores less scaled content.

`source.zip`: 94 files, 3,408,765 bytes unpacked. It is the **project-local**
part of the compile closure — the manuscript sources, the generated table and
figure inputs, the venue template and the four vendored third-party packages —
plus the inputs pdfTeX never opens: `references.bib` and `tmlr.bst` for bibtex,
and the four licence texts. It is not the whole `.fls` closure: the 249 TeX
distribution files are recorded in `release_manifest.json` instead, not shipped.
Unpacking `source.zip` into an empty directory and running `latexmk -pdf
main.tex` reproduces `main.pdf` **byte for byte** (verified). It was 45 files
before section 9i vendored the packages.

`supplement.zip`: 140 members, 84,165,371 bytes unpacked and 84,190,529 bytes
stored — both read from the archive's own metadata, not from `du`, which counts
directory inodes. That is **84.2% of the venue's 100 MB limit**, with 15.8 MB
spare (15,809,471 bytes exactly); `package.check_archive_size` fails the build at the limit and warns
within 10% of it. The member count was 143 before section 9d dropped six
excluded legacy benchmark artifacts; it gained `tools/tex_conditionals.py` in
section 9e, `SOURCE_CLOSURE.json` in section 9f, and
`tools/numeric_context_pins.py` in section 9g. `bash verify.sh` from a clean
unpacked copy exits 0 on its gate and all four advertised checks. Two of its
files are anonymized packaging copies rather than original evidence bytes; see
section 9a.

## 5. Changed files

Tracked modifications:

```
.gitattributes
.github/workflows/transport-committed-evidence.yml
README.md
paper/EXPOSITION_REVISION.md
paper/main.tex
paper/transport_experiment.tex
paper/transport_experiment_appendix.tex
tests/test_transport_github_review_bundle.py
tools/verify_transport_committed_evidence.py
```

The repair pass that answered the independent review touched, on top of the
above: `.gitattributes` (new), the three workflow sidecar call sites plus the
CI-only `pyyaml` install, `paper/body_related.tex` (trailing blank line), the
extraction header comment in all fourteen extracted `paper/*.tex` sources,
`submissions/tmlr_2026/package.py` (anonymous transform and revision scan),
`submissions/tmlr_2026/supplement_README.md`,
`submissions/tmlr_2026/supplement_verify.sh`,
`submissions/tmlr_2026/release_manifest.json`,
`tools/transport_artifact_expectations.py`,
`tools/verify_tmlr_submission_numbers.py`, this report, and the new
`tests/test_tmlr_release_package.py`.

An eleventh pass, answering the eight findings collected in section 9j, changed
ten files and added none: `.gitattributes`,
`submissions/tmlr_2026/{package.py,README.md,release_manifest.json,
supplement_README.md,FINALIZATION_REPORT.md}`,
`tools/{anonymous_package_contract.py,numeric_context_pins.py,
verify_tmlr_submission_numbers.py}` and `tests/test_tmlr_release_package.py`.
Counted from `git diff --name-status`: **0 added, 0 deleted, 10 modified**. No
manuscript source changed, so `main.pdf` and `source.zip` are byte-identical to
the previous pass; `supplement.zip` changed because it carries the shipped
verifier, the pin module and the supplement README, all three of which this pass
edited.

A tenth pass, answering the seven findings collected in section 9i, added
`paper/texmf_vendor/` — 46 verbatim third-party package files, three licence
texts and a note explaining both — deleted
`submissions/tmlr_2026/external_tex_inputs.py`, and changed
`.github/workflows/transport-committed-evidence.yml`,
`paper/EXPOSITION_REVISION.md`,
`submissions/tmlr_2026/{build.sh,package.py,README.md,release_manifest.json,
FINALIZATION_REPORT.md}`,
`tools/{anonymous_package_contract.py,verify_tmlr_submission_numbers.py}` and
`tests/test_tmlr_release_package.py`. Fifty new files, one deleted, nine
changed. No manuscript source changed, and `main.pdf` is byte-identical again —
which is the point of the vendoring: it changed where the compiler read from,
not what it produced.

A ninth pass, answering the five findings collected in section 9h, added
`submissions/tmlr_2026/external_tex_inputs.py` — the digest record of every
compiled input no trusted TeX distribution supplies — and changed
`submissions/tmlr_2026/{package.py,README.md,release_manifest.json,
FINALIZATION_REPORT.md}`,
`tools/{anonymous_package_contract.py,numeric_context_pins.py,
verify_tmlr_submission_numbers.py}` and `tests/test_tmlr_release_package.py`.
Counted from `git diff --name-status`, that pass was **50 added, 1 deleted and
11 modified**. No manuscript source changed, so `main.pdf` was byte-identical
again; both archives changed size because their members are now stored rather
than deflated.

An eighth pass, answering the five findings collected in section 9g, added
`tools/numeric_context_pins.py` — the generated record of every pinned numeric
context — and changed `submissions/tmlr_2026/{package.py,release_manifest.json,
FINALIZATION_REPORT.md}`, `tools/verify_tmlr_submission_numbers.py` and
`tests/test_tmlr_release_package.py`. Six files, one of them new. No manuscript
source changed, so `main.pdf` and `source.zip` are byte-identical to the
previous pass; `supplement.zip` changes only because it carries the shipped
tools and the new pin record.

A seventh pass, answering the five findings collected in section 9f, changed
`paper/validate.py`, `submissions/tmlr_2026/{package.py,release_manifest.json,
supplement_README.md,FINALIZATION_REPORT.md}`,
`tools/verify_tmlr_submission_numbers.py` and
`tests/test_tmlr_release_package.py`. Seven files, no new files.

A sixth pass, answering the nine findings collected in section 9e, added
`tools/tex_conditionals.py` and changed `paper/validate.py`,
`submissions/tmlr_2026/{package.py,README.md,supplement_README.md,
supplement_verify.sh,release_manifest.json,FINALIZATION_REPORT.md}`,
`tools/{anonymous_package_contract.py,verify_tmlr_submission_numbers.py}` and
`tests/test_tmlr_release_package.py`. Ten files, one of them new. No manuscript
source changed in this pass, so no rendered byte of the paper changed for any
reason other than the new shipped tool appearing in the supplement.

A fifth pass, answering the eleven findings collected in section 9d, changed
`.github/workflows/transport-committed-evidence.yml`, `README.md`,
`paper/appendix_deferred.tex`, `paper/appendix_protocol.tex`,
`paper/notation.tex`, `paper/transport_experiment.tex`,
`paper/transport_experiment_appendix.tex`, `paper/transport_theory.tex`,
`submissions/tmlr_2026/{main.tex,build.sh,package.py,README.md,
supplement_README.md,supplement_verify.sh,release_manifest.json}`,
`tools/{anonymous_package_contract.py,transport_artifact_expectations.py,
verify_tmlr_submission_numbers.py}`, `tests/test_tmlr_release_package.py` and
this report. Twenty files, no new files.

A fourth pass, answering the required-package finding in section 9c, changed
`tools/anonymous_package_contract.py`,
`tools/verify_tmlr_submission_numbers.py`,
`tools/transport_artifact_expectations.py`,
`submissions/tmlr_2026/supplement_verify.sh`,
`submissions/tmlr_2026/supplement_README.md`,
`submissions/tmlr_2026/release_manifest.json`,
`tests/test_tmlr_release_package.py` and this report.

A third pass, answering the packaged-verifier trust-boundary finding in section
9b, added `tools/anonymous_package_contract.py` and changed
`submissions/tmlr_2026/package.py`, `submissions/tmlr_2026/supplement_verify.sh`,
`submissions/tmlr_2026/supplement_README.md`,
`submissions/tmlr_2026/release_manifest.json`,
`tools/transport_artifact_expectations.py`,
`tools/verify_tmlr_submission_numbers.py`,
`tests/test_tmlr_release_package.py` and this report.

New files:

```
paper/notation.tex                    paper/body_intro.tex
paper/body_related.tex                paper/body_conclusion.tex
paper/broader_impact.tex              paper/availability.tex
paper/appendix_rates.tex              paper/appendix_deferred.tex
paper/appendix_protocol.tex           paper/appendix_onesided_proof.tex
paper/appendix_cg.tex                 paper/appendix_twosided.tex
paper/appendix_ggn.tex                paper/appendix_expfam.tex
paper/tmlr_style/{tmlr.sty,tmlr.bst,fancyhdr.sty,LICENSE,PROVENANCE.md}
submissions/tmlr_2026/{main.tex,build.sh,package.py,README.md,PORTAL.md,
                      FINALIZATION_REPORT.md,release_manifest.json,
                      supplement_README.md,supplement_verify.sh,
                      external_tex_inputs.py}
tools/verify_tmlr_submission_numbers.py
tools/transport_artifact_expectations.py
tools/anonymous_package_contract.py
tools/tex_conditionals.py
tools/numeric_context_pins.py
tests/test_tmlr_release_package.py
.gitattributes
paper/texmf_vendor/            46 vendored package files, 3 licence texts,
                               and VENDORED-PACKAGES.md
```

`submissions/tmlr_2026/external_tex_inputs.py` was added in the ninth pass and
deleted in the tenth: it held the digest pins that admitted external inputs from
a user tree, and section 9i removes that route entirely.

## 6. Scientific-exposition edits and formal-block comparison

### Structural: one copy of the mathematics

`paper/main.tex` went from 4,052 lines to a 167-line AISTATS shell. Everything
it used to hold is now in shared files that both entry points `\input`. The
mapping is tabulated in `paper/EXPOSITION_REVISION.md`.

The extraction was mechanical. Verification, run **before** any content change:

- AISTATS rebuild after extraction: 64 pages, five overfull hboxes, exit 0 —
  identical to the pre-extraction build.
- `pdftotext -layout` output of the two PDFs: **byte-identical**.
- `paper/validate.py`: 261 labels, 184 resolved reference targets, 37 cited
  keys, zero unresolved, before and after.

After applying the four corrections and the three experiment-prose edits, a
word-level diff of the two AISTATS PDFs (reading order, de-hyphenated) shows
**56 changed regions, every one of them accounted for**: the seven intended
edits plus float repositioning and column reflow. No formal block moved
position, no equation changed, and no number changed.

### Formal blocks: before and after

178 formal environments, 155 equation/align environments, three algorithms, 261
labels and 37 citation keys. Counts before = counts after.

**One lemma statement changed, and it is the approved correction 1 below.**
`lem:cg` carries the fixed-tolerance qualifier, so its statement text is not the
text it had at START. That is the whole of the exception: it is the only
theorem, lemma, corollary, proposition or assumption *statement* that differs,
and the narrower claims all still hold across every formal block including
`lem:cg` — no equation changed, no conclusion changed, no quantifier,
filtration, event condition, constant or sign changed, and no proof obligation
was added or removed. The change is a scope qualifier on when `α_t` is
horizon-independent; it constrains the lemma rather than strengthening it.

The `\iflegacyextras` guards do not alter any block they wrap; they only decide
whether an entry point typesets it.

### The four inherited corrections, all still needed at START and all applied

1. **`lem:cg`.** Was: "here `W_t = n` for unrescaled windowed/refresh buffers,
   giving `κ̄_t` and `α_t` independent of `T`". `α_t = √((1+ε̄_t)/(1−ε̄_t))` is a
   function of the tolerance, not of `κ̄_t`, so a fixed buffer bounds only
   `κ̄_t`. Now says the condition-number bound is horizon-independent, and that
   `α_t` is horizon-independent only under a fixed target tolerance or a
   tolerance sequence uniformly bounded below one. No equation touched.
2. **"Cost of the analyzed configuration".** The simplified `O(K t^{3/2})` and
   `O(K T^{5/2})` counts silently dropped `log(1/ε̄_t)`. Now qualified by a fixed
   target tolerance and fixed problem constants, with the log factor required
   for a varying schedule, and restated as sufficient width-solve budgets rather
   than lower bounds on the work CG performs.
3. **"Computable Curvature Operator".** Was "cost `O(It)` CVPs per round"; that
   is one action's solve. Now: one action's solve is `O(It)` sample-CVPs, a
   round with `K_t` separate common-budget solves is `O(K_t I t)`, and an
   explicit final original-system residual check is charged separately at `t−1`
   further sample-CVPs per checked action.
4. **Detailed pseudocode.** `+log[` → `+\log[`. Only the backslash was inserted.
   Confirmed in the rendered PDF at 300 dpi: upright operator, not italic.

### Experiment-section accuracy edits

- The `e^{D̄_t^Q/2}` range `1.02`–`1.18` now says explicitly that it is the
  `T = 1000` cells; previously the horizon scoping was carried only by the
  paragraph opening.
- "The dense endpoint, frozen reference, and naive-current policies have lower
  sample means in every condition" → "All three comparison policies have lower
  sample-mean pseudo-regret than transport Hessian in every reported condition
  at this horizon."
- Added the endpoint ratio `D̄_t^Q/d_Th = 3.07×10⁵`–`2.24×10⁶` at `T = 1000`, so
  the abstract's five-to-six-orders-of-magnitude statement is checkable from the
  body rather than only from the appendix table.
- Added, at the end of the policy-outcomes paragraph: these outcomes do not show
  a causal or uniform advantage for full curvature, and the reverse ordering is
  specific to this environment, certificate and horizon.
- `body_related.tex`: a single-author citation's verb ("control" → "controls").

No new analysis was run and no existing supported claim needed correction.

### Cut record

| Cut from the TMLR submission | Why | Dependency chain checked |
|---|---|---|
| `paper/legacy_experiments.tex` (`app:legacy-evidence`), with `tables/linear_bound_ratios.tex` and `tables/autodiff_ggn_summary.tex` | Disconnected legacy benchmarks. They summarize studies designed for the one-sided theorem, none of which executes the transported score or records its certificates. The submission's empirical content is restricted to the completed scaled-tanh study. | Three references, all prose, from `body_intro.tex`, `body_conclusion.tex` and `availability.tex`. Each is replaced under `\iflegacyextras` by an explicit statement that earlier studies are excluded and are not evidence. Nothing formal depends on it. |
| `lem:pcg` (fixed-preconditioner CG accuracy) and its proof | Redundant derivation. The study uses dense Cholesky, and `lem:cg` — which *is* retained and *is* referenced by `lem:bonus`, `cor:lam-observable` and `cor:gammahat` — carries the CG interface. | `lem:pcg` and all four of its equation labels are referenced nowhere. Verified by a full cross-reference graph over all seven source files. |
| `prop:offdiag-witness` (off-diagonal linear-Gram witness) and its proof | Disconnected diagnostic. It is a 2-D counterexample about *diagonal* operator approximations; the submission claims nothing about diagonal operators, and keeping it invites a curvature-superiority reading the evidence does not support. | Referenced nowhere. Same cross-reference graph. |

Everything else was kept. TMLR does not count appendices against length, so
there was no pressure to cut proofs, and the retained one-sided dynamic fallback
(referenced from `transport_theory.tex` as the applicable fallback when a lower
operator factor is unavailable) pulls in nearly all of the remaining appendix by
a live reference chain. All three cut blocks remain in the repository and in the
AISTATS entry point.

## 7. Numerical provenance

Single evidence source:
`results/derived/transport_instantiation/full_aggregate.json`, SHA-256
`0ddebd4915dd2e264e24b7b25047d24f86c3cdf63930a1e6df77585e0b97de02`, input-set
digest `4af9f51467981326c4f99ef171dc21e3fb27beb4d519b65d28d18f678e65ef66`.
Configuration `experiments/configs/transport_instantiation.yaml`, SHA-256
`d6f6c0de47651a7e6a291f63ba609654afd5cff6cc13d11722d9fae587e7abdd`.

Provenance identities kept distinct, none replaced by START:

| Identity | Value |
|---|---|
| Original execution revision (`aggregate.git_revision`) | `0cd6264c1f8b8751728f3c4a198207e8289aed74` |
| Selection freeze (`selection_sha256`) | `8c16bec7cc220109df3fd7173c3d06ae6c6e1b95e9db5bc5b8c3377b3564f6f4` |
| Renderer / review revision (`IMPLEMENTATION_COMMIT`) | `93eaa537d2702d5d18b05905913b0b879e3d608f` |
| Review-bundle base | `47037a2df6b81befd4a0cb3c5974e3565d8f61b6` |
| Publication candidate (this work) | `b99b682…` plus one local finalization commit |

`tools/verify_tmlr_submission_numbers.py` is the ledger, and it is executable
rather than a table in a document. Each entry records manuscript location, the
displayed literal, source path and SHA-256, selector, units, aggregation rule,
population, unrounded value and display rounding. It re-derives every value from
the locked aggregate, requires agreement to within half a unit in the last
displayed place, and requires the literal to occur in the file it is attributed
to.

Result in the repository: **257 PASS, 0 FAIL, 3 NOT EXECUTED**, 260 checks over
67 ledger entries. Run inside a clean unpack of the supplement it is **279 PASS,
16 PASS_ANON, 2 NOT EXECUTED**: the package adds the anonymous-package contract
and the compiled-source-closure contract, and loses the repository's third
NOT_EXECUTED, which is the standing note that a repository tree has no compiler
manifest and is therefore a preflight rather than a certification.
The two are stated, not hidden: the deterministic paired bootstrap resamples
per-seed values that live in the uncommitted raw tree, and the raw bytes behind
the aggregate's SHA-256 inventory are absent. Neither is reported as a pass.

### Coverage, not just correctness

The ledger said that the numbers it listed were right. It said nothing about
numbers it did not list, and an independent review found that gap was real: the
horizon grid `{250,500,1000}` and the deterministic-cap range `500--2,000` were
printed in the manuscript and checked by nothing, so editing them to
`{251,500,1000}` and `501--2,001` left the shipped verification green.

Two things changed. First, the omissions themselves are now entries derived
from the frozen configuration: each horizon from `base.horizons[i]`, each target
label from `base.target_D[i]`, the primary horizon from
`base.reporting.primary_horizon`, the Clopper--Pearson level from
`base.statistics.coverage_level`, the bootstrap level from
`base.statistics.paired_bootstrap_level`, the ratio tolerance from
`base.numerics.ratio_denominator_tolerance`, the cap range as `2 × min` and
`2 × max` of the horizon grid, and every restatement of the seed count and the
population sizes.

Second, and more to the point, the omission *class* is closed. A literal audit
now reads the submitted sources, masks the spans that ledger entries account for
and the spans explicitly declared non-empirical, and fails on whatever numeric
literal is left over. Adding an unchecked number to a results section is a
failure, not an omission. The pieces:

| Rule | What it enforces |
|---|---|
| Audited sources | The compiled source closure — the LaTeX recorder's own list of what pdfTeX opened, 43 inputs — plus the supplement README. In a repository tree, where no build has run, a transitive `\input` walk covering braced, unbraced and `\include` forms stands in as a preflight |
| Visible bytes only | Comments are stripped and the venue switch resolved before any match, in the audit and in the literal-occurrence check both |
| Per-literal classification | 76 `(file, literal)` pairs in 8 categories, each with a written reason, an exact occurrence count **and a pinned digest over the ordered contexts of those occurrences** |
| Declared phrase occurrences | 74 `(file, phrase)` declarations, likewise counted and context-pinned, covering the ledger sentences and six non-empirical phrases. A phrase in a file it is not declared for is an unclassified literal |
| Regenerated evidence | The 6 artifacts, by byte identity against the locked aggregate; the status is rejected unless a matching sidecar backs it |
| Structural checks | `paper/macros.tex` must be declarations with no numeric literal at all; every body cell of the symbolic rate table is **parsed** as an asymptotic rate and the parsed cells must equal a pinned list |
| Typeset artifacts | Every `\input` from `tables/` or `figures/` must be a regenerated evidence artifact or the one declared symbolic rate table |
| No stale exemptions | A classification naming a file outside the closure is itself a failure |
| Cost illustration | The one arithmetic example in the theory appendices (`K=10`, `I=25`, `m_t=256` giving `64,000` and `66,560`) is checked arithmetically |

Everything else fails closed. Table and figure cells are not listed literal by
literal, and deliberately so: `tools/transport_artifact_expectations.py` rebuilds
all 21 of those files from the locked aggregate and requires byte identity,
which binds every cell to a committed source more tightly than a per-literal
entry could.

Adversarial coverage, each asserting the audit fails: the reviewer's two exact
grid mutations, a changed target label, a changed confidence level, a changed
seed count, a changed run count, a changed ratio tolerance, a changed parameter
count in the introduction, a brand-new unledgered number, a study value moved
into a theory source, a `%`-commented copy of a replaced value, a leading-dot
decimal, a newly `\input` source, a changed supplement-README count both in the
repository and inside a clean unpack of the built archive, and an undeclared
typeset table. A positive control asserts the untouched throwaway tree audits
clean, so each of those is a transition and not one more failure on a pile.

One defect surfaced while building this and is recorded rather than quietly
fixed: the first version of the typesetting mask treated whitespace between a
number and its unit as allowed, so `126.7 in the study` was blanked as "126.7
inches" and the theory-source rule silently passed a planted study value. The
mask now requires the unit to be adjacent, which is how every length in these
sources is written, and a test asserts both directions.

Aggregation units are kept apart in the ledger and in the prose: trajectory
means, pooled seed-round medians, pooled eligible seed-checkpoint ratios, and
medians of within-trajectory maxima each carry their own population. The paper
continues to state that reusing base seeds across cells supports paired
comparisons within a condition and not a pooled sample of 600 independent runs.

The rejected bootstrap-zero-exclusion count was **not** restored. No variance
was fabricated, no equivalence was inferred from similar means, and no optional
terminal quantiles were added.

All 21 generated tables, figures and CSVs regenerate **byte-identically** from
the locked aggregate. No locked CSV was overwritten, no expected hash was
changed, and no tolerance was loosened.

## 8. Verification: what ran, what it returned

### Declared native runtime: BLOCKED, and not by anything in this work

`BUCK2_SETUP.md` declares Buck2 against a host monorepo checkout. It does not
work on this host:

```
$ buck2 targets //paper:validate //tools:verify_transport_committed_evidence
Error parsing root//paper
  4: Error evaluating module: `prelude//configurations/util.bzl`
  5: error: Unexpected parameter named `root_values`
Command failed: Failed to parse 1 package        (exit 3)
```

The repository pins buck2 `4b1af7328ff43271e1a3f23d7587680dbbb23c77` via
DotSlash, and `.buckconfig` points the `prelude` cell at a live symlink into the
host monorepo. That prelude has moved ahead of the pinned binary and now passes
`root_values` to `ConfigurationInfo`, which the pinned buck2 rejects. The build
graph cannot be parsed, so no Buck target can be analyzed, built or tested.

This is pre-existing and independently recorded: `review/realistic_transport/REPAIR_CANDIDATE.md`
already notes a preserved baseline log containing "exit 3, `NO TESTS RAN`, and
the Buck/Prelude `root_values` error". Fixing it needs either a newer pinned
buck2 or an older host checkout, both of which are dependency mutations outside
this task.

### Portable route, labelled as such

Not the declared build. Assembled from the repository's own pinned dependency
set: the checked-in wheels `third_party/wheels/numpy-2.2.3` and
`scipy-1.13.1` (both verified against `third_party/wheels/SHA256SUMS`), plus the
host monorepo's declared `pytest 7.2.2`, `psutil 7.2.2`, `scikit-learn 1.5.1`,
`joblib 1.5.3`, `threadpoolctl 3.5.0` sources, on `PYTHONPATH`. CPython
`3.12.14+meta`. This is the same manual-`PYTHONPATH` fallback the repository's
own repair record describes. It is a portable reviewer route, not proof that the
Buck preparation closure builds.

### Results

Every number below comes from the R16 run of this pass, read from the logs of
the final amended commit and named row by row. Nothing is carried forward from
an earlier pass. Where a figure cannot be stated in a file that is itself part
of the commit being measured -- the project-revision count is the only one --
the row says so and names the log instead.

| Check | Command | Exit | Result |
|---|---|---:|---|
| Static TeX validation, legacy entry point | `python3 paper/validate.py` | 0 | 261 labels, 184 ref targets, 38 cite keys, 0 unresolved |
| Static TeX validation, staged TMLR entry point | `python3 paper/validate.py <out>/src/main.tex` | 0 | 249 labels, 178 ref targets, 38 cite keys, 0 unresolved |
| Numerical-provenance ledger | `python3 tools/verify_tmlr_submission_numbers.py` | 0 | 67 entries, 260 checks: 257 PASS, 3 NOT EXECUTED, 0 FAIL |
| Every pinned semantic unit, printed for review | `… --print-contexts` | 0 | 74 phrase pins and 76 `(file, literal)` pins over 485 distinct units, each with the complete enclosing unit and the category rationale, plus 23 whole-file bindings |
| Artifact regeneration | `python3 tools/transport_artifact_expectations.py --root .` | 0 | 21/21 byte-identical, nothing written |
| Detached committed-evidence verifier | `python3 tools/verify_transport_committed_evidence.py` | 0 | 98 PASS, 39 PASS_RECOMPUTED, 2 STRUCTURAL_PASS, 2 KNOWN_DIVERGENCE, 4 NOT_EXECUTED, **0 FAIL** |
| Repository test suites | `TMLR_OUT=… pytest -q tests experiments/tests` | 0 | 643 passed, 0 skipped, read from the final-SHA run in `R16-pytest-repo-postamend.log` |
| Deferred realistic extension | `pytest -q experiments/realistic_transport` | 0 | 297 passed — a fixture suite, **not** clearance |
| Whitespace, exact range | `git diff --check b99b682..HEAD` | 0 | clean |
| Submission build | `TMLR_OUT=… bash submissions/tmlr_2026/build.sh` | 0 | 68 pages, staged entry point validated, every reference resolved, compiled layout gate clean over 38 of 89 recorded inputs (2 venue-template, 3 generated-figure and 46 vendored-package files exempt by pinned digest), 89 compiled inputs recorded in `SOURCE_CLOSURE.json`, **249 external compiled inputs, 0 admitted by digest**, shipped tool digests matched, scrub clean, identity scan clean over every project revision the checkout knows. The scanner's population is `package.project_revisions`: the union of `RECORDED_PROJECT_REVISIONS`, `git rev-list --all`, `git reflog --all` and `HEAD`. Amending adds a reflog entry, so that count rises by one with every amendment and cannot be stated here without the statement invalidating itself; the exact figure for this candidate is in `R16-build-postamend.log`, which is written after the final commit exists |
| Build determinism | second build into a second directory | 0 | all four deliverables byte-identical, `release_manifest.json` included |
| Build into a symlink-booby-trapped output | four deliverable paths and `src/` pre-placed as symlinks | 0 | every linked target byte-unchanged, every deliverable a real file, bytes identical to the clean build |
| Release-package and anonymization tests | `TMLR_OUT=… pytest -q tests/test_tmlr_release_package.py` | 0 | 521 passed, 0 skipped, read from the final-SHA run in `R16-release-package-suite-postamend.log` |
| Anonymous-package contract, repository mode | `python3 tools/anonymous_package_contract.py --root .` | 0 | 5/5 pinned provenance and shipped-tool checks; repository is not a packaged tree |
| Anonymous-package contract, required mode in the repository | same, with `--require-package` | **1** | correctly refuses to treat the repository as a package |
| Release manifest still describes a rebuild | `package.py --compare-manifest` | 0 | byte-identical over all 10 record classes, not only `deliverables` |
| `source.zip` clean rebuild | unpack + `latexmk` in an empty directory | 0 | byte-identical PDF |
| `supplement.zip` clean verify | unpack + `bash verify.sh` | 0 | gate + four checks pass; 279 PASS, 16 PASS_ANON, 2 NOT EXECUTED, 0 FAIL; 43 evidence files against their sidecars, 4 more against the pinned contract |
| Every archive member is STORED | shipped scanner over both archives | 0 | 94 + 140 members, `compress_type == 0` on every one, `compress_size == file_size` |
| Supplement size against the venue limit | `package.check_archive_size` | 0 | 84,190,529 bytes, 84.2% of 100,000,000, 15,809,471 bytes spare |
| Supplement mutated: content + sidecar + declaration | `bash verify.sh` | **1** | rejected at the gate |
| Supplement with its declaration deleted, originals restored | `bash verify.sh` | **1** | rejected at the gate |
| Supplement with an unsidecarred evidence file added | `bash verify.sh` | **1** | rejected by the sidecar-coverage check |
| Supplement with a provenance `artifact_sha256` zeroed | `bash verify.sh` | **1** | rejected by the pinned provenance check |
| Supplement README count changed to `2,401` in a clean unpack | `bash verify.sh` | **1** | rejected by the ledger |
| One byte changed in a recorded compiled input | `bash verify.sh` | **1** | rejected by the closure byte binding |
| `SOURCE_CLOSURE.json` deleted from an otherwise clean unpack | `bash verify.sh` | **1** | rejected: the manifest is required in package mode |
| An unledgered `42.7` planted in a shipped compiled source | `bash verify.sh` | **1** | rejected twice over: the closure byte binding, and "1 unclassified literal(s) with no ledger entry and no declared classification" |
| A pinned sentence reworded around an allowed number | `bash verify.sh` | **1** | rejected by the semantic-unit pin, with the count unchanged |
| A claim reversed 60 characters past the nearest number | `bash verify.sh` | **1** | rejected by the semantic-unit pin; the old ±40 context was byte-identical before and after |
| A source edited **and its pin regenerated** inside the unpack | `bash verify.sh` | **1** | rejected by the shipped-tool digest in the contract module, before a single pin is read |
| `"bytes": true` in the closure manifest | `bash verify.sh` | **1** | rejected by the exact scalar type check; `isinstance(True, int)` would have passed it |
| A nested `paper/parts/smuggled.tex` added to the unpack | `bash verify.sh` | **1** | rejected by the recursive completeness sweep |
| A symbolic rate-table cell changed | `bash verify.sh` | **1** | rejected by the structural cell parser |
| A recorded external input from a user tree | `recorder_inputs` | **raises** | rejected: "not from a trusted system TeX distribution". There is no digest that admits it |
| A source or supplement archive over the venue limit | `package.check_archive_size` in the staging area | **10** | the prior release is byte-identical afterwards; nothing was published |
| A staged manifest that disagrees with the bytes beside it | `package.check_pending_release` | **12** | same: the staging area is removed and the prior release stands |
| A rewritten `pgfplots.sty` digest in `SOURCE_CLOSURE.json` | `bash verify.sh` | **1** | rejected against the pinned non-supplement contract; the supplement has no bytes to recompute from |
| The `main.bbl` closure entry deleted | `bash verify.sh` | **1** | rejected: no archive carries it, so only the mandatory-entry check can see it |
| `"schema_version": true` in the closure manifest | `bash verify.sh` | **1** | rejected by the exact integer type check |
| A nested `submissions/tmlr_2026/smuggled.tex` in the unpack | `bash verify.sh` | **1** | rejected by the sweep over every shipped source root |
| TMLR-only missing citation | `bash submissions/tmlr_2026/build.sh` | **7** | caught by staged static validation, before any compile |
| The same citation with static validation stubbed out | `bash submissions/tmlr_2026/build.sh` | **8** | caught by the compiled-log gate on natbib's own warning, before any deliverable is written |
| All SHA-256 sidecars in the repository | `sha256sum -c`, from each sidecar's own directory | 0 | 71 sidecars plus `code_mit_2026/SHA256SUMS` |
| PDF structure, fonts, metadata, references | `qpdf --check`, `pdfinfo`, `pdffonts`, `pdftotext` | 0 | no syntax errors, all fonts embedded subsets, every metadata field empty, no trailer `/ID`, no banner, zero `??` / `[?]` / `(?)` placeholders |
| Archive CRC, paths, duplicates, symlinks, identity | shipped scanner over every extracted member, plus a raw-byte pass | 0 | 0 findings in either archive, scanned against the full revision population described in the build row; the pre-amend run is `R16-archive-scan.log` and the final-commit run is `R16-archive-scan-postamend.log`; no duplicate name, no absolute or `..` path, no symlink member |
| Protected inventory | blob-for-blob against START, from the final amended commit | 0 | see `R16-protected-inventory.log`; 0 differences |
| Visual inspection | all 68 rendered pages | — | `main.pdf` is byte-identical to the previously inspected candidate (`4ef4ef3b…`) and no manuscript source changed in this pass, so the earlier full-page inspection stands; **not re-run** |
| Legacy AISTATS entry point, in a disposable copy | `latexmk -pdf paper/main.tex` in a `git archive` tree | — | **not re-run this pass**: no file under `paper/` changed, so an earlier pass's 64 pages and five overfull hboxes still describe it |

Durable logs under `/home/buiksat/cce-tmlr-work/logs/`, all with the `R16-`
prefix: `R16-build-release.log`, `R16-build-postamend.log`,
`R16-build-determinism.log`, `R16-symlink-build.log`, `R16-paper-validate.log`,
`R16-paper-validate-staged.log`, `R16-ledger.log`, `R16-ledger.json`,
`R16-pinned-contexts.log`, `R16-artifact-regen.log`,
`R16-detached-verifier.log`, `R16-verifier.json`,
`R16-git-diff-check-range.log`, `R16-focused-1-firstrun.log`,
`R16-focused-2.log`, `R16-release-package-suite.log`,
`R16-release-package-suite-postamend.log`, `R16-pytest-repo.log`,
`R16-pytest-repo-postamend.log`, `R16-pytest-realistic.log`,
`R16-contract-repo-optional.log`, `R16-contract-repo-required.log`,
`R16-manifest-compare.log`, `R16-manifest-compare-postamend.log`,
`R16-sourcezip-build.log`, `R16-supplement-verify-clean.log`,
`R16-stored-members.log`, the twenty-four `R16-attack-*.log` files,
`R16-sidecars.log`, `R16-pdf-checks.log`, `R16-archive-scan.log`,
`R16-archive-scan-postamend.log`, `R16-protected-inventory.log`,
`R16-changed-from-START.txt`, the reproductions `R16-repro-1a.log`,
`R16-repro-1b.log`, `R16-repro-2.log` and `R16-repro-2_regular.log` with their
`R16-fixed-*.log` counterparts, and the exit-code ledger `R16-EXITCODES.txt`.
Earlier prefixes remain on disk as the record of earlier passes; section 9m
cites the `R13-` set and nothing in this table does.

The previous pass's logs, superseded but kept, had the `R15-`
prefix: `R15-build-release.log`, `R15-build-postamend.log`,
`R15-build-determinism.log`, `R15-symlink-build.log`, `R15-paper-validate.log`,
`R15-paper-validate-staged.log`, `R15-ledger.log`, `R15-ledger.json`,
`R15-pinned-contexts.log`, `R15-artifact-regen.log`,
`R15-detached-verifier.log`, `R15-verifier.json`,
`R15-git-diff-check-range.log`, `R15-focused-1-firstrun.log`,
`R15-focused-2.log`, `R15-release-package-suite.log`,
`R15-release-package-suite-postamend.log`, `R15-pytest-repo.log`,
`R15-pytest-repo-postamend.log`, `R15-pytest-realistic.log`,
`R15-contract-repo-optional.log`, `R15-contract-repo-required.log`,
`R15-manifest-compare.log`, `R15-manifest-compare-postamend.log`,
`R15-sourcezip-build.log`, `R15-supplement-verify-clean.log`,
`R15-stored-members.log`, the twenty-four `R15-attack-*.log` files,
`R15-sidecars.log`, `R15-pdf-checks.log`, `R15-archive-scan.log`,
`R15-archive-scan-postamend.log`, `R15-protected-inventory.log`,
`R15-changed-from-START.txt`, the reproductions `R15-repro-1.log`,
`R15-repro-2.log`, `R15-repro-3.log` and `R15-repro-4.log` with their
`R15-fixed-*.log` counterparts, and the exit-code ledger `R15-EXITCODES.txt`.
Earlier prefixes remain on disk as the record of earlier passes; section 9m
cites the `R13-` set and nothing in this table does.

The previous pass's logs, superseded but kept, had the `R14-`
prefix: `R14-build-release.log`, `R14-build-postamend.log`,
`R14-build-determinism.log`, `R14-symlink-build.log`, `R14-paper-validate.log`,
`R14-paper-validate-staged.log`, `R14-ledger.log`, `R14-ledger.json`,
`R14-pinned-contexts.log`, `R14-artifact-regen.log`,
`R14-detached-verifier.log`, `R14-verifier.json`,
`R14-git-diff-check-range.log`, `R14-focused-1.log`,
`R14-release-package-suite.log`, `R14-release-package-suite-postamend.log`,
`R14-pytest-repo.log`, `R14-pytest-repo-postamend.log`,
`R14-pytest-realistic.log`, `R14-contract-repo-optional.log`,
`R14-contract-repo-required.log`, `R14-manifest-compare.log`,
`R14-sourcezip-build.log`, `R14-supplement-verify-clean.log`,
`R14-stored-members.log`, the twenty-four `R14-attack-*.log` files,
`R14-sidecars.log`, `R14-pdf-checks.log`, `R14-archive-scan.log`,
`R14-protected-inventory.log`, `R14-changed-from-START.txt`, the five
reproductions `R14-repro-1a.log`, `R14-repro-1b.log`, `R14-repro-1c.log`,
`R14-repro-2.log` and `R14-repro-3.log` with their `R14-fixed-*.log`
counterparts, and the exit-code ledger `R14-EXITCODES.txt`.
The `R13-` set remains on disk as the record of the previous pass and is what
section 9m's revision-count correction cites.

The previous pass's logs, superseded but kept, had the `R13-`
prefix: `R13-build.log`, `R13-build-postamend.log`,
`R13-build-determinism.log`, `R13-symlink-build.log`, `R13-paper-validate.log`,
`R13-paper-validate-staged.log`, `R13-ledger.log`, `R13-ledger.json`,
`R13-pinned-contexts.log`, `R13-artifact-regen.log`,
`R13-detached-verifier.log`, `R13-verifier.json`,
`R13-git-diff-check-range.log`, `R13-focused-1.log`,
`R13-release-package-suite.log`, `R13-release-package-suite-postamend.log`,
`R13-pytest-repo.log`, `R13-pytest-repo-postamend.log`,
`R13-pytest-realistic.log`, `R13-contract-repo-optional.log`,
`R13-contract-repo-required.log`, `R13-manifest-compare.log`,
`R13-sourcezip-build.log`, `R13-supplement-verify-clean.log`,
`R13-stored-members.log`, the twenty-four `R13-attack-*.log` files,
`R13-sidecars.log`, `R13-pdf-checks.log`, `R13-archive-scan.log`,
`R13-protected-inventory.log`, `R13-changed-from-START.txt`, the six
reproductions `R13-repro-1.log` through `R13-repro-5.log` with their
`R13-fixed-*.log` counterparts, and the exit-code ledger `R13-EXITCODES.txt`.
The `R12-` set remains on disk as the record of the previous pass.

The previous pass's logs, superseded but kept, had the `R12-`
prefix: `R12-build.log`, `R12-build-regate.log`, `R12-build-determinism.log`,
`R12-symlink-build.log`, `R12-paper-validate.log`,
`R12-paper-validate-staged.log`, `R12-ledger.log`, `R12-ledger.json`,
`R12-pinned-contexts.log`, `R12-artifact-regen.log`,
`R12-detached-verifier.log`, `R12-verifier.json`,
`R12-git-diff-check-baseline-to-worktree.log`, `R12-git-diff-check-range.log`,
`R12-focused-gate-publish.log`, `R12-release-package-suite.log`,
`R12-release-package-suite-postamend.log`, `R12-pytest-repo.log`,
`R12-pytest-realistic.log`, `R12-contract-repo-optional.log`,
`R12-contract-repo-required.log`, `R12-manifest-compare.log`,
`R12-sourcezip-build.log`, `R12-supplement-verify-clean.log`,
`R12-stored-members.log`, the twenty-four `R12-attack-*.log` files,
`R12-sidecars.log`, `R12-pdf-checks.log`, `R12-archive-scan.log`,
`R12-publish-faults.log`, `R12-manifest-gate.log`, the three reproductions
`R12-repro-publish.log`, `R12-repro-rollback.log` and `R12-repro-manifest.log`,
`R12-firstrun-failures-NOTE.txt`,
`R12-firstrun-failure-extract-grep.txt`, `R12-protected-inventory.log`,
`R12-changed-from-START.txt`, and the exit-code ledger `R12-EXITCODES.txt`.
Every claim in this report refers to that run; the earlier `final-*`, `r3-*`,
`r4*`, `R5-*` through `R11-*` files remain on disk as the record of the earlier
passes and are not cited here as evidence for the current state.

Honesty notes about the ledger. The R12 one *is* a defect in the candidate and
was found by a failing run; the rest are not:

- The first full suite run of this pass failed: 24 failed / 381 passed in the
  release-package suite, 24 failed / 503 passed in the combined one. 23 were
  tests still calling `check_pending_release(pending, manifest)` after its
  second argument became the anonymization transforms, and one pinned the old
  crash-consistency docstring phrase. Repairing them found something worse: the
  rewritten gate had dropped the shipped-closure check, so a supplement
  carrying a drifted `SOURCE_CLOSURE.json` with a manifest derived from it
  would have published. See section 9k, finding 2.
  **The original stdout of both failing runs was overwritten in place by the
  green rerun and is gone.** `R12-firstrun-failures-NOTE.txt` records the exact
  observed summaries and says so; `R12-firstrun-failure-extract-grep.txt` is a
  grep of the failing log captured while it still existed, which is an extract,
  not the run. Do not read the current
  `R12-release-package-suite.log` as the first run.
- A mid-pass status note reported the 24-case adversarial battery complete when
  9 cases had not yet run. The note was wrong and the ledger records the
  genuine 24/24 completion, verified against the log files and the process
  table rather than the note.

- `R5-EXITCODES.txt` preserved a failing first archive scan. That scan was an
  ad-hoc script of mine that tested abbreviated revisions as raw substrings,
  without the hex-run boundaries the shipped scanner uses, so five 7-character
  prefixes matched *inside* 64-hex content digests in the 77 MB aggregate. Every
  scan since uses `package.scan_for_identifiers` itself plus a boundary-correct
  raw pass, and reports 0 findings.
- An early R6 run of `pytest -q tests experiments/tests` reported no skips, and
  that was misleading rather than good news: the archive integration tests fell
  back to a **stale** default output directory left by an older default-path
  build. Every recorded run since binds `TMLR_OUT` to the release that pass
  actually built. CI does the same and fails the step if the "no built release
  directory" skip message appears.
- `R8-EXITCODES.txt` keeps two preserved exit-`1` lines from that pass: a test
  fixture assembled a package without `SOURCE_CLOSURE.json` and the new strict
  contract correctly refused it. That was a fault in my fixture, not in the
  candidate, and it is recorded rather than erased.
- One R11 run failed before the recorded one, and it was mine. The first full
  release-package suite reported nine failures, every one stale test scaffolding
  rather than a product defect: a fixture helper that appended the mandatory
  closure entries on top of a fixture that now already contains all 89, a
  `mkdir(parents=True)` on a directory the completed fixture already creates,
  and two assertions naming a check I had renamed. The first run is kept as
  `R11-release-package-suite-firstrun.log`; the rerun after fixing the fixtures
  is the recorded one.
- Three R10 runs failed before the recorded one, and all three were mine.
  `R10-EXITCODES.txt` records them. The first build could not name two external
  inputs it had just accepted, because the naming table read the lexical
  kpsewhich values and the recorder had written resolved ones. The first clean
  supplement verification failed on `tmlr.bst`, which I had put in the mandatory
  compiler-input list even though bibtex reads it and pdfTeX never does. The
  first full suite run failed twice: a bare 40-hex string in an upstream
  pgfplots FIXME comment, and a fixture that used placeholder digests which the
  new pinned contract correctly rejected. Each is described where it is
  recorded; none was a defect in the candidate.

### Baseline at START, for comparison

| Check | At START | Now |
|---|---|---|
| Detached verifier | 6 FAIL, exit 1 | 0 FAIL, exit 0 |
| `tests` + `experiments/tests` | 1 failed, 113 passed, 1 skipped | 643 passed, 0 skipped |
| `experiments/realistic_transport` | 297 passed | 297 passed |
| `git diff --check b99b682..HEAD` | exit 2, three findings | exit 0 |
| `( cd paper && sha256sum -c main.pdf.sha256 )` in CI | never reached: the step above it exited 1 | exit 0, and the downstream steps run |
| 40-hex Git object ids in `supplement.zip` | 2 files carried the execution revision | none in either archive |
| supplement mutated with a matching sidecar and declaration | `verify.sh` exit 0 | `verify.sh` exit 1 |
| supplement with its declaration deleted and originals restored | `verify.sh` exit 0 | `verify.sh` exit 1 |
| horizon grid edited to `{251,500,1000}` | shipped verification exit 0 | ledger exit 1, four failing checks |
| cap range edited to `501--2,001` | shipped verification exit 0 | ledger exit 1, three failing checks |
| rendered font of the three evidence tables | about 6.18, 6.31 and 6.70 pt | 9.96 pt, the body size |
| excluded legacy benchmark files in `supplement.zip` | 6 | 0 |
| `\iffalse ... \else \scriptsize \fi` in a compiled branch | layout gate exit 0 | exit 6 |
| `\fontsize{6pt}{7pt}\selectfont` | layout gate exit 0 | exit 6 |
| a visible value replaced while the old one stays in a `%` comment | ledger exit 0 | ledger exit 1 |
| an unledgered number in any theory source | ledger exit 0 | ledger exit 1 |
| `2,400 trajectories` -> `2,401` in a clean unpack | `verify.sh` exit 0 | `verify.sh` exit 1 |
| a provenance `artifact_sha256` zeroed | `verify.sh` exit 0 | `verify.sh` exit 1 |
| deliverable paths pre-placed as symlinks | linked targets overwritten | targets untouched, links replaced |
| a TMLR-only unresolved `\ref` or `\cite` | build exit 0, renders `??` | build exit 7 |
| abbreviated superseded candidate `F94FA4B` in a shipped file | scan clean | scan finding |
| benign SHA-1 `a9993e36…` in a shipped file | scan finding | scan clean |

### The six START verifier failures, each disposed of

1. **`study source experiments/BUCK` — unpinned divergence.** Commit `b99b682`
   prepends a `filegroup` listing source files for the deferred realistic
   extension: 24 inserted lines, zero deleted, no change to any existing rule,
   no dependency added to anything the transport study builds or runs, and no
   scientific source touched. Build files are inputs to neither tuning nor
   aggregation: the path appears in neither `selection.inputs` nor
   `aggregate.inputs`.

   Acknowledged by a hash-exact pin in
   `CURRENT_STUDY_SOURCE_COMPATIBILITY`, held in the **verifier**, deliberately
   **not** in the exporter's `KNOWN_STUDY_SOURCE_DIVERGENCES`. That map is
   serialized into `review/transport_instantiation/manifest.json`; adding to it
   would change the frozen review bundle's bytes. Both hashes are exact, so any
   further edit to `experiments/BUCK`, and any divergence in any other study
   source, still fails closed as unpinned. Three tests enforce this: the bundle
   manifest must not learn about the pin, the pin must carry both hashes and the
   causing commit, and perturbing the expected hash must restore the failure.

2–6. **Five stale manuscript-literal checks.** The manuscript was rewritten in
   later commits and the literals no longer occurred. Replaced with literals of
   the same scientific meaning against the current wording — dense diagnostic
   comparator, empirical vacuity, no generic network-width claim, the adverse
   regret direction — except for "do not show a causal or uniform advantage for
   full curvature", where the *required qualifier itself* was missing from the
   experiment section; that sentence was restored to the manuscript and the
   check was left untouched.

   Keyword co-occurrence is not semantic verification, so the positive list was
   paired with a prohibited list and negative tests. New checks: no
   `\usepackage[accepted]{tmlr}` or `[preprint]` option, no "are verified
   numerical certificates", no "validates the theorem", no "empirically
   validates", no "uniformly better", no "outperforms", no "state-of-the-art",
   no acknowledgments section. New tests prove that deleting a required
   qualifier fails, that adding an overclaim fails, and that switching the style
   option fails.

### The reported "five path-tightness CSV regeneration mismatches": not reproducible

I could not reproduce them, and I do not believe they happened. At START, with
the declared runtime available, all 21 artifacts regenerate byte-identically and
the artifacts section of the verifier reports 21 `PASS_RECOMPUTED`. The
rendering path is numpy-only in effect — `make_transport_instantiation_artifacts`
imports numpy and no scipy; the one scipy import in the chain is
`scipy.stats.beta`, used during aggregation, not during rendering — and the numpy
pin is `2.2.3` both in `experiments/requirements.txt` and in the checked-in
wheel.

What does reproduce is the verifier's behaviour **without numpy**: the whole
artifacts section collapses into one `FAIL` reading "the declared repository
rendering stack is unavailable (ModuleNotFoundError: No module named 'numpy')",
which turns 6 FAIL into 7. The repository's own pass-16 record independently
lists six failures — the `experiments/BUCK` divergence plus five manuscript
literals — and no CSV mismatch. I have recorded numbers and classifications from
runs I performed; I have not adopted the earlier CSV-mismatch description.

One genuine inconsistency did surface while checking this, and it is unresolved
rather than fixed: `experiments/requirements.txt` pins `scipy==1.15.2` while
`third_party/wheels/` ships `scipy-1.13.1`. CI installs the former, the Buck
graph and this host use the latter. It does not affect rendering, but the
declared runtime and the bundled wheel disagree about a scientific dependency.

### Submission checks run independently of the deferred extension

CI was split into two jobs. `submission-evidence` carries everything the
submission depends on. `realistic-transport-deferred` carries the deferred
extension, runs it, and reports its true status; it is not a dependency of the
other job, so its failures neither block nor are hidden by the submission
checks. The header comment says in the file that a failure there is not
clearance and not a submission blocker.

The `paths:` triggers and the three output exclusions are unchanged, which the
deferred extension's own structural test checks.

### The CI sidecar check ran from the wrong directory

An independent review reproduced a second CI defect. `paper/main.pdf.sha256`
names its subject as the bare filename `main.pdf`, so `sha256sum -c` has to run
from `paper/`:

```
$ sha256sum -c paper/main.pdf.sha256
sha256sum: main.pdf: No such file or directory
main.pdf: FAILED open or read                      exit 1

$ ( cd paper && sha256sum -c main.pdf.sha256 )
main.pdf: OK                                       exit 0
```

All three call sites used the first form, under `set -euo pipefail`, so the job
aborted in "PDF structural checks" before the ledger, the artifact regeneration,
the manuscript compile and the whole submission build ever ran. Every one is now
`( cd paper && sha256sum -c main.pdf.sha256 )`, with a comment at the first site
saying why.

`tests/test_tmlr_release_package.py` guards it behaviourally rather than by
keyword. It extracts each sidecar command from the workflow and runs that exact
string through `bash -c` against a temporary tree: the extracted command must
exit 0, the old repository-root form must still fail, and a one-byte-tampered
PDF must make the extracted command fail so the check remains a gate. Structural
tests assert the six submission steps come after the PDF check in file order and
that no step carries `continue-on-error`. A YAML parse asserts the two jobs
exist and that neither `needs` the other, so the deferred extension can report
its real status without gating the submission.

CI installs `pyyaml==6.0.2` for that parse. It is CI-only tooling and is
deliberately not added to `experiments/requirements.txt`, which is the
scientific dependency set.

### The range check I claimed, and the one that was actually run

The previous report's results table said `git diff --check` passed, exit 0. That
command was run, and it did pass — but on the post-commit working tree, which
was clean, so it compared nothing. The reviewer ran the range that matters and
got exit 2:

```
$ git diff --check b99b682..e32de5b
paper/body_related.tex:140: new blank line at EOF
paper/tmlr_style/fancyhdr.sty: upstream trailing whitespace
paper/tmlr_style/tmlr.sty: upstream trailing whitespace
```

Reproduced here, with one addition the reviewer did not list:
`paper/tmlr_style/tmlr.bst:2` has the same upstream trailing whitespace.

Two different causes, two different fixes:

- `paper/body_related.tex` ended with a blank line, introduced by my extraction.
  That is our defect and it is removed. The file now ends with exactly one
  newline after its last line of prose, and a test asserts no manuscript source
  under `paper/` ends with a blank line.
- The three upstream style files ship trailing whitespace on comment lines from
  upstream. Editing them is out of the question: TMLR says changes to the
  stylefile "may result in rejection without review". `.gitattributes` now unsets
  the `whitespace` attribute for exactly those three paths and nothing else. Only
  `whitespace` is unset — no `text` and no `eol` attribute is set — so Git never
  rewrites them, and their four SHA-256 values are unchanged and asserted by a
  test. A second test asserts the attribute is scoped: our own sources, and even
  the `LICENSE` in the same directory, remain `unspecified` and therefore still
  checked.

The results table now names the exact range command, and the test runs
`git diff --check b99b682..HEAD` rather than an empty working-tree diff.

### The CI PDF step, repaired rather than removed

"Attempt the clean PDF rebuild" previously compiled the current sources and
exited 1 if the bytes differed from `paper/main.pdf`. They always will: that
file is a frozen pre-rewrite snapshot at 63 pages and the current sources
produce 64. The step therefore failed every run and everything after it was
skipped — which is exactly why the later verifier, PDF and build steps "did not
run". It now separates the two questions. A build failure or an unresolved
reference fails the step; a difference against the frozen snapshot is reported
as a classification. The frozen PDF's hash and provenance are verified by the
separate structural-checks step, and the step re-verifies the snapshot's hash
afterwards to prove it was not touched.

The step name is unchanged because the deferred extension's
`test_workflow_required_pipelines_enable_pipefail` asserts that exact name, and
`experiments/realistic_transport/` is not mine to edit.

## 9. Anonymity and leak control

`package.py` refuses to write outside the repository-external output directory,
and refuses to ship anything matching an identifying pattern: author surnames,
employer and institution names, internal hostnames and monorepo paths, local
filesystem paths, the repository slug, and ORCID. It also refuses to ship
`FINALIZATION_REPORT.md`, `PORTAL.md`, `package.py` or `build.sh`. Both
archives pass.

Deliberately **not** on the forbidden list: the literal `BUCK` and the tool name
`buck2`. Both appear as ordinary build-file names inside the frozen selection
record's study-source inventory. That inventory is immutable evidence; a
build-file name identifies neither an author nor a host, and rewriting locked
evidence to satisfy a scrub pattern would be much worse than shipping the name.
The reasoning is in the source, not just here.

PDF-level anonymity, verified on the built file: `/Title`, `/Author`,
`/Subject`, `/Keywords`, `/Creator` and `/Producer` all empty; no
`/CreationDate` or `/ModDate`; no trailer `/ID`; no pdfTeX banner. Achieved with
`\pdfinfoomitdate`, `\pdftrailerid{}`, `\pdfsuppressptexinfo` and a pinned
`SOURCE_DATE_EPOCH`, which also makes the build reproducible. A byte-level
`strings` scan of the PDF finds no identifying content. No acknowledgments, no
funding text, no institution, no repository link, no local path.

**One residual anonymity signal, and it is an author decision.** The
bibliography cites `granziol2026hessian` — "Diego Granziol and Khurshid Juarev,
Hessian Spectral Analysis at Foundation Model Scale, arXiv:2602.00816, 2026" —
which is a preprint by two of this paper's four established authors, cited twice
in the third person. Citing one's own prior work in the third person is normal
and permitted under double-blind review, and removing a genuine citation would
be worse than keeping it. The scrub allows author names inside
`references.bib` and nowhere else, so the exemption is explicit rather than
accidental. Flagged in `PORTAL.md`.

One anonymizing transformation is applied, to two files, and it is declared
rather than hidden. Section 9a has the whole of it. Every other byte in both
archives is the repository's byte, and nothing anywhere is rewritten and then
labelled original.

Excluded from both archives: `.git`, everything under
`submissions/code_mit_2026/`, internal reviews and handoffs, this report,
`PORTAL.md`, the build scripts, all Buck files and `.buckconfig`,
`BUCK2_SETUP.md`, `third_party/` including the bundled wheels, `.github/`,
machine logs, caches, and the whole deferred `experiments/realistic_transport/`
tree. No fonts are distributed beyond what `source.zip` needs, and no monorepo
tooling is distributed at all.

## 9a. The anonymous packaging transform

An independent review found that `supplement.zip` shipped the study's
`git_revision`. That value is a Git object id which resolves in the project's
public repository to a named author and email, so the "anonymous" supplement was
not anonymous. The string scrub had never looked at revision identifiers.

### What is transformed, and where

The committed evidence is **not** edited. `package.py` writes anonymous copies
into the external staging tree only, and the repository's bytes, manifests,
hashes, sidecars and provenance records are untouched.

| Packaged path | Field | Original SHA-256 | Packaged SHA-256 |
|---|---|---|---|
| `results/derived/transport_instantiation/full_aggregate.json` | `git_revision` | `0ddebd4915dd2e264e24b7b25047d24f86c3cdf63930a1e6df77585e0b97de02` | `279e40f790c7e4a1045cbf24c3d61d5b2f10d870d77bdb7ab42b7d6896dcfdcb` |
| `results/derived/transport_instantiation/selection.json` | `git_revision` | `8c16bec7cc220109df3fd7173c3d06ae6c6e1b95e9db5bc5b8c3377b3564f6f4` | `6cb37fe4e03384df11b59898874fb38f4cba39b2ab555f0ca14857ed20883e49` |

Removed value in both files, recorded here and in `release_manifest.json`
(internal release metadata, not uploaded):
`0cd6264c1f8b8751728f3c4a198207e8289aed74`, the study execution revision.
Replacement: the literal string `withheld-for-double-blind-review`. It is
deliberately not forty hex characters: it must not be mistakable for a commit,
and it is not a substitute provenance identifier.

The replacement is byte-targeted. A regex matches exactly one
`"git_revision": "<40 hex>"` occurrence per file and refuses to proceed if the
count is anything other than one; every byte outside the replaced value is
preserved. The `.sha256` sidecars next to the two files are regenerated over the
packaged bytes, because a sidecar that describes bytes the reviewer does not
have is a lie. The `.provenance.json` records are **not** regenerated: they
truthfully describe the original evidence, and `ANONYMIZATION.json` says so and
gives both digests.

### A second instance the new gate caught

`package.py` now runs a revision/identity scan over both archives after the
transform and fails the build on any hit. Its first run failed: the provenance
header comment I had added to each of the fourteen extracted manuscript sources
said "Extracted verbatim from paper/main.tex at b99b682", shipping an
abbreviated baseline revision into `source.zip` and the supplement. The headers
now cite the line range and point at `paper/EXPOSITION_REVISION.md`, which is not
uploaded. The scan is a gate the transform has to satisfy, not a description of
it.

### Why this provably did not touch the numbers

`git_revision` is metadata. Nothing in the rendering path reads it:
`make_transport_instantiation_artifacts` imports numpy and never touches the
field, and the only `git_revision` consumers are in
`aggregate_transport_instantiation.py`, which runs during aggregation, not
rendering.

That is an argument. The check is stronger than the argument: the supplement
regenerates all 21 published tables, figures and CSVs **from the packaged,
redacted aggregate** and requires byte equality with the committed copies. They
reproduce byte-identically, which they could not do if the redaction had
perturbed anything the artifacts depend on. `tools/transport_artifact_expectations.py`
stamps the artifacts with the declared original-evidence digest, which is the
digest the published artifacts and their provenance records actually carry, so
the check is exact rather than self-fulfilling.

A test closes the remaining gap directly: it substitutes the removed value back
into the packaged bytes and asserts the result equals the original file byte for
byte.

### What the reviewer is told

`ANONYMIZATION.json` ships at the supplement root and states that the listed
files are modified copies and not original evidence, names the field and the
placeholder, gives both digests, says the placeholder is not a commit, and
explains the sidecar/provenance asymmetry. Both tools surface it rather than
reporting a plain pass:

- the ledger reports `PASS_ANON  source hash: …/full_aggregate.json (anonymized
  packaging copy, NOT original evidence bytes)`;
- the artifact checker reports `anonymized copy …  (NOT original evidence
  bytes)` and counts the declaration checks separately from the 21 artifacts.

The supplement README has a section headed "What was redacted, and what that does
and does not mean", which separates content verification from Git provenance and
says plainly that the latter is not verifiable from the supplement, by design.

### Scan semantics

`scan_for_identifiers` flags **every** project revision at any abbreviation of
seven characters or more in either letter case, any 40-hex value sitting in a
field whose name says it is a version-control identifier, the repository slug
and URL shape, and author and employer identity matched case-insensitively.

It deliberately does **not** flag a bare 40-hex string. It used to, and that was
wrong in a way a reviewer demonstrated with the SHA-1 of `abc`: a content digest
is not a leak, and rejecting the shape rather than the identity would force real
evidence to be rewritten to satisfy a scan. 64-hex SHA-256 digests are likewise
fine — the hex boundaries stop a 40-hex or 7-hex window from matching inside a
longer run — and unit tests assert all three directions.

"Every project revision" is derived, not maintained: `project_revisions()`
unions the recorded list, `git rev-list --all`, the reflog and `HEAD`. The
reflog matters: amending the finalization candidate leaves the previous one
reachable from nothing else, and a reviewer got an abbreviated superseded
candidate past the scan for exactly that reason. Every superseded candidate is
also written into the recorded list as it is superseded, which is the floor for
a build run outside a Git checkout. The recorded R9 build scanned against 137
revisions; a rebuild at the commit containing this report covers one more, that
commit itself. `package.py` is internal and is never uploaded, which is why
revisions may be written down there at all; a test asserts none of them appears
in the shipped contract module.

The bibliography exemption is scoped to the **matched token**, not the line it
sits on. It used to clear a whole line as soon as one allowed author name
appeared anywhere on it, so a `references.bib` line carrying both a name and a
local checkout path would have shipped the path. The two allowed names are also
exempt inside a `\cite`-family key argument, because a BibTeX key is
mechanically derived from the first author's surname and
`\citep{granziol2026hessian}` is the same third-person citation decision as the
bibliography entry itself. Prose naming an author is not exempt anywhere, in any
letter case, and tests cover both directions.

## 9b. The packaged verifier no longer trusts its own declaration

A second independent review found a trust-boundary defect in the fix above, and
reproduced it against the exact `supplement.zip`:

1. change `selection.json`'s `candidate_count` from 9 to 10;
2. recompute its `.sha256` sidecar;
3. update `ANONYMIZATION.json`'s `packaged_sha256` to match;
4. `bash verify.sh`.

Result before that repair: **exit 0**, 102 PASS / 1 PASS_ANON / 2 NOT_EXECUTED,
21/21 artifacts byte-identical, and the supplement's own study tests green.
`packaged_bytes` was not checked at all. Reproduced here before changing
anything.

The cause is simple and was mine: the shipped verifiers compared each packaged
file against `record["packaged_sha256"]` read out of `ANONYMIZATION.json`. That
file is reviewer-visible and reviewer-editable, so it is a claim about what was
done, and I had made it the authority for what is acceptable. Anything an
attacker could edit, they could also re-declare.

### The contract is now pinned in code

`tools/anonymous_package_contract.py` is new, shipped, and holds the whole
contract as constants:

- the exact set of two packaged paths, no more and no fewer;
- the exact field name `git_revision` and the exact replacement token;
- the exact original content SHA-256 and byte count of each evidence file;
- the exact sanitized content SHA-256 and byte count;
- the exact sidecar text that must sit beside each sanitized file;
- the exact declaration schema, required keys, required record fields, and
  forbidden record fields.

Every pinned hex value is a 64-character SHA-256 content digest. None is a Git
object id, the removed value appears nowhere in it, and a test asserts both
facts against the identity scanner.

`ANONYMIZATION.json` is now *validated against* those constants and never
consulted as an expectation. Both shipped verifiers call `contract.check(root)`
before trusting any packaged byte, and the artifact regenerator takes the
original-evidence digest it stamps from the contract rather than from the
declaration. Repository mode is unchanged and still strict: with no declaration
present, the original digests are required exactly as before.

Packaging is tied to the same constants from the other side.
`submissions/tmlr_2026/package.py` now refuses to build if the bytes it produces
do not match the pinned digests and byte counts, and it writes the sidecars from
`contract.sidecar_text()`. A test asserts the constants equal what packaging
actually produces, so the pins cannot drift away from the shipped archive in
either direction.

`verify.sh` gained a step 0 that runs the contract check on its own, so a
reviewer can see the boundary independently of the ledger and the artifacts.

### Evidence that it holds

Against the rebuilt `supplement.zip`, from clean unpacks:

| Case | `verify.sh` exit |
|---|---:|
| unmodified archive | 0 |
| reviewer's mutation: `candidate_count`, sidecar and declaration all updated | **1** |

The mutated run fails in three independent places — the contract step, the
ledger, and the artifact regenerator — each naming
`sanitized bytes match the pinned contract:
results/derived/transport_instantiation/selection.json`. Logs:
`r3-attack-clean.log` and `r3-attack-mutated.log`.

Negative coverage, all against a real packaged tree built by the real packaging
code, each asserting a nonzero exit from the shipped entry point:

| Mutation | Failing check |
|---|---|
| reviewer's exact repro (content + sidecar + declaration) | sanitized bytes match the pinned contract |
| `packaged_bytes` changed in the declaration | declaration agrees with the pinned contract |
| record `path` changed | declared record set is exactly the pinned set |
| extra record added | declared record set is exactly the pinned set |
| record removed | declared record set is exactly the pinned set |
| replacement token changed in the file | redacted field holds the pinned token |
| replacement token changed in the declaration | declaration agrees with the pinned contract |
| sanitized digest changed in the declaration | declaration agrees with the pinned contract |
| sidecar recomputed over mutated bytes | sidecar text matches the pinned contract |
| internal-only field leaked into the declaration | declaration agrees with the pinned contract |

Plus two positive controls: the clean package satisfies the contract, and the
repository is correctly detected as not a packaged tree, so nothing relaxes
there.

## 9c. Supplement verification requires package mode

A final independent review found the last way out of the contract in 9b, and
reproduced it against the exact `supplement.zip`:

1. unpack it;
2. delete `ANONYMIZATION.json`;
3. restore the two original evidence JSON files and their original sidecars;
4. `bash verify.sh`.

Result before this repair: **exit 0**, "all supplement checks passed", with both
restored files carrying `git_revision` in plain sight. Reproduced here before
changing anything.

The cause is the same class of mistake as 9b, one level up. The contract checker
treated "no declaration" as "this is the repository, so there is no
anonymization contract to check". That is the right default for running a
checker against the original committed evidence, and it is why repository
tooling does not have to carry an anonymization file. It is the wrong default
for the shipped supplement entry point, where the declaration's absence is
itself the finding.

### Two modes, chosen explicitly

`tools/anonymous_package_contract.py` now distinguishes them:

- **Optional repository mode**, the default. No declaration means nothing to
  check, and the tool says so. Unchanged behaviour for direct repository checks.
- **Required package mode**, via `--require-package` or
  `CCE_REQUIRE_ANONYMOUS_PACKAGE=1`. A missing declaration is a failure with a
  named check, not an empty pass.

The signal is explicit in both forms and is never inferred from the tree. That
is deliberate: a tampered package is missing exactly the file any such inference
would key on, so a path heuristic would fail precisely when it mattered.

Both shipped verifier entry points take the same flag and honour the same
environment variable, so running one directly inside a package cannot silently
fall back to repository semantics. `tools/verify_tmlr_submission_numbers.py`
and `tools/transport_artifact_expectations.py` each return a single named
failure and stop when package mode is required and no declaration is present.

`supplement_verify.sh` now exports `CCE_REQUIRE_ANONYMOUS_PACKAGE=1`, runs the
contract check first with `--require-package` as a **gate** rather than as one
result among several, and exits nonzero immediately if it fails, so a tampered
supplement cannot produce a wall of reassuring green below the failure. It also
passes `--require-package` explicitly to the ledger and the artifact checker.

None of the pinned checks from 9b was weakened: the hashes, byte counts, token,
sidecar text, paths, schema and record set are all still enforced exactly as
before, and the earlier mutation is still rejected.

### Evidence

Clean unpacks of the rebuilt `supplement.zip`:

| Case | `verify.sh` exit | Log |
|---|---:|---|
| untouched archive (positive control) | 0 | `logs/r4f-clean.log` |
| declaration deleted, originals and original sidecars restored | **1** | `logs/r4f-nodecl.log` |
| 9b's mutation: content, sidecar and declaration all updated | **1** | `logs/r4f-mutated.log` |

The omitted-declaration run fails at the gate with
`ANONYMIZATION.json is present (required package mode)` and prints "Refusing to
run the remaining checks"; the ledger and artifact steps never run, so nothing
in the output can be misread as a pass.

Tests added to `tests/test_tmlr_release_package.py`, all against a complete
supplement built by the real packaging code and driven through the real
`verify.sh`:

- the reviewer's exact reproduction, asserting a nonzero exit, the gate's
  message, and the *absence* of both "all supplement checks passed" and any
  later step's output. It also asserts up front that the restored files really
  do carry the identifier and that their original sidecars are self-consistent,
  so the test is failing for the right reason;
- the positive control: the untouched supplement still exits 0;
- `--require-package` on the ledger and on the artifact checker, each rejecting
  a declaration-free tree;
- the environment contract, on all three shipped checkers;
- a structural check that `verify.sh` exports the variable, runs the gate before
  every other checker, aborts rather than merely recording, and passes the flag
  to each;
- optional repository mode still passing with no declaration present;
- the resolution order of the signal: explicit flag first, then environment,
  including that an explicit `False` can still opt out.

No Git revision or author identifier entered any shipped file: the archive
identity/revision scan is clean on both archives, and the contract module's
constants remain 64-character content digests only.

## 9d. The final review's eleven findings

A final independent review of the candidate raised two blockers, four medium
findings and five low ones. Its own summary said "4 LOW" while enumerating five;
**the corrected severity count is 2 BLOCKER, 4 MEDIUM, 5 LOW, eleven in total**,
and all eleven are resolved below. None was silently dropped.

### 1 (BLOCKER) Evidence-table font and spacing shrinkage

The submission entry point halved `\tabcolsep` and then scaled whatever was
still too wide, on top of callers that had already chosen `\scriptsize`. The
three generated evidence tables rendered at roughly 6.18, 6.31 and 6.70 pt
against 9.96 pt body copy. TMLR does not allow fonts or spacing to be reduced to
fit content, so that was a real violation and not a matter of taste.

The `\widetable` wrapper is gone, `\scriptsize` is gone from every evidence
table, and `\tabcolsep` is the template's everywhere. The tables are reflowed
instead: `paper/notation.tex` sets each on a landscape float at the body font
size and substitutes a column preamble that lets the long headers wrap.
`\evidencetabular{<preamble>}{<\input>}` discards the generated file's own
`tabular` preamble and nothing else, so every cell, value, unit, qualifier,
caption and rule still comes from the generated file exactly as generated — the
committed artifacts are untouched and still regenerate byte-identically. No
empirical value was changed to make the layout fit.

Measured, at the body font size and the template's `\tabcolsep`, against the
650.43 pt landscape measure:

| Table | Natural width | Width as set | Headroom |
|---|---:|---:|---:|
| validity (11 columns) | 706.96 pt | 580 pt | 70 pt |
| performance (7 columns) | 675.85 pt | 613 pt | 37 pt |
| tightness (10 columns) | 646.56 pt | 615 pt | 35 pt |

The four hand-written tables that also carried `\scriptsize` or `\footnotesize`
now use `\ccetablesize`, which is empty in the submission and `\scriptsize` in
the legacy two-column layout. Two `\begin{quote}\small` remarks lost their
`\small`. **Nothing the submission compiles reduces a font size, reduces
`\tabcolsep` or `\arraystretch`, scales a box, or touches the margins.** The
result is 0 overfull hboxes and 0 overfull vboxes, down from five overfull
hboxes; all 68 pages were rendered and inspected.

The regression is a build gate, not a comment. `package.py` resolves
`\iflegacyextras` the way the submission compiles it and then refuses to build
if any shrink mechanism survives in what pdfTeX will actually see: `\resizebox`,
`\scalebox`, `\adjustbox`, `\tiny`, `\scriptsize`, `\footnotesize`, `\small`,
any assignment to `\tabcolsep`, `\arraystretch`, `\textwidth`, `\columnwidth`,
`\oddsidemargin`, `\evensidemargin` or `\topmargin`, and `geometry`. It also
requires each evidence table to still be reached through `\evidencetabular`, and
reports an unbalanced `\iflegacyextras` rather than letting it hide the rest of
a file. Tests inject each of the eleven mechanisms into the entry point and into
each evidence-table call site and assert the gate fires; a further test asserts
the legacy exemption is the dead branch and not a hole, by moving the same
mechanism into the compiled branch and watching it fail.

One defect in the gate itself is recorded because it mattered:
`\newif\iflegacyextras` was first read as opening a branch, which meant the
whole entry-point preamble fell outside the scan. The declaration is now
distinguished from a branch, and a test compiles the real entry point through
the resolver and asserts `\begin{document}` survives it.

### 2 (BLOCKER) Ledger coverage

Resolved in section 7 above: the two named omissions became source-derived
entries, and the omission class is closed by the literal audit.

### 3 (MEDIUM) CI gates the release path

`submission-evidence` now runs the **whole** `tests/test_tmlr_release_package.py`
module with `TMLR_OUT` bound to the output this job built, so the archive
integration tests grade real deliverables rather than skipping; the step fails
if the "no built release directory" skip message appears. It then unpacks the
generated `supplement.zip` into a clean directory and runs that archive's own
untouched `verify.sh`, requiring "all supplement checks passed". Both steps
write their logs to `RUNNER_TEMP` and then assert the worktree is unchanged, so
no protected path can receive a build output. The deferred
`realistic-transport-deferred` job is unchanged, still independent, and still
reports its real status. Workflow tests factor the gate into a checkable
function: the real step list yields no findings, and deleting either step yields
findings, so the test cannot pass vacuously.

### 4 (MEDIUM) Excluded legacy results removed from the supplement

`package.py` copied `paper/tables` and `paper/figures` directory-wide, which
shipped four `autodiff_ggn_summary*` files and two `linear_bound_ratios*` files
— outputs of the two legacy benchmarks the cut record excludes and
`availability.tex` tells the reviewer are excluded. The inventory is now an
explicit list: the 21 regenerated artifacts with their sidecars and provenance
records, plus the one symbolic rate table the manuscript typesets. The build
raises if `paper/tables` or `paper/figures` holds a file that is neither shipped
nor explicitly excluded, so a newly generated artifact cannot be dropped by
silence, and raises if a listed file is missing.

`verify.sh` gained a fourth check that walks `paper/tables` and `paper/figures`
**as they arrive in the archive** and verifies every file against its sidecar,
failing on a file that has none. That is what covers the symbolic table, which
has no aggregate to regenerate from. The clean run reports 43 shipped evidence
files verified. Tests assert the six excluded files are absent from both the
inventory and the archive, that every active artifact and record is present,
that the shipped list equals exactly what the artifact checker regenerates, that
an unclassified or missing artifact stops the build, and that smuggling an
unsidecarred file into a supplement makes `verify.sh` exit nonzero.

### 5 (MEDIUM) Root build instructions

`README.md` no longer calls Buck2 a verified path. It says plainly that
`buck2 test` and `buck2 run` fail during prelude evaluation on the declared host
setup and must not be reported as passing until that is fixed, and it gives the
direct `pytest` and `paper/validate.py` commands instead. Manuscript builders
are pointed at `submissions/tmlr_2026/build.sh` with an external output
directory. The historical AISTATS entry point, `make pdf`, and every other
command that can overwrite `paper/main.pdf` are documented as
disposable-copy-only, with the `git archive` recipe. `paper/main.pdf` and its
sidecar are unchanged.

### 6 (MEDIUM) Formal-preservation record

Corrected in section 6. `lem:cg` is recorded as the sole lemma-statement
exception; the narrower claims about equations, conclusions, signs, quantifiers
and proof obligations are preserved and still hold, including for `lem:cg`.

### 7 (LOW) Identity-scanner blind spots

Covered under "Scan semantics" in section 9a: case-insensitive surnames
including Granziol and Juarev, token-scoped rather than line-scoped
bibliography exemption, and a derived revision set covering the current
candidate and every ancestor.

### 8 (LOW) Declaration schema

`REQUIRED_DECLARATION_KEYS` is now an equality, not a containment: a declaration
carrying an extra top-level key fails, because the extra key may say something a
reviewer will read and nothing has checked it. Missing and unexpected keys are
both named in the failure. An extra-key regression was added; required-package
and repository-mode behaviour are unchanged, with a positive control.

### 9 (LOW) Truthful contract diagnostics

`transport_artifact_expectations.py` printed "1 anonymous-package contract
checks passed" and "0 of 0 generated artifacts" when required-package mode found
no declaration — it counted the checks that ran rather than the ones that
passed, and derived the source label from that same count. It now counts
successes, takes the label from actual package detection, says "no generated
artifact was checked: the run stopped before reaching them" instead of "0 of 0",
and prints an explicit `FAILED: n of m checks did not pass` line. A regression
pins the exact output and the exit status, and asserts the old shapes are gone.

### 10 (LOW) Report facts

This whole report was re-derived after the rebuild: deliverable sizes and
digests, the `release_manifest.json` size, the page count, archive member
counts, the number of checks `verify.sh` runs, every test count, the
`paper/tables` and `paper/figures` inventory count, where each adversarial
mutation stops, which independent checks ran, and the log links. Every pass
since has repeated the exercise; section 8 now points only at the `R8-` run.
Preserved failing exit codes are explained there rather than rerun away.

### 11 (LOW) Sibling output paths

`build.sh` no longer runs a `${out#"$repo"}` string-prefix test, which rejected
a valid sibling such as `<repo>-release` because it shares the repository's path
prefix without being inside it. Containment is decided once, in
`package.ensure_output_outside_repo`, on resolved paths with
`Path.is_relative_to`. Tests cover a valid sibling and three genuinely
in-repository paths, and assert the prefix test is gone from `build.sh`.

## 9e. The second review's nine findings

A second independent review of the corrected candidate ran skeptic passes
against the exact archives. Nine findings survived: **4 BLOCKER, 2 MEDIUM, 3
LOW**. All nine are resolved below, and every reproduction it supplied is now a
regression.

### 1 (BLOCKER) The layout gate did not fail closed

Two mechanisms got past it, both reproduced here before anything changed:

| Injected | Rendered at | Why it passed |
|---|---|---|
| `\iffalse X\else\scriptsize\fi` inside the compiled branch | about 7 pt | the parser knew only `\iflegacyextras`, so the inner `\else` flipped the *outer* switch and the rest of the file was dropped unscanned |
| `\fontsize{6pt}{7pt}\selectfont` | about 6 pt | an explicit size selection was not on the mechanism list |

The conditional parser now lives in `tools/tex_conditionals.py` and is shared
with `paper/validate.py`, so the two internal checkers cannot disagree about
which bytes are live. `\iflegacyextras` is still evaluated; **every other
conditional is opaque and both of its branches are scanned**, because a checker
that guesses which branch compiles is a checker that can be steered. A `\newif`
declaration opens nothing, an unbalanced conditional is a finding rather than a
silently truncated string, and a stray `\else` or `\fi` is a finding too.

The mechanism list gained `\fontsize`, `\selectfont`, `\usefont`,
`\@setfontsize`, `\DeclareFontShape`, `\linespread`, `\baselineskip`, and —
failing closed on syntax the checker cannot read — `\csname`, `\expandafter`,
`\scantokens` and `\catcode`. None of the submitted sources uses any of them.

The gate also moved: it now runs **before** anything is staged or compiled, so a
violation costs nothing and cannot be mistaken for a property of an output that
already exists. A test asserts the build exits 6 and writes no `src/`.

The tables themselves did not change: still landscape floats at 9.96 pt with the
template's `\tabcolsep`, still 0 overfull boxes.

### 2 (BLOCKER) The number audit was not exhaustive

Three reproduced bypasses, all now regressions:

- a visible `180.4` replaced by `.1`, with `180.4` left behind in a `%` comment
  to satisfy the literal check;
- a new `42.7` in a theory source, which the old rule ignored because it only
  rejected values already known to the ledger;
- a leading-dot decimal, which the token recognizer did not match at all.

Comments and the venue switch are now resolved **before** any literal is
matched, in the audit and in the literal-occurrence check both, so only bytes a
reader sees can satisfy either. The recognizer matches leading-dot decimals.

The audit is exhaustive over the transitive `\input` closure of the entry point
— computed from the files, not from a maintained list, so a newly typeset source
joins the audit the moment it is `\input`. Every numeric literal in every source
in that closure must be one of:

| Accounted for by | Count today | Rejects |
|---|---|---|
| a source-derived ledger entry | 67 entries | an edited value, an edited literal |
| a whole-file guarantee: byte-identical regeneration from the locked aggregate (6 files), a declared symbolic rate table, or macro definitions | 8 files | a "generated" label without a matching digest |
| an explicit `(file, literal) -> (category, count)` classification | 76 pairs, 8 categories | the same token in a different file, and one occurrence too many |

and nothing else. Since the fifth review each of those 76 classifications also
carries the complete semantic unit of each of its occurrences — the enclosing
paragraph, cell, item, caption or heading — so any edit inside that unit is
rejected even when the number and the count are unchanged; see section 9h.
There is no regex exemption and no per-section carve-out; the
two narrow masks that remain — a numeral immediately followed by a TeX unit, and
the string `SHA-256` — are named rules with their own regressions. An
unclassified literal fails closed.

Every one of the previous pass's checks survives. As of the current pass the
ledger stands at **67 entries, 258 checks, 255 PASS, 0 FAIL** plus **3
NOT_EXECUTED** raw-data limitations, unchanged in wording and still not reported
as passes.

### 3 (BLOCKER) The reviewer-facing supplement text was outside the audit

Changing `2,400 trajectories` to `2,401` in a clean unpack left every stage
green. The supplement README is now audited under the same rule, in both the
repository copy and the packaged `README.md`; the packaged name counts only in a
packaged tree, because a repository also has an unrelated top-level
`README.md`. Its counts are source-derived: the trajectory count from
`completed_run_count`, the artifact count from the grid
(`3 x (3 + len(target_D))`). The declared NumPy and SciPy versions are checked
against `experiments/requirements.txt` by a structural check, which is what
makes classifying them as environment metadata honest. The exact archive-level
mutation is a regression that unpacks the built `supplement.zip`, edits
`README.md` and asserts `verify.sh` exits nonzero.

### 4 (BLOCKER) Symlink-target overwrite in the external output

An output directory holding pre-placed `main.pdf` and `release_manifest.json`
symlinks built successfully and rewrote whatever those links pointed at.
Containment does not help: the escape is the link, not the path.

Every release output now goes through `atomic_write_bytes`, which creates a
fresh `O_EXCL` temporary in the destination directory and `os.replace`s it into
position. `os.replace` renames over the *link*, not through it. That covers
`main.pdf`, `source.zip`, `supplement.zip`, `release_manifest.json`, the
sanitized evidence copies, their sidecars and `ANONYMIZATION.json` — not only
the two names demonstrated. `write_zip` builds in memory and writes the same
way, so the deterministic bytes are unchanged. Directories that are staging
roots are reset through `reset_build_directory`, which unlinks a symlink rather
than following it, and a real directory at a deliverable path is refused
outright. Regressions cover a file symlink, a directory symlink, a real
directory, temporary-file cleanup, zip determinism, and a structural test that
no write into the output tree bypasses the helpers.

### 5 (MEDIUM) Unresolved references now fail the release

`paper/validate.py` validated the historical entry point only, so a `\ref` or
`\cite` that the TMLR entry point could not resolve rendered `??` and shipped.
The validator now takes an entry point as an argument and resolves the venue
switch, and packaging runs it against the **staged** TMLR tree and its
transitive closure. After the final converged LaTeX run, packaging reads
`main.log` for undefined references, undefined citations, multiply-defined
labels and non-convergence, and corroborates against the rendered text for
`??`, `[?]` and `(?)`. A bare `?` is deliberately not a signal: the manuscript
asks real questions, cites a URL containing `forum?id=`, and uses superscript
stars that `pdftotext` renders as `?`. Independent missing-reference and
missing-citation regressions both fail the staged validation.

### 6 (MEDIUM) The two shipped provenance records are verified

They were shipped and covered by nothing: the sidecar sweep walked
`paper/tables` and `paper/figures` only, so replacing a provenance
`artifact_sha256` with zeros left `verify.sh` green. They are kept, because they
are what binds each evidence file to its raw-input inventory, and they are now
pinned in `tools/anonymous_package_contract.py`: exact bytes, exact byte count,
and the structure — the artifact path, `artifact_sha256`, `input_set_sha256`,
`schema_version`, and an input list of the pinned length in which every entry
has a path and a 64-hex digest. The pins are checked in **both** modes, since
the transform does not touch those bytes, and repository mode no longer returns
early without checking anything. The supplement sweep now also walks
`results/derived/`, skipping only what `--list-pinned` reports as verified from
constants, so every shipped scientific evidence file is in exactly one closure.
The zeroing mutation is a regression.

### 7 (LOW) The revision scanner names identities, not hex shapes

Two errors in opposite directions. `F94FA4B` — the previous candidate,
unreachable once it was amended away — passed, because `rev-list --all` cannot
see an unreachable commit. And the SHA-1 of `abc`,
`a9993e364706816aba3e25717850c26c9cd0d89d`, failed for no reason other than
being 40 hex characters.

`project_revisions()` now unions the recorded list, `rev-list --all`, the reflog
and `HEAD`, and every superseded finalization candidate is written into the
recorded list as it is superseded — in `package.py`, which is internal and never
uploaded, so no identifier enters an archive. Abbreviations of seven characters
or more match in either case. A bare 40-hex string is no longer a finding on its
own; a 40-hex value in a field *named* as a version-control identifier still is,
in JSON, YAML or prose. Author names, repository identifiers and private paths
are rejected exactly as before, and 64-hex content digests still pass.

### 8 (LOW) Two stale audit facts

The reported unpacked supplement size came from `du`, which counts directory
inodes; it is now taken from ZIP metadata. The protected-inventory log compared
START against the index rather than the amended commit, so it said 41 changed
paths and omitted `paper/transport_theory.tex`; the R6 log is generated from
`git diff --name-only START..HEAD` after the final amend. The rest of this
report was re-derived from the final bytes, as section 8 records.

### 9 (LOW) The rotating dependency

`submissions/tmlr_2026/README.md` now lists every LaTeX package beyond a base
TeX Live with the TeX Live package and the Debian and RHEL package that supply
it, `rotating` included, and says plainly that `source.zip` bundles only the
venue's mandatory template files. The clean `source.zip` unpack rebuilds the
submitted PDF byte for byte under that documented set.

## 9f. The third review's five findings

A third independent review found **3 BLOCKER, 1 MEDIUM, 1 LOW**. All five are
resolved below.

### 1 (BLOCKER) The layout gate did not see the whole compiled closure

It globbed the entry point and `paper/*.tex`. The seven compiled inputs under
`paper/tables/` and `paper/figures/` were never scanned, and a directory added
later never would have been.

The authority is now the LaTeX recorder. After a successful compile,
`recorder_inputs()` reads `main.fls` — the list of every project-local file
pdfTeX opened while producing the submitted PDF — and `check_compiled_layout_rules`
runs the venue's rule over exactly that closure, before any deliverable is
written. The last build scanned **38 of 43 recorded inputs**. The repository
preflight still runs first and still exits 6, but it now says in its own output
that it is a diagnostic and not the authority, and a test asserts the compiled
gate runs after `compile_pdf` and before `write_zip`.

The recorder list is not merely read, it is policed: a recorded input that
escapes the staged tree, is a symlink, is missing, or carries a suffix the
checker cannot read aborts the build rather than being skipped. Skipping was the
old behaviour for anything that resolved outside the tree, which meant a symlink
pointing at `/etc/hostname` looked exactly like a system TeX Live file.
Normalisation is now lexical, before any `resolve()`, so the link is seen.

Five of 43 inputs are exempt, both classes **earned by bytes**:

| Exempt | Why | What breaks the exemption |
|---|---|---|
| `tmlr.sty`, `fancyhdr.sty` | the venue's mandatory template, which may not be edited and legitimately defines size commands | any edit: the digest stops matching the pinned upstream one and the file is scanned |
| the three generated pgfplots figure sources | `legend style={font=\scriptsize}` and friends set a plot's own axis annotations, not body or table text | any edit: the digest stops matching the locked artifact and the file is scanned |

`main.bbl` is scanned, with the one natbib preamble block `tmlr.bst` emits
verbatim excluded as an exact string rather than the file being excluded.

Regressions: `\scriptsize`, `\fontsize{6pt}{7pt}\selectfont`, a reduced
`\tabcolsep` and a `\resizebox` injected into each of a nested table input, the
symbolic table, and a generated figure — twelve cases, all failing — plus a
brand-new `appendix/` subdirectory input, an edited venue template, an edited
generated figure, and the four unreviewable-input classes. A positive control
asserts the clean closure passes.

### 2 (BLOCKER) The audit closure now comes from the compiler too

The audit followed `\input{...}` only, and did not resolve the venue branch
before following. Two consequences: plain-TeX `\input path` was invisible, and a
source reachable only from the legacy branch would have been audited as if it
were submitted.

Packaging now writes `SOURCE_CLOSURE.json` into the supplement: every recorded
compiled input with its staged name, repository path, SHA-256, byte count, role,
and whether this archive carries it. `verify.sh` has no TeX installation, so
without this the packaged audit would have to re-derive the closure by parsing —
the guesswork the recorder exists to replace. The ledger binds every entry to
bytes actually present and rejects a missing, extra, changed, unsafe or
duplicated path; it also requires every `.tex` the archive ships under `paper/`
to be a recorded compiled input, so deleting an entry to dodge the audit fails.

The `\input` walk is retained for the repository preflight, where no build has
run. It now covers `\input{braced}`, `\input unbraced` and `\include{...}`, and
resolves the venue switch before following anything.

Regressions: an unbraced `\input` of a new source fails; an inactive-branch
source is correctly **not** treated as submitted evidence; byte drift, a missing
entry, a duplicate entry, an unsafe path and a deleted entry each fail, in the
repository and in a clean unpack of the built archive.

### 3 (BLOCKER) Classifications are bound to a file and to a count

Three separate holes: ledger phrases were masked globally rather than only in
the file they were declared for; a per-file literal classification authorised
*every* occurrence in that file; and `paper/macros.tex` and the symbolic rate
table were whole-file exemptions.

Both tables are now occurrence-bound. `PHRASE_OCCURRENCES` says where each of
the 74 ledger and non-empirical phrases may appear and how often;
`CLASSIFIED_LITERALS` says the same for 76 `(file, literal)` pairs, each with a
category and a written rationale. A phrase appearing in a file it is not
declared for is an unclassified literal. A count that does not match — one more,
one fewer, or moved — is a failure. That is what stops a newly written empirical
sentence from reusing a classified theorem constant.

The two whole-file exemptions are gone:

- `paper/macros.tex` must consist only of macro declarations and must contain
  **no numeric literal at all**; every macro in it is notation.
- every body cell of `paper/tables/growing_window_pareto.tex` must be drawn from
  the alphabet an asymptotic rate in `T`, `K` and `q` uses, so a decimal point
  is enough to fail it.

The six generated artifacts keep the stronger guarantee they already had, byte
identity against the locked aggregate, and the audit still rejects that status
unless a matching sidecar backs it.

Ledger after this pass: **67 entries, 285 checks, 283 PASS, 0 FAIL**, plus the
same two NOT_EXECUTED raw-data limitations. Regressions added: a ledger phrase
copied into the wrong file; a second occurrence of a classified literal in an
empirical sentence; an empirical value in the macro file; an empirical value in
the symbolic table; a missing classified occurrence. Every earlier regression —
comment shadowing, the leading-dot decimal, `42.7` in a theory source, the
README `2,401`, the horizon grid and the cap range, and the new-input case — is
retained and still fails.

### 4 (MEDIUM) natbib's own diagnostics are recognised

`tmlr.sty` loads natbib, and natbib does not use the `LaTeX Warning:` prefix. A
checker that only knew `LaTeX Warning: Citation` saw nothing at all. The log
check now matches `Package natbib Warning: Citation ... undefined`, the
"There were undefined citations" summary, the rerun notice, the multiply-defined
summary, and a restricted catch-all for any warning that names a citation,
reference or label as undefined. Log lines are unwrapped first, because pdfTeX
wraps at 79 columns and a warning can straddle two physical lines.

`LaTeX Warning: Font shape ... undefined` is routine and is deliberately
excluded: a gate that fails on it is a gate someone turns off. Ordinary question
marks in prose, the `forum?id=` URL and `pdftotext`'s rendering of superscript
stars are all still fine.

The log check is complete on its own; the rendered-text pass is corroboration
and says NOT EXECUTED when no text extractor is available, rather than being a
silent dependency.

Build-level evidence, both run end to end:

| Case | Exit | Which gate fired |
|---|---:|---|
| a TMLR-only `\citep[see][]{nobody-wrote-this-r7}` | **7** | staged static validation — `paper/validate.py`'s citation pattern now sees optional arguments, which it did not before, so `\citet[Thm.~6.1.1]{...}` was previously invisible to it too (38 cite keys now, was 37) |
| the same injection with static validation stubbed out | **8** | the log gate, naming `undefined citation (natbib) 'nobody-wrote-this-r7'` |

### 5 (LOW) The protected-inventory log names the final commit

The R6 log was generated before the last amend and named an intermediate
commit. The R7 inventory and changed-path logs are generated **after** the final
commit exists and record that exact SHA, and the changed-path list is taken from
`git diff --name-only START..FINAL`. No further amend was made to put the SHA
into a tracked file.

## 9g. The fourth review's five findings

A fourth independent review found **3 BLOCKER, 0 MEDIUM, 2 LOW** and requested
changes. All five are resolved below.

### 1 (BLOCKER) The recorder classifier now fails closed both ways

Anything the compiler opened outside the staged tree was dropped in silence as
"a system TeX Live file". A manuscript input anywhere on the filesystem could
therefore affect the submitted PDF without appearing in `source.zip` or in any
audit closure.

An external input became a finding unless it lay under a TeX tree the runtime
itself names: the allowlist was derived by asking `kpsewhich -var-value` for
`TEXMFDIST`, `TEXMFMAIN`, `TEXMFLOCAL`, `TEXMFHOME`, `TEXMFVAR`, `TEXMFSYSVAR`,
`TEXMFCONFIG` and `TEXMFSYSCONFIG`, then filtering for an absolute, existing
directory at least three components deep, never one of `/`, `/usr`,
`/usr/share`, `/home`, `/tmp`, `/var` and the rest of that list, and never an
ancestor of the repository or of the staged tree. Six trees resolved, and
`main.fls` recorded 1,586 `INPUT` lines, 340 distinct paths once normalised: 45
staged and 295 external.

**Superseded by section 9h, finding 1.** That allowlist was still too wide: it
trusted `TEXMFHOME` and the user caches, and it asked kpsewhich in an
environment that could answer for the installation. Only system variables are
trusted now, the engine is asked with the TeX search environment stripped, and
every root and file must be write-protected and unlinked at every path
component. What remains from this pass is the direction: an input outside the
staged tree is a finding until something proves otherwise.

A staged input must also resolve to a **canonical** regular file: the realpath
has to equal the lexical path, so a symlink anywhere along the relative portion
is caught, and two recorded names that resolve to the same file are reported as
an alias rather than merged. Empty paths, `..` components, missing files,
non-regular files and unsupported suffixes were already findings and still are.

One external input is a distribution-internal symlink —
`texmf-dist/web2c/texmf.cnf` points at `/etc/texlive/web2c/texmf.cnf`. This pass
handled it by testing membership on the lexical path; section 9h replaced that
with a digest pin, because a symlink the build cannot verify is not something to
wave through on the strength of where it appears to live.

Regressions: an outside-tree manuscript input, a linked staged input, an
ordinary `article.cls` dependency from a derived tree, the clean closure of the
real build, the allowlist's narrowness, a root that would contain the
repository, and a structural test that the closure is read before any
deliverable is written.

### 2 (BLOCKER) The closure manifest is validated as a contract

Package verification could previously proceed on a manifest that was
incomplete or noncanonical. Every invariant below is now checked before a single
entry is used, and each has its own regression:

presence in package mode; valid JSON; object shape; exact top-level keys;
supported schema version; exact per-entry keys and types; canonical unique
staged paths; canonical unique repository paths; repository-path containment in
a known project directory; regular-file and no-symlink status; a consistent
staged-to-repository mapping; the **role recomputed** from the validated path
rather than read; **supplement membership derived** from the role's policy and
cross-checked against what the archive actually holds; and the exact byte and
digest binding, with no missing closure member and no shipped manuscript source
that the manifest fails to declare.

Unknown keys are rejected outright, in the top level and per entry. Repository
preflight mode still works without a manifest, and now says so in its own
output as a NOT_EXECUTED check: it is a preflight and it does not certify a
packaged release. Deleting the manifest from a supplement fails.

### 3 (BLOCKER) Every classification is bound to a context

A category and a same-file count still authorised a number after its meaning
changed: it could move anywhere inside its file, and the sentence around it
could be rewritten under it.

Each allowed occurrence was pinned to its context: for every declared phrase and
every classified literal, `tools/numeric_context_pins.py` recorded the exact
occurrence count and a SHA-256 over the ordered contexts — 40 characters of
normalised text before each occurrence, the literal, and 40 after. 74 phrase
pins and 76 classified pins, cross-checked against the reviewable category table
in both directions, so a pin without a rationale and a rationale without a pin
are both failures.

**Superseded by section 9h, finding 3.** A fixed radius cannot see a
meaning-changing edit past its own edge; the context is now the complete
enclosing semantic unit, with a whole-file digest alongside it, and the pin
module is bound through the contract module so it cannot authorize itself. The
cross-check against the category table, and the two-directional completeness it
enforces, are unchanged.

The pins are generated data, committed so the audit compares against a fixed
record rather than against whatever the sources currently say.
`tools/verify_tmlr_submission_numbers.py --print-contexts` prints the strings
behind every pin, with each category's rationale, so the record is reviewable
and not opaque.

The symbolic rate table no longer passes an alphabet-membership test, which
accepted any rearrangement of the same characters. Each body cell is **parsed**
against the grammar of an asymptotic rate in `T`, `K` and `q`, and the parsed
cells must equal a pinned list — so `KT^{2}` becoming `KT^{3}` fails even though
both are well-formed rates.

Regressions, one per category family and per failure mode: a changed
citation locator, a changed cited scale, a changed illustration input, a changed
declared version, a classified constant reused in a new sentence, a reworded
context around an unchanged number, a moved occurrence, a symbolic rate changed
to another valid rate, an empirical value in the symbolic table, and an
empirical value in the macro file. Every earlier regression is retained and
still fails: comment shadowing, the leading-dot decimal, `42.7` in a theory
source, the README `2,401`, the horizon grid, the cap range, a new unbraced
`\input`, and the archive-level mutations.

### 4 (LOW) The superseded R7 candidate is recorded

`8f74363694c41ba323233a324f1b570decdd39ab` is in the explicit prior-candidate
record, together with the two other candidates the earlier passes produced. A
clean checkout can no longer fail to discover it after the amend. Full and
abbreviated forms are matched case-insensitively; the benign SHA-1 and 64-hex
content-digest controls still pass; and a test asserts that no recorded
revision, full or abbreviated, appears in any shipped reviewer artifact.

### 5 (LOW) Every report fact regenerated from the final outputs

Sizes, digests, member counts, unpacked bytes, page count, ledger counts in both
modes, suite counts, revision-scan coverage and the changed-path count in this
report are taken from the R8 artifacts and logs, not carried over. The durable
inventory and changed-path logs are `R8-protected-inventory.log` and
`R8-changed-from-START.txt`, generated **after** the final amend and naming that
exact SHA; this report refers to its own commit as "the commit containing this
report" and no amend was made solely to insert a SHA into a tracked file.

## 9h. The fifth review's five findings

A fifth independent review found **3 BLOCKER, 1 MEDIUM, 1 LOW** and requested
changes. All five are resolved below.

### 1 (BLOCKER) The TeX runtime allowlist is now a trust decision, not a question

The previous pass accepted an external compiled input from any tree kpsewhich
named. That included `TEXMFHOME` and the user caches, which is to say: bytes the
account running the build can rewrite at will could reach the submitted PDF
without appearing anywhere in the audited closure. Worse, `kpsewhich
-var-value=TEXMFDIST` reports whatever `TEXMFDIST` in the environment says, so
the allowlist could be supplied by the thing it was meant to constrain.

Four changes:

- **Only system variables.** `TEXMFDIST`, `TEXMFMAIN`, `TEXMFLOCAL`,
  `TEXMFSYSVAR`, `TEXMFSYSCONFIG`. `TEXMFHOME`, `TEXMFVAR` and `TEXMFCONFIG` are
  never trusted.
- **The engine is asked with the environment stripped.** Every kpsewhich call
  runs with `TEXMF*`, `TEXINPUTS`, `BIBINPUTS`, `KPATHSEA*` and the rest removed,
  so it reports the values compiled into the installation.
- **Ownership, mode and ancestry.** A root, and every component of its path from
  `/` down, must be a real directory that is not a symlink, not writable by the
  invoking user, and not group- or world-writable; it must already be canonical,
  at least three components deep, outside the shallow-root list, and neither
  inside nor containing the repository or the staged tree. On this host that
  accepts `texmf-dist`, `texmf-local`, `texmf-config` and `/var/lib/texmf`, and
  rejects `/usr/share/texlive/texmf-var`, which is a group- and world-writable
  symlink.
- **The same walk for the file.** Every accepted external input must itself be
  canonical, a regular file, unlinked at every component below the root, not
  writable by this user or its group or the world, and must not resolve back
  into the project.

Then the honest part. This host's TeX Live 2020 (el9) does not package
`pgfplots`, `microtype`, `cleveref` or `mathtools`, and the manuscript needs all
four, so they were installed into `TEXMFHOME`. Two more inputs are outside a
trusted root for the distribution's own reasons: `texmf-dist/web2c/texmf.cnf` is
a symlink into `/etc`, and the format dump `pdflatex.fmt` is written into the
user's `TEXMFVAR` cache. Nothing an unprivileged account can do makes those
root-owned.

So 48 inputs are accepted by a second route, and only that route:
`submissions/tmlr_2026/external_tex_inputs.py` names each one as
`VARIABLE:relative/path` and pins its SHA-256. A pinned input must still be a
readable regular file whose bytes match; a changed byte stops the build, and an
input that is neither trusted nor pinned stops the build. The names carry no
absolute path, because the absolute path of a user tree carries the operator's
account name and this is a double-blind submission. Every accepted external
input, trusted or pinned, is written into `release_manifest.json` with its
digest, so the audited record of the release names every byte outside the
project that the PDF depended on. The recorded build: 295 external inputs, 247
from trusted roots, 48 by pin.

This is weaker than a root-owned distribution and it is labelled as such in
section 12. It is stronger than the previous pass in the way that matters: those
bytes are no longer absent from the audited closure.

Regressions: a user-writable root, a linked root component, a group/world
writable component, an environment-supplied root, a broad root, a project path
reached through a root, a pinned input with changed bytes, an unpinned untrusted
input, the clean system dependency, the real build closure, pinned names that
carry no absolute path, and the manifest record.

### 2 (BLOCKER) The rest of the source-manifest contract

Five invariants were still missing, each with its own regression:

- **Exact scalar types.** `type(x) is int`, not `isinstance`. In Python `bool`
  subclasses `int`, so `"bytes": true` passed the old check and then compared
  equal to `1`: a one-byte file would have satisfied the byte binding.
- **A non-null repository path for every entry** except the one derived role
  that has no repository source, `bibliography-output` (`main.bbl`, which bibtex
  writes during the build). The exception is computed from the staged path, not
  granted by the entry.
- **Exact staged-to-repository mapping.** `derive_repository_path` recomputes
  the whole path from the staged name, mirroring what `stage()` actually copies.
  The old check compared basenames, which accepts `figures/x.csv <-
  experiments/x.csv`: the audit would then read a different file from the one
  the compiler opened, under a name that looks right.
- **Symlink-free path components**, not only a non-symlink leaf. A symlinked
  `paper/` redirects every entry under it while each leaf still reports as a
  plain file.
- **Recursive completeness.** The sweep is `rglob`, not one directory deep, and
  it runs in both directions: every shipped `.tex`/`.sty`/`.bst` under `paper/`
  must be a recorded compiled input, every shipped `.csv`/`.bib` must be either
  recorded or sidecarred, and every audited-role source the archive carries must
  be in the audited set. A nested `paper/parts/smuggled.tex` was previously
  invisible.

### 3 (BLOCKER) Contexts are complete semantic units, not a character window

The ±40-character digest could not see a meaning-changing edit past its own
edge. The demonstration, now a regression: in `paper/appendix_cg.tex`,
"independently of $T$" → "growing linearly in $T$" reverses a claim about the
sufficient budget about sixty characters from the nearest pinned number. The old
context strings are byte-identical before and after.

Every pinned occurrence is now bound to the **complete normalized semantic
unit** it sits in, plus its offset inside that unit. A unit is what a reader
would call one statement, and its boundaries come from the source: a blank line,
`\\`, an unescaped `&`, `\item`, a sectioning command, `\begin`/`\end`,
`\caption`, a booktabs rule. In practice that is a paragraph, a table row or
cell, a list item, a caption, a heading, or an equation environment — 485
distinct units across the closure, the largest 3.8 kB and most a paragraph.

The record stays reviewable. `tools/numeric_context_pins.py` carries the units
themselves, not just digests: `UNITS` holds each distinct unit once and the pin
tables cite them by index, which is both smaller and easier to read than
repeating the same paragraph for each of the dozen numbers in it. Each pin gives
canonical file, literal or phrase, category, expected count, and the unit with
the offset. `--print-contexts` prints all of it with the category rationale.

`FILE_PINS` adds a whole-file binding — a digest over the entire normalized
auditable text of each of the 23 audited sources. It catches a meaning-changing
edit in a part of a file that holds no pinned number, which no per-occurrence
pin can see; `paper/availability.tex` states no number at all and can still be
rewritten to say something false. It is an addition, not a replacement: a file
digest says only that something changed, and the unit says what.

Two consequences worth stating. The unit split also made three occurrences of
`0` in `paper/transport_theory.tex` visible that the recogniser had been blind
to, because a `\\` immediately before a digit suppressed the match; the pinned
count for that literal went from 19 to 22. And the marker had to be NUL: an
earlier draft used `\x1d`, which Python's `str.split()` treats as whitespace, so
every marker was eaten and each file came out as a single unit.

The symbolic rate table is unchanged: each body cell is still parsed against the
asymptotic-rate grammar and compared to the pinned list.

**Self-authorization.** The pin module is generated from the sources and it
ships, so inside an unpacked supplement someone could edit a source and make the
pin agree — and the unit comparison, asked whether the source matches a record
derived from that same source, would say yes. It does: the R9 battery ran that
exact attack and the per-occurrence checks passed. What stops it is that the pin
module's own SHA-256 is pinned in `tools/anonymous_package_contract.py`, checked
by the ledger *before* a single pin is read, cross-checked by packaging (which
refuses to build on a mismatch), and recorded again in `release_manifest.json`.
`verify.sh` stops at the contract gate and refuses to run the remaining checks.
This is a binding, not a signature — an offline archive has no cryptographic
root — and a reviewer wanting certainty compares against the release manifest,
which never ships. Separately, the generator cannot run inside a package at all:
it needs repository paths the supplement does not carry.

Regeneration is an authoring aid and is not on the verification path; a test
asserts `literal_coverage_checks` never calls it, and another asserts the
committed pins are exactly what this repository's sources produce.

### 4 (MEDIUM) Archive identity no longer depends on zlib

`write_zip` used `ZIP_DEFLATED` at level 9. A deflate stream is whatever the
linked zlib emitted, so two hosts with different zlib builds produce different
archive bytes from byte-identical members and the deliverable hash in
`release_manifest.json` drifts for a reason that has nothing to do with the
submission. Nothing in the declared build closure pins zlib.

Members are now `ZIP_STORED` with fixed names, order, timestamps and modes, so
the archive is a pure function of things this project does pin. A test asserts
every member's `compress_type` is 0 and `compress_size == file_size`, that the
member bytes appear verbatim in the archive, that `ZIP_DEFLATED` is gone from
`package.py`, and that the writer produces identical bytes with `zlib.compressobj`
monkeypatched to raise.

The cost is size, and it is the reason this is a judgment call rather than an
obvious win: `supplement.zip` went from 11.5 MB to about 84 MB, because it
is dominated by one 77 MB committed evidence file. That is 84.1% of TMLR's
100 MB limit, 15.9 MB spare. `package.check_archive_size` now fails the build at
100,000,000 bytes — the smaller reading of "MB", so the check cannot pass on a
generous interpretation — and warns within 10% of it.
`submissions/tmlr_2026/README.md` records the trade, both sizes, and the rule
for revisiting it: pin a compressor into the build closure, do not quietly turn
deflate back on.

### 5 (LOW) Report facts regenerated again, from the R9 outputs

Every size, digest, member count, unpacked byte count, page count, ledger count
in both modes, suite count, revision-scan coverage and changed-path count in
this report comes from the R9 artifacts and logs. The stale supplement size the
review found is gone, along with the deflated figure it described. The durable
inventory and changed-path logs are `R9-protected-inventory.log` and
`R9-changed-from-START.txt`, generated **after** the final amend and naming that
exact SHA; this report still refers to its own commit as "the commit containing
this report", and no amend was made solely to insert a SHA into a tracked file.

## 9i. The sixth review's seven findings

A sixth independent review found **2 BLOCKER, 1 MEDIUM, 4 LOW** and requested
changes. All seven are resolved below.

### 1 (BLOCKER) Nothing is admitted by digest any more

The previous pass tightened the trusted-root rule and then undercut it: a digest
pinned in committed code could still admit an input that failed every one of
those rules. The last release recorded 48 such inputs — 46 from `TEXMFHOME`, the
format dump from `TEXMFVAR`, and a linked `texmf.cnf`. A pin proves the bytes
did not change between the pin and the build. It proves nothing about who can
change them next, and that was the whole question.

The escape is gone. `submissions/tmlr_2026/external_tex_inputs.py` is deleted,
and so is the code that read it. An external compiled input is accepted if and
only if it sits in a system distribution tree that is write-protected, unlinked
and canonical at every path component from `/` down, and is itself a canonical,
write-protected, unlinked regular file that does not resolve back into the
project. There is no second branch.

Three changes made that survivable:

- **The compile runs in a scrubbed environment.** `compile_environment` strips
  every TeX search variable, then sets `TEXMFHOME` and `TEXMFCONFIG` to
  directories under the staged tree that are never created, so no user tree can
  shadow the distribution; `TEXMFVAR` to the system variable tree, so the format
  dump is the root-owned one; and `TEXMFCNF` to the directory holding the
  installation's real `texmf.cnf`, so the recorder writes that canonical path
  rather than the distribution's symlink to it. That directory is derived from
  the installation — resolve `$TEXMFDIST/web2c/texmf.cnf` and validate what you
  find — not taken from the environment.
- **A system tree published under a symlink is admitted as its real path.**
  `TEXMFSYSVAR` here is a root-owned link to `/var/lib/texmf`. The link is never
  the trusted root; the target is, and only after passing the whole walk on its
  own.
- **Four packages are vendored.** This host's TeX Live does not ship `pgfplots`,
  `microtype`, `cleveref` or `mathtools`, an unprivileged account cannot install
  into a root-owned tree, and the manuscript needs all four. They now live in
  `paper/texmf_vendor/` — 46 files, verbatim and unmodified — and stage flat
  beside `main.tex`, where kpathsea finds them first. Their licences (GPL v3 for
  pgfplots, LPPL 1.3c for microtype and mathtools, LPPL 1.2 for cleveref) permit
  redistribution, and the three licence texts travel in `source.zip` with the
  code. No font is vendored. Every file is held to a pinned SHA-256 in
  `package.VENDORED_PACKAGE_DIGESTS`, is exempt from the layout rule and the
  per-literal number audit on the same terms as the venue template, and carries
  the role `vendored-package` in the compiled-source closure.

The recorded build: 249 external compiled inputs, **all of them trusted, none
admitted by digest**, each named in `release_manifest.json` by the kpathsea
variable whose tree holds it and bound to its SHA-256. `main.pdf` is
byte-identical to the previous pass, which is the evidence that vendoring
changed what the compiler read from and not what it produced.

Regressions: a user-tree input, a user-cache input, a linked root, a linked
path component, a writable root, a writable file, a broad root, an
environment-supplied root, a project path reached through a root, the symlinked
system tree admitted only as its real path, the derived config root, the
scrubbed compile environment, the clean real build, every vendored digest, an
edited vendored package, the shipped licences, "no font is vendored", and a
manifest assertion that every recorded external input is trusted.

### 2 (BLOCKER) The last of the manifest contract

Four invariants, each with its own negative test and a clean positive control:

- **`schema_version` is exactly an `int`.** `True == 1`, so an equality test
  alone accepted `"schema_version": true`.
- **`what_this_is` is exactly a non-blank `str`.**
- **Completeness sweeps every shipped source root**, `submissions/tmlr_2026/`
  included. A `.tex` dropped in beside the entry point was invisible to a
  `paper/`-only sweep.
- **Every mandatory compiler input is recorded once and byte-bound.**
  `main.bbl`, the venue template and the 46 vendored packages travel in
  `source.zip`, not in the supplement, so the packaged checker has no bytes to
  recompute from and its recorded digest used to be unfalsifiable — zeroing
  `pgfplots.sty`'s recorded `sha256` inside an unpacked supplement changed
  nothing. The expected values are pinned in
  `contract.NON_SUPPLEMENT_CLOSURE_DIGESTS`, packaging refuses to build if what
  it records disagrees, and the check now fires. The list is derived, so it
  cannot fall behind the vendored set.

### 3 (MEDIUM) A release is published in one step or not at all

The size gate ran after `main.pdf`, `source.zip` and `supplement.zip` had
already replaced the previous release, so an oversized supplement left three new
deliverables beside a `release_manifest.json` describing the old ones — a mixed
generation that looks like a release.

Every deliverable is now built into `<out>/.pending`. The size gates run there,
then `check_pending_release` confirms the staged bytes are the bytes the staged
manifest describes and that each archive's member list is the one the manifest
records. Only then does `publish_release` move all four into place, each through
`atomic_write_bytes`, so a pre-existing symlink at a deliverable path is still
replaced rather than written through. A failure removes the staging area and
returns; every prior deliverable is byte-identical afterwards.

Regressions: both size gates against sentinel prior deliverables, a manifest
that disagrees with the bytes beside it, an archive whose member list drifted, a
missing staged deliverable, a clean publication, and a structural test that both
gates precede `publish_release` and that nothing is written into `out` before
it.

### 4 (LOW) The immediate prior candidate is recorded

`e0f2b414cdb73c5fbcb2e87fd00b5bc09f234f71` is in the explicit prior-candidate
record. Full, abbreviated and mixed-case forms are rejected in a clean checkout,
and the existing test that no recorded revision appears in a shipped reviewer
artifact covers it.

### 5 (LOW) Every current-artifact size comes from this build

Section 2 still quoted 11,436,761 bytes for the supplement — a deflated figure
from three passes ago, stated as a current fact. Every size, digest, member
count and unpacked byte count in this report is now read from the R10 archives'
own metadata. Historical figures appear only where they are labelled as history:
"it went from 11.5 MB to about 84 MB" in section 9h is a statement about the
change, not about the artifact.

### 6 (LOW) The source archive is described as what it is

`source.zip` was described as "exactly the files pdfTeX opened" and as the
recorder's `.fls` closure. It is neither: it is the **project-local** part of
that closure, plus `references.bib`, `tmlr.bst` and four licence texts, which
pdfTeX does not open. The overstatement is corrected in
`submissions/tmlr_2026/README.md`, `submissions/tmlr_2026/build.sh`,
`paper/EXPOSITION_REVISION.md` and section 4 here. The README now also says
where the rest of the closure is: 249 distribution files, listed in
`release_manifest.json` under `external_tex_inputs` with their digests, not
shipped.

### 7 (LOW) The formal-change record names its one exception

`paper/EXPOSITION_REVISION.md` recorded the bounded `lem:cg` statement-text
correction and then said no theorem or lemma changed. Both were true in their
own paragraph and contradictory together. The summary now states that `lem:cg`
is the sole theorem/lemma/corollary/proposition statement-text exception, that
the change is a scoping qualification, and that its equations, conclusion and
proof are unchanged. The original correction text is preserved exactly.

## 9j. The seventh review's eight findings

A seventh independent review returned BLOCK with **3 BLOCKER, 1 MEDIUM, 4 LOW**.
Each was reproduced here before it was fixed; the reproductions are recorded in
`R11-EXITCODES.txt` and are now regressions.

### 1 (BLOCKER) Publication is a set transaction

`publish_release()` replaced the four deliverables one at a time with no
rollback. Injecting a failure on the second replacement left a new `main.pdf`
beside three old deliverables — a mixed generation that looks like a release,
and that nothing downstream can detect.

It now snapshots every deliverable path that exists, replaces all four, and on
any exception restores each one byte for byte and removes any path that did not
exist before. A path that is a **symlink** is recorded as a symlink and
recreated as one: the bytes at the other end are not ours, and neither the
publish nor the rollback writes through them.

The guarantee is stated as what it is. Caught failures — an exception at any
replacement or during cleanup — leave the previous release exactly as it was.
This is **not** crash consistency: a power loss between two `os.replace` calls
still leaves a mixed set, and only a versioned directory with a single pointer
swap would fix that, which would change the documented output paths. The
docstring says so, and a test asserts the docstring says so.

Regressions: injected failure at each of the four replacements, crossed with
all-four, none, and two-of-four pre-existing outputs (12 cases); a successful
publication writing all four from one generation; and the symlink case, which
also asserts the link target's bytes are untouched.

### 2 (BLOCKER) Closure membership is an exact set, bound outside the manifest

Removing one compiler-recorded figure CSV from `SOURCE_CLOSURE.json` left full
supplement verification green. The file's `.sha256` sidecar still verified its
bytes, and nothing required the file to be *in the closure*. A sidecar says
"these are the bytes I expect"; only the closure says "and the compiler read
this file".

`contract.COMPILED_CLOSURE` now pins all 89 entries — repository path, digest,
byte count, role and `ships_in` — in the package-contract module rather than in
the manifest it judges. Missing, extra, duplicated and remapped all fail, before
a single sidecar is consulted. Packaging refuses to build if what it is about to
record disagrees, in both directions.

Regressions: removal of one input from each class — ordinary manuscript source,
sidecarred figure CSV, sidecarred generated table, vendored package, venue
template, and the generated `main.bbl` — plus an extra entry and five field
remappings. The reviewer's exact reproduction, sidecar intact, is its own test.

### 3 (BLOCKER) Structural sources are held to their whole-file pin

`paper/macros.tex` and the symbolic rate table returned before the `FILE_PINS`
check. Redefining `\argmin` to render "arg max" and updating the closure entry
to match passed the complete shipped verifier: the specialized checks for those
two files — declarations only, cells that parse as asymptotic rates — are blind
to a renamed operator.

The whole-file pin now runs for every non-regenerated audited source, **before**
the structural short-circuit, and the specialized checks remain as additions. A
structural test asserts the ordering so it cannot regress. The pins are not
self-authorizing: `FILE_PINS` lives in `tools/numeric_context_pins.py`, whose
digest is pinned in the contract module and checked before any pin is read.
Regenerated-evidence semantics and the NOT_EXECUTED cases are unchanged.

### 4 (MEDIUM) Both manifest comparisons are complete

`check_pending_release()` compared deliverable hashes and member *names*, so a
member whose bytes changed under an unchanged name went through.
`--compare-manifest` compared only the `deliverables` block, ignoring every
archive inventory, the external-input records, the anonymization metadata and
the shipped-tool pins.

Now: every member's path, byte count and SHA-256 is recomputed from the pending
archive; every top-level record class is validated against its pinned value; the
shipped `SOURCE_CLOSURE.json` is checked against the contract before publication;
and `--compare-manifest` compares the **complete canonical manifest byte for
byte** after the same deterministic serialisation the build uses.
`MANIFEST_RECORD_CLASSES` lists the ten record classes, so a new one has to be
added there — which is the moment to give it a check. There is no
non-authoritative field; anything that did not need validating was removed
rather than skipped.

Regressions: 20 tampering cases, one per record class plus per-member hash and
size changes, duplicate members, and unknown or missing top-level keys.

### 5 (LOW) The revision floor covers every prior candidate

`eafcf90c…`, `e32de5bd…` and `86b81252…` join the static record, which is the
floor a clean checkout has with no reflog and no local objects. The regression
scans full, abbreviated and mixed-case forms of every prior candidate against
that static list alone.

### 6 (LOW) The whitespace exemption covers only pinned upstream bytes

`paper/texmf_vendor/** -whitespace` also exempted `VENDORED-PACKAGES.md`, which
is prose this project wrote. The exemption is now listed file by file for the 49
pinned upstream files, and the authored note has `whitespace` explicitly
re-enabled. A regression clones the checkout, appends trailing whitespace to
each, and asserts `git diff --check` reports the authored file and not the
vendored one.

### 7 (LOW) Current release facts are machine-checked

The README said `~0.8 MB` for a 3,420,977-byte archive and "roughly 14 MB" of
headroom against 15.8 million bytes. It now carries a **Current release** table
whose every figure a test recomputes from the built artifacts: the four sizes,
both member counts, both unpacked totals, the exact headroom, the percentage of
the limit, and the closure's 89 entries split 40/48/1. The report's own current
values are regenerated from the final bytes; historical figures appear only
where they are labelled as history.

### 8 (LOW) `main.bbl` is described as what it is

The manifest said every entry outside the supplement was in `source.zip`. That
was wrong for `main.bbl`, which bibtex writes during the build and which no
archive carries. The boolean `in_supplement` is replaced by `ships_in`, with
three values — `supplement`, `source`, `neither` — and the schema is version 2.
The supplement README explains all three and says plainly that the one `neither`
entry is verifiable by unpacking `source.zip` and running bibtex; a test does
exactly that and gets the pinned digest back.

## 9k. The rereview's four findings

A rereview of the previous candidate returned BLOCK with **1 BLOCKER, 1 MEDIUM
and 2 LOW**. Both technical defects were reproduced here before anything was
changed; the reproductions are `R12-repro-publish.log`,
`R12-repro-rollback.log` and `R12-repro-manifest.log`.

### 1 (BLOCKER) The publication rollback is complete and verified

The previous rollback iterated a list of names the *successful* writes had
appended to, which two attacks walked straight through.

* An exception raised **after** the second replacement completed left
  `source.zip` new beside three old files — that name had not yet been
  appended, so the rollback never touched it.
* An exception **during** a rollback write aborted the rollback with two files
  already replaced, and a `finally` then deleted the backup directory, which was
  the only copy of the old bytes.

The rollback no longer consults what succeeded. It restores all four paths from
the complete prepublication snapshot, unconditionally: a regular file goes back
with its bytes and its mode, a symlink is recreated as a symlink, an absent path
is removed. Each restoration is attempted independently — one failure does not
skip the other three — and each is then verified against the snapshot: digest,
byte count and mode for a file, link target for a symlink, absence for an absent
path. The restore writer is separate from `atomic_write_bytes`, and nothing
reads or writes through an output symlink in either direction.

The backup is deleted only when all four verify. If any does not,
`ReleaseRecoveryError` names the exact retained recovery directory and every
failed restoration, and says nothing about the old generation being back.

Scope is unchanged and still stated plainly: caught application failures are
covered, crash and power-loss consistency are not, and only a single atomic
generation switch would change that.

Regressions, all in `tests/test_tmlr_release_package.py` — 34 cases:

* failure injected **before** each of the four replacements, crossed with
  all-existing, none-existing and mixed prior sets (12);
* failure raised **after** a replacement had already completed, same crossing
  (12) — this is the reviewer's first attack, and it is the one the old
  success-list rollback could not see;
* failure **inside** `atomic_write_bytes`, between the temporary write and the
  `os.replace`, at each of the four steps (4);
* a rollback writer that fails on one path: `ReleaseRecoveryError` is raised,
  the durable recovery copy is retained and named, it holds the old bytes, the
  other three paths are restored anyway, and no restore temporary is left
  behind;
* one restoration raising does not skip the rest — all four are attempted and
  the failure is reported per path;
* a clean recovery deletes the backup, so retention means something;
* a pre-placed output symlink is recreated and its target's bytes are asserted
  untouched;
* exact success publication, and the whole-set move.

### 2 (MEDIUM) The last prepublication gate is authoritative

The reviewer changed the build metadata, the external-input names, hashes and
sizes, and the anonymization digests; removed a deliverable record; and replaced
the staged manifest file while keeping the original in-memory object.
`check_pending_release()` returned **no findings** for any of it, because it
compared the manifest against itself.

`derive_release_manifest()` is now the only place a manifest is built, and the
gate calls it again rather than re-serialising the build's object. Deliverable
digests come from the pending bytes; archive inventories are recomputed member
by member from the pending archives; external inputs are re-resolved through the
engine's own TeX variables and re-hashed from the files on disk; the shipped-tool
pins, anonymization token and declaration name come from the contract; the build
record and schema are pinned constants. The anonymization records are checked
field by field against `contract.CONTRACT` before anything else. Then the gate
reads `release_manifest.json` **back from disk** and requires exact canonical
equality with that derived expectation, so no field escapes — the comparison is
over the whole document. `--compare-manifest` uses the same contract and
additionally requires every record class to be present in both.

Two things are deliberately checked **outside** that comparison, because a
manifest derived from the archives cannot catch them:

* `check_shipped_closure()` holds the `SOURCE_CLOSURE.json` inside
  `supplement.zip` to `contract.COMPILED_CLOSURE`, entry set and every pinned
  field. The manifest records that member's digest, so a build that shipped a
  drifted closure and then hashed it would agree with itself perfectly. The
  contract is the only party to the comparison that lives outside both.
* `check_derived_manifest()` judges the derived expectation itself. Byte
  equality is worth exactly as much as what it compares against: an external
  input that no longer resolves is recorded with an empty digest and zero
  bytes, and a manifest derived from that degenerate record matches the staged
  file exactly. So the derivation has to be non-degenerate — real digests,
  positive byte counts, `trusted` on every external input, a non-empty input
  list, exactly the three hashed deliverables, no duplicate archive member.

Regressions: 33 tampering cases parametrized over every record class, each one
applied to the **staged file** rather than to an object, covering every reviewer
mutation, missing and extra deliverable records, top-level extra or missing
fields, wrong scalar types (a boolean `schema_version`, a list where `build`
belongs, a string where the external-input list belongs, a scalar where a
deliverable record belongs), duplicate archive members, and per-member digest
and size drift. Plus the reviewer's exact staged-file-versus-in-memory attack,
an anonymization record edited away from the contract, a closure with an entry
removed and one with an entry's digest rewritten (both with the manifest
restaged so every hash agrees), and the degenerate-expectation case. The
untampered staged release is clean.

Housekeeping found on the way: `check_pending_release` and `publish_release`
each existed twice in `package.py`, an artifact of an earlier patch that matched
the wrong anchor. The later copy shadowed the earlier one, so behaviour was the
later definition in both cases, but it meant the file carried dead code that
read as authoritative. Both duplicates are gone.

**What the first full-suite run caught, and it was a real defect.** Changing
`check_pending_release`'s second argument from the manifest object to the
anonymization transforms broke 23 tests that still passed a manifest, and one
more asserted the old docstring wording. Repairing them was not just a signature
edit: the rewritten gate had **dropped** the shipped-closure check the previous
version had, and nothing in the byte comparison replaced it. A staged release
carrying a drifted `SOURCE_CLOSURE.json` with a consistent manifest would have
published. That check is restored above, with two regressions that only it can
fail, and the derived-expectation checks close the matching hole on the other
side. The suite run is what surfaced this; it is recorded here rather than
quietly fixed.

### 3 (LOW) The README says what is actually bundled

It claimed only the venue template was bundled and everything else was stock TeX
Live, while `source.zip` also carries 46 files from four third-party packages
and three licence texts. The dependency table now has an explicit "In
`source.zip`?" column: the venue template, `mathtools`, `cleveref`, `pgfplots`
and `microtype` are bundled; `rotating` and `cm-super` are external. A test
cross-checks every row against the real archive membership.

### 4 (LOW) The report's test count is derived, not retyped

The report said 402 release-package tests, the pre-amend R11 figure; the R11
post-amend run had 403. The current count is read from the final-SHA run and
asserted against the suite itself by
`test_the_report_states_the_current_release_package_test_count`, which collects
this file and compares, so it cannot go stale again — it went from 405 to 441
inside this pass and the test caught it both times. 402 and 403 survive only in
the R11 ledger, where they describe those earlier runs.

## 9l. The eighth review's six findings

An independent reviewer verified the previous pass's fixes and returned BLOCK
with **4 BLOCKER, 1 MEDIUM and 1 LOW**. All five technical findings were
reproduced here first, in `/home/buiksat/cce-tmlr-work/repro-r13/`; the logs are
`R13-repro-1.log`, `R13-repro-2a.log`, `R13-repro-2b.log`, `R13-repro-3.log`,
`R13-repro-4.log` and `R13-repro-5.log`, and the same attacks against the fixed
code are `R13-fixed-*.log`.

The theme is one the previous passes half-fixed. A check is worth nothing when
both sides of it come from the same object: last pass that was the manifest
comparing itself, and this pass it is an archive inventory recomputed from the
archive, an external-input set read back out of the cache that produced it, and
a transform record compared with the caller that supplied it.

### 1 (BLOCKER) Rollback verification is attempted for every deliverable

Restoration was already independent per path; verification was not. A raise
inside `verify_restored` on the first file abandoned the loop, so the other
three were never checked, the exception escaped as a plain `OSError` rather than
`ReleaseRecoveryError`, and the mixed public set it left behind had its only
backup inside the staging directory the function then removed.

Each verification is now attempted in its own `try`, a raise is recorded as
`"<name>: verification raised ..."` and the loop continues. Reproduced:
`verify_restored was called for: ['main.pdf']`. After: all four, and a
`ReleaseRecoveryError` naming a durable directory.

### 2 (BLOCKER) The recovery copy is created, never taken over

`retain_recovery` writes to a fresh `mkdtemp` directory under the output tree
with the `.release-recovery-` prefix. It never deletes, reuses or follows an
existing path, which closes both halves of the finding:

* a pre-existing `.release-recovery` **directory** used to be `rmtree`'d, which
  destroyed an earlier failed generation's only copy. Reproduced; it now
  survives untouched.
* a pre-existing `.release-recovery` **symlink** used to be followed by
  `shutil.move`, so the backup landed in a directory outside the output tree
  while the reported path still said otherwise. Reproduced — the external target
  received `.previous`, `main.pdf`, `source.zip`, `supplement.zip` and
  `release_manifest.json`. It is now empty after the same attack, and the
  reported path is a real directory inside `out`.

The complete snapshot metadata is serialised beside the retained files as
`RECOVERY.json`, with the original failure and every unrestored path. If even
that move fails, the staging directory is kept and the error names the backup
inside it, because at that point it is the only copy.

This is caught-failure integrity. It is not crash or power-loss atomicity, and
the docstring still says so.

### 3 (BLOCKER) Archive inventories are derived outside the archives

`expected_source_members` re-parses `main.fls` through `closure()` and hashes
the staged files the compiler read. `expected_supplement_members` walks
`supplement_entries(repo)` and hashes the repository files, with three
deliberate exceptions, each bound to something pinned rather than waved through:
a file the anonymizing transform rewrote is bound to `contract.CONTRACT`'s
packaged digest, its regenerated sidecar to `contract.sidecar_text`, and the two
documents the build generates — `ANONYMIZATION.json` and `SOURCE_CLOSURE.json` —
are derived byte for byte from the transform records and from
`contract.COMPILED_CLOSURE`. `check_archive_inventory` then reports missing,
unauthorised and byte-drifted members separately for each archive.

Reproduced on both archives, four ways each, regenerating the manifest from the
mutated archive every time: renamed, byte-changed, added and removed members all
passed. All eight now fail, and a ninth check confirms the two real built
archives match their derived inventories exactly.

### 4 (BLOCKER) External inputs come from the recorder, not from a cache

`EXTERNAL_INPUT_CACHE` is deleted. `derive_external_inputs(repo, src)` re-runs
`recorder_inputs` against the staged tree, so membership follows the `.fls` file
pdfTeX wrote and there is nothing in between for a caller to edit. Reproduced:
deleting one of 249 entries before derivation produced a 248-entry manifest that
passed. A regression appends a real trusted `article.cls` to a cloned `.fls`,
sees the derived set grow by exactly that record, removes the line and sees it
return — and asserts the module has no such cache attribute any more.

### 5 (MEDIUM) Anonymization records are derived, and the build's are compared

`derive_anonymization_records(repo)` builds one record per `contract.CONTRACT`
path from pinned constants, the contract's digests and the removed value
re-extracted from the original evidence in the repository.
`check_anonymization_record` enforces exactly `TRANSFORM_RECORD_KEYS`, exactly
one record per contract path, no extras and no duplicates, and every descriptive
field against its constant. What `anonymize()` reports is passed to the gate
only so `check_reported_transforms` can disagree with it; it is never an
authority. Reproduced: a changed descriptive field, a removed `source_path`, an
extra key and a duplicated record all passed. Each now fails twice — once as a
reported/derived disagreement and once against the derived set itself.

### 6 (LOW) The final audit numbers are read from the final run

The results table was labelled R11, the combined-suite figure was 525 from two
passes ago, and revision coverage said 141. The first two were corrected from
the R13 logs, and the combined-suite count is now asserted against the suites
themselves by `test_the_report_states_the_current_repository_suite_count`, the
way the release-package count already was.

The revision coverage was corrected to the wrong numbers -- 142 and 144, when
the logs that pass named say 144 and 145. See section 9m, finding 4.

## 9m. The ninth review's four findings

An independent reviewer reproduced four findings against the previous candidate.
All three technical ones were reproduced here first, in
`/home/buiksat/cce-tmlr-work/repro-r14/`; the logs are `R14-repro-1a.log`,
`R14-repro-1b.log`, `R14-repro-1c.log`, `R14-repro-2.log` and
`R14-repro-3.log`, with `R14-fixed-*.log` showing the same attacks afterwards.

### 1 (BLOCKER) The recovery backup moves as one directory, or not at all

Retention created a new directory and then moved the backup into it **entry by
entry**, writing the metadata afterwards. Three failures followed from that
shape, and all three were reproduced:

* a failure on the second move left `release_manifest.json`, `source.zip` and
  `supplement.zip` in `.previous` — the reported path — and `main.pdf` in a
  `.release-recovery-…` directory nobody was told about, with no metadata in
  either;
* a failure writing the metadata left the reported `.previous` **empty** and all
  four files in an unreported directory, again with no `RECOVERY.json`;
* a retry into the surviving staging directory succeeded and took the residual
  backup with it, because `publish_release` begins by resetting `.previous`.

The transaction is now: write `RECOVERY.json` inside `.previous` and fsync the
file and the directory, then relocate the **whole directory** with one
`os.rename` to a name that did not exist, then fsync the parent. A rename within
one filesystem is atomic, so there is no state where part of the backup is in
one place and part in another. Either it all moved, or none of it did and
`.previous` is still complete and self-describing.

If retention fails anyway, `recovery_locations()` enumerates every directory
under the output that holds recovery material and the error names all of them
with their contents, rather than assuming one. And
`residual_recovery_problem()` refuses to start a publication while `.previous`
holds a previous generation, so no retry can erase it; clearing it is a
deliberate human act.

Regressions: a failed backup move, a failed metadata write, the retry, a clean
retention, and the scratch-name primitive. Each asserts file contents and the
reported location, not only the exception type.

### 2 (MEDIUM) Symlink restoration owns its scratch path

The rollback recreated a `main.pdf` symlink through a fixed
`.main.pdf.restore-link`, which it deleted before use. Everything about the
rollback was right except that an unrelated file with that name was destroyed.
Reproduced. `unique_scratch_symlink()` now creates the link at a random name
with `os.symlink`, which fails with `EEXIST` rather than replacing anything, so
creation is the test and only the path this call made is ever removed.

### 3 (MEDIUM) Anonymization digests are computed from the current bytes

`derive_anonymization_records` re-extracted the removed revision from the
repository but copied all four digests and byte counts straight from
`contract.CONTRACT`. A reviewer changed evidence bytes while leaving
`git_revision` alone; every derived record came back identical to the contract
and the complete pending-release gate returned no findings. Reproduced against a
disposable clone.

The digests and byte counts are now computed from the bytes on disk and
`check_anonymization_record` compares them with the contract, so the comparison
has two independent sides. An end-to-end regression mutates a clone's evidence,
preserves the revision field, and asserts the complete gate rejects it on both
`original_sha256` and `packaged_sha256` — and asserts the repository's own bytes
are untouched, since the fixture copies rather than links.

### 4 (LOW) The revision counts match the logs they cite

Section 9l corrected 141 to 142 and 144. Those were still wrong: the logs it
pointed at record **144** before the amendment (`R13-build-release.log`,
`R13-archive-scan.log`) and **145** at the final commit
(`R13-build-postamend.log`, `R13-archive-scan-postamend.log`), which the
reviewer observed independently. Every occurrence now reads 144 and 145 and
names the exact log. The pin-count discussion is unrelated and unchanged.

## 9n. The tenth review's five findings

An independent panel reported five surviving findings against the previous
candidate. All four technical ones were reproduced here first, in
`/home/buiksat/cce-tmlr-work/repro-r15/`; the logs are `R15-repro-1.log`
through `R15-repro-4.log`, with `R15-fixed-*.log` showing the same attacks
afterwards.

### 1 (BLOCKER) The residual-recovery guard is at the CLI boundary

`publish_release` refused to run over an unrecovered `.pending/.previous`, but
`main()` had already called `reset_build_directory(pending)` by then, and that
deletes `.previous` with everything in it. Reproduced through the real CLI: a
residual backup holding the only copy of a previous generation, `main()`
returning **0**, the backup gone and the public release replaced. Data loss, not
a rejected publication.

The check now runs immediately after the output directory is resolved and before
anything in the process creates, resets or removes a directory under it; the CLI
exits **13** and says nothing was read, written or removed. The guard inside
`publish_release` stays, for the library entry point. A structural test asserts
the guard precedes every `reset_build_directory`, `shutil.rmtree`, `stage` and
`anonymize` call in `main()`, and an end-to-end test drives the real `main()`
and asserts every recovery byte, the unchanged public release and the exit code.

### 2 (BLOCKER) The recovery record is durable before the first replacement

Metadata was first written during retention, after public bytes had already
moved. A reviewer gave the prior release a `main.pdf` symlink and no
`supplement.zip`, failed the metadata write, and got a retained directory of
regular files with no `RECOVERY.json`, no link target and no record of the
absent entry — neither of which leaves a file behind, so the directory could not
be interpreted at all.

`write_recovery_metadata` is now called twice: once with
`stage: "prepublication"` before the first replacement, fsyncing both the file
and the directory entry, and once during retention to add what could not be
restored. If the first write or its fsync fails, publication aborts with the
public release untouched and says so. If the second fails, that is recorded as
one more problem and retention continues — the directory is already
interpretable. The R14 whole-directory atomic relocation is unchanged.

Regressions: metadata-write and fsync faults before the first replacement, each
with a prior symlink and a prior absent deliverable, asserting exact public
state; and a retention-update fault asserting the retained record still names
the symlink target and the absent entry.

### 3 (BLOCKER) Staged compiled sources are bound to the committed contract

`expected_source_members` hashed the staged files, so the staged tree was its own
authority. A reviewer changed a staged manuscript source **and** the matching
`source.zip` member, regenerated the manifest, and `check_pending_release`
returned an empty list; a clean rebuild of that archive produced a different PDF.

`expected_staged_sources` now takes every digest from
`contract.COMPILED_CLOSURE`, which is committed, and from the repository files
that `stage()` copies the six non-compiled extras from — `references.bib`,
`tmlr.bst` and the four licence texts, named by the same constants `closure()`
and `stage()` use. `check_staged_sources` holds the staged tree to that
inventory and separately requires the compiler's own recorded input list to be
exactly the pinned set. `expected_source_members` is the same inventory minus
the one entry the contract marks `ships_in == "neither"`. Nothing in either
reads `src/`, `source.zip` or the release manifest for its expectations. The
anonymizing transformation stays explicit and pinned on the supplement side,
with both original and packaged bytes verified.

`check_archive_inventory` also rejects a member listed twice and a member whose
mode says it is not a regular file.

Regressions: the reviewer's end-to-end mutation with every caller-controlled
artifact regenerated; missing, renamed and symlinked staged sources; an extra
compiled input; duplicate members in both archives; a symlink member.

### 4 (MEDIUM) Unreadable recovery locations are reported, not raised

A pre-existing recovery directory that could not be enumerated raised
`PermissionError` out of the failure handler, replacing the structured
`ReleaseRecoveryError` and taking the known backup path with it. Reproduced by
fault-injecting `Path.iterdir`, so the result does not depend on this process
being stoppable by `chmod`.

`directory_contents` returns names or an explanation, never raises, and every
recovery path is inspected through it. An unreadable candidate counts as a
surviving recovery location, is never cleaned up, and appears in the error with
the underlying failure. The residual guard fails closed the same way.

### 5 (LOW) The results table cites this pass's logs, and no volatile count

The table said every number came from the R14 run while its build and archive
rows cited R13 filenames and R13's 144/145; R14's own scans recorded 145 and
146; and it named `R14-build.log`, which does not exist — the pre-amend file is
`R14-build-release.log`.

The scanner's population is `package.project_revisions`: the union of
`RECORDED_PROJECT_REVISIONS`, `git rev-list --all`, `git reflog --all` and
`HEAD`. Amending adds a reflog entry, so the count rises by one with every
amendment and no number written into the commit being measured can survive it.
The rows now describe the check and name the final immutable log rather than
hardcoding a figure that a second report-only amendment would invalidate again.
Every other row cites an `R15-` log. Section 9m's historical R13 correction is
unchanged.

## 9o. The eleventh review's two findings

Both were reproduced here first, in `/home/buiksat/cce-tmlr-work/repro-r16/`;
the logs are `R16-repro-1a.log`, `R16-repro-1b.log`, `R16-repro-2.log` and
`R16-repro-2_regular.log`, with `R16-fixed-*.log` showing the same cases
afterwards.

### 1 (MEDIUM) The recovery destination is recorded at the rename, not inferred

`retain_recovery` fsynced the output directory after the rename and returned
only on success. When that fsync failed, nothing had recorded where the
directory had gone, so `publish_release` fell back to scanning `out` for
`.release-recovery-*` names. Two ways that misleads, both reproduced with an
older recovery generation named so it sorts first:

* the scan succeeded and the **older** generation was reported as the primary
  backup, with the just-retained one listed second;
* the scan also failed, and the error said "no recovery material could be
  located" while naming the staging backup that the rename had already emptied
  — the current destination appeared nowhere at all.

No bytes were lost either way, but an operator following the error would have
recovered the wrong generation.

The destination is now appended to a caller-supplied `relocated` list the
instant `os.rename` returns, before the fsync. On failure that path is the
structured error's primary backup and the first reported location; anything the
scan finds is appended behind it, deduplicated, and never allowed to precede it.
`recovery_locations` reports its own inspection failures through a `troubles`
out-parameter instead of swallowing them, so "there is nothing else" and
"nothing else could be looked at" are no longer the same message. Nothing is
deleted in any branch.

Regressions: rename-success plus parent-fsync-failure, with output-directory
enumeration both working and failing, each in the presence of an older recovery
directory, asserting the primary path, every reported location and inspection
failure, and the exact preserved bytes in both generations. Plus a structural
test that the append sits between the rename and the fsync.

### 2 (MEDIUM) Archive members are checked against the full Unix type field

`check_archive_inventory` tested `S_ISLNK` and `S_ISDIR` only. A member whose
mode said FIFO, character device, block device or socket passed the complete
publication gate with a matching name and payload, leaving the outcome to
whatever the reviewer's extractor does with such an entry. Reproduced on all
four through `check_pending_release`, not through the helper.

`member_file_type` now reads the creator field first — only Unix and Mac OS X
record a Unix mode there — and then the whole `S_IFMT` field, accepting an
absent type field and `S_IFREG` and naming everything else, including a type
this platform does not define. The duplicate, membership and content checks are
untouched.

Regressions: each of the six irregular types through the full gate; five
supported regular-file metadata variants that must keep passing (Unix regular,
Unix permission bits with no type field, Mac OS X creator, MS-DOS creator,
NTFS creator); a well-typed member with the wrong bytes, which must still be
rejected on content; and the helper directly.

## 10. Protected material

Recorded before and after; the two inventories are **identical**.

Unchanged, byte for byte and blob for blob:

| Path | Git blob | SHA-256 |
|---|---|---|
| `paper/main.pdf` | `4e977c49213c031111cdddcee03db90afcd17d48` | `2545c368d6b97393f5c1e5bb61d4696f7fed6b8ae988ce42c9d7bc7ccab717e1` |
| `paper/main.pdf.sha256` | `ad30d8335c114e431241129bb1b6d84845860eba` | `3de3d2f674c720985d149d235422e83d925b2a0dce3c63c2af2bee98d8cde80f` |
| `submissions/code_mit_2026/main.tex` | `f1406cdf9b687acc88b1b5de020e5b75a5ed4477` | `34775e7b111ab96a445b1d70666606506a2a4f9ac19c00aebdc96a8360844d40` |
| `submissions/code_mit_2026/main.pdf` | `76500806b5ccf561c9b02e3a7c4281a5af183f84` | `48981b159fe4c2bdb85ae1ebee3e80e5ec9d1b3879757ab427f8af454cc6dd64` |
| `results/derived/.../full_aggregate.json` | `aac10364c27b9a401dca78c50708c8f0d432628e` | `0ddebd4915dd2e264e24b7b25047d24f86c3cdf63930a1e6df77585e0b97de02` |
| `results/derived/.../selection.json` | `919a612b816c05ce3947a6fadf4b316790b65740` | `8c16bec7cc220109df3fd7173c3d06ae6c6e1b95e9db5bc5b8c3377b3564f6f4` |

Tree digests, before → after:

```
review/          221619c9c07316255b2b88fdbfdcde83903b946dbb94d61e2dc4832602664a0a  (unchanged)
results/derived/ ea75ce11cdba0ebf1d0089a8fe1e5f8ecde69738000998c97e07411aca43b7f4  (unchanged)
experiments/     0bea465b7e2c637c3014c77d00e4920d27c79a4ff49b331826ca65a974ab60be  (unchanged)
```

All 92 tracked files under `paper/tables/` (20) and `paper/figures/` (72) are
unchanged, blob for blob. The manuscript sources that typeset them —
`paper/transport_experiment.tex` and `paper/transport_experiment_appendix.tex` —
did change, but they are sources, not generated artifacts. All 71 `*.sha256`
sidecars verify from their own directories, and
`submissions/code_mit_2026/SHA256SUMS` verifies.

Blob-for-blob comparison against START over every tracked path under
`paper/main.pdf`, `paper/main.pdf.sha256`, `paper/tables/`, `paper/figures/`,
`results/`, `review/`, `experiments/realistic_transport/`,
`submissions/code_mit_2026/` and `third_party/`: **329 protected paths at START,
329 now, zero differences.**

`git diff --name-only START..HEAD` lists **95** changed or added tracked paths,
fifty of them the vendored package tree added in section 9i.
`R16-protected-inventory.log` and `R16-changed-from-START.txt` are generated from
the amended commit rather than from the index, which is what made an earlier
pass's log say 41 and omit `paper/transport_theory.tex`. Both external logs name
the exact final SHA; no tracked file carries a self-reference to the commit that
contains it.

`paper/main.pdf` was never rebuilt. `make pdf`, `make cleanall` and every
artifact-generating path were kept out of the working tree; every side-effecting
check ran in a disposable copy made with `git archive`, and the artifact
regeneration is in-memory by construction with a test asserting it writes
nothing.

One housekeeping note, recorded because it briefly perturbed the `experiments/`
digest: running the tools from the repository root created 44 gitignored
`__pycache__`/`.pyc` files and a `.pytest_cache`. All were inventoried
(`/home/buiksat/cce-tmlr-work/logs/cache-removal-inventory.txt`), confirmed
untracked, and removed. The digest then matched START exactly.

## 11. Deferred, and not cleared

The realistic Covertype/Nyström extension is **deferred and excluded**, and this
submission does not depend on it.

- No authentic Covertype data was prepared. No pilot, tuning, fallback or
  evaluation run. No project F or L commit.
- The raw-grid discovery defect is still there, untouched:
  `experiments/realistic_transport/aggregate.py` does
  `int(seed_text.removeprefix("seed-"))`, which maps the physically distinct
  `seed-100` and `seed-0100` directories onto the same integer-keyed cell.
- The Buck preparation closure remains build-blocked, and the last independent
  review left R12 PARTIAL and R13 BUILD BLOCKED with the B1–B4
  evidence-integrity findings open.
- Its 297 tests pass under the portable route, unchanged from START. **That is
  not clearance.** Those tests exercise trust boundaries against fixtures; they
  do not and cannot establish that the study's evidence path is sound, and the
  repository's own repair record says so.

Two of those tests broke on my first workflow edit and were fixed by changing my
edit, not the tests: the required-pipeline name list and the package-aware Buck
resource oracle. `experiments/realistic_transport/` was not modified.

## 12. Unresolved

Technical, in this repository:

1. **The declared Buck2 runtime cannot parse the build graph on this host.**
   Pre-existing, environment-caused, blocks every `buck2 test`/`buck2 run`
   command in `BUCK2_SETUP.md` and `README.md`. Needs a pinned-buck2 bump or an
   older host checkout; both are dependency decisions.
2. **`experiments/requirements.txt` pins `scipy==1.15.2`, the bundled wheel is
   `scipy-1.13.1`.** The declared runtime and the checked-in dependency disagree.
   No effect on any reported number, but it should be reconciled.
3. **Raw trajectories remain missing** and were not reconstructed from
   aggregates. Two ledger checks and four verifier checks stay NOT EXECUTED. In
   a repository preflight a third ledger check is NOT EXECUTED as well: without
   `SOURCE_CLOSURE.json` the audited set comes from an `\input` walk, not from
   the compiler, and the tool now says so rather than implying it certified a
   release.
4. **The three wide evidence tables are landscape floats.** That is the only way
   to give them the body font size and the template's spacing on a 6.5 in
   measure without editing the generated bytes, and it is a normal typographic
   device, but a reader has to rotate the page. Splitting each table's columns
   would avoid that and would require regenerating locked artifacts, which is
   out of scope here and an author decision.
5. **`rotating` is a LaTeX dependency of the submission.** It is now documented
   in `submissions/tmlr_2026/README.md` with the TeX Live, Debian and RHEL
   package that supplies it, and `source.zip` still rebuilds the PDF byte for
   byte from a clean unpack, but it is one more package a reviewer's
   installation has to have and it is not bundled.
6. **The layout gate reads tokens, not a typeset document.** It now fails closed
   on constructs it cannot read — opaque conditionals are scanned in full,
   `\csname` and friends are findings — but it is still a source check. What
   rules out a shrunken table in the *output* is the zero-overfull build plus
   inspection of all 68 rendered pages, both recorded above.
7. **The number audit's classification table is maintained by hand.** 76
   `(file, literal)` pairs with a category and a rationale, plus 74 declared
   phrases. The 485 semantic units and 23 whole-file digests behind them are
   generated, but the categories are not. That is deliberate friction: a new
   constant in a proof requires an explicit entry. It also means the table has
   to be reviewed, not just trusted, and a check rejects entries naming files
   outside the closure so it cannot quietly rot.
8. **Four LaTeX packages the PDF depends on are carried by the submission
   rather than supplied by the distribution.** TeX Live 2020 on el9 does not
   package `pgfplots`, `microtype`, `cleveref` or `mathtools`, and an
   unprivileged account cannot install into a root-owned tree, so section 9i
   vendored all four into `paper/texmf_vendor/` under their own licences. The
   build no longer reads a single byte from a user tree, and `main.pdf` is
   byte-identical either way. What remains is maintenance, not exposure: a
   package upgrade is now a deliberate, digest-pinned change in this repository
   instead of something the host does underneath. A host whose distribution
   carries these four would let the vendoring be dropped.
9. **The supplement is 84.2% of the venue's size limit.** Storing rather than
   deflating bought an archive hash that does not depend on an unpinned zlib,
   and cost 73 MB of compression. 15,809,471 bytes of headroom is comfortable
   but not large, and the archive is dominated by one 77 MB committed evidence file. A
   build that crosses 100,000,000 bytes fails; crossing it means pinning a
   compressor into the declared build closure, not reverting to deflate.

10. **Release publication is transactional for caught failures, not for
   crashes.** An exception at any replacement or cleanup step restores every
   previously published deliverable byte for byte and removes any that was
   absent; twelve injected-fault cases assert it. A power loss between two
   `os.replace` calls still leaves a mixed set. Fixing that means a versioned
   release directory with one pointer swap, which changes the documented output
   paths, so it was not done; the docstring says what is and is not guaranteed.

Nothing above is a correctness defect in the manuscript, and no material
unresolved gap in the science was found.

Author-side, none of which an implementer can settle:

4. Author list, order, affiliations, OpenReview profiles, and remaining
   authorship quota.
5. Domain and personal conflicts of interest.
6. Funding and competing interests.
7. Recommended action editors.
8. **Whether the CODE@MIT abstract was actually submitted**, and if it was, a
   written non-archival declaration or a disclosure to the action editor.
9. Whether the coauthor self-citation should stay as-is.
10. The exact wording of the AI-assistance disclosure.

## 13. Bottom line

The technical candidate is ready: it builds deterministically, it is typeset at
the template's font size and spacing throughout, its PDF is anonymous and
reproducible from `source.zip`, its supplement ships the active evidence closure
and verifies from a clean unpack, every reported number re-derives from locked
evidence *and* every number that does not is a build failure, and every check
that can run here returns zero with the ones that cannot explicitly labelled NOT
EXECUTED.

Release is held on author consent and the CODE@MIT overlap question. Both are
human decisions, and neither is a defect in the work.
