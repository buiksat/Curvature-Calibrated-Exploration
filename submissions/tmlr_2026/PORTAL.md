# Private OpenReview portal text — TMLR

**Not part of any upload.** `package.py` refuses to place this file in
`source.zip` or `supplement.zip`. It exists so that whoever submits does not
have to re-derive the form text, and so that the things an implementer cannot
decide are visible as decisions rather than as blanks.

Portal: <https://openreview.net/group?id=TMLR>. Submission is rolling; there is
no deadline to hit.

Every `DECIDE:` line below is an author decision. None of them is filled in
here, because filling them in would mean asserting something about people,
funding or consent that is not recorded anywhere in this repository.

---

## Title

```
Confidence Transport for Relinearized Curvature in Contextual Bandits
```

## Abstract

Paste the abstract from the compiled `main.pdf` (it is also the
`\begin{abstract}` block of `submissions/tmlr_2026/main.tex`). It is one
paragraph, as the template requires.

## Authors

Established author block, taken verbatim from the CODE@MIT derivative in
`submissions/code_mit_2026/main.tex`, which is the only place in this repository
where the author list is recorded:

1. Bahram Behzadian
2. Khurshid Juarev
3. Diego Granziol
4. Houssam Nassif

`DECIDE:` whether this list and this order are still correct for a TMLR
submission. TMLR fixes the author set at submission time and permits no
additions or removals afterwards, with no exceptions.

`DECIDE:` affiliations. The CODE derivative records employer strings for these
names; that is not the same as a current, confirmed affiliation for a different
venue, and it is not inferred here.

`DECIDE:` every author has an active OpenReview profile with education and
career history filled in. TMLR requires this of all authors at submission.

`DECIDE:` every author still has authorship-quota budget for the year. TMLR
applies the Generalized Harmonic Quota Rule with N_1 = 2 and N_9 = 9, doubled
for reviewers and action editors, and budget is spent even by desk-rejected
submissions. The calculator TMLR links is at
<https://www.cs.cmu.edu/~nihars/quota/author.html?rule=generalized&N1=2&A=9&NA=9>.

`DECIDE:` every author is aware of and agrees to this submission, and meets
TMLR's three authorship criteria (substantial intellectual contribution;
contributed to drafting or revising; takes full responsibility for the content).

## Conflicts of interest

`DECIDE:` domain conflicts, entered through each author's OpenReview Education &
Career History, covering at least the last three years.

`DECIDE:` personal conflicts — family or close personal relationships, PhD
advisor/advisee relationships, and current, frequent or recent collaborations
within the past three years.

One fact worth checking rather than assuming: the 2026 CODE@MIT page, accessed
2026-09-15, lists a "Houssam Nassif — Meta" on its LIFT Committee, and a
Houssam Nassif is the fourth author above. Whether those are the same person,
and whether that matters for any TMLR conflict declaration, is not something
this repository can establish.

## Recommended action editors

`DECIDE:` TMLR emails after submission asking for suggestions from
<https://jmlr.org/tmlr/editorial-board.html>. Nothing here can pick them.

## Human subjects / IRB

No human subjects. The reported study is a synthetic scaled-tanh contextual
bandit with simulated rewards; no data about people was collected or used.

## Funding

`DECIDE:` no funding information is recorded anywhere in this repository, and
none is invented here.

## Competing interests

`DECIDE:` see conflicts above.

## Prior and concurrent submission

Draft text, to be confirmed against what the authors actually did:

> A three-page extended abstract derived from this work was prepared for the
> 2026 Conference on Digital Experimentation at MIT (CODE@MIT), whose
> three-page stage-one deadline was 13 September 2026. The repository records
> that abstract as prepared and not uploaded; the submission portal was
> authentication-gated and was never reached. This submission is not an
> expanded version of a conference paper and has not been submitted in parallel
> to any archival, peer-reviewed venue.

`DECIDE:` **this is the single most important line to confirm before
submitting.** Two separate records in the repository say the CODE abstract was
prepared but not submitted, and one of them adds "Whether the abstract was
actually uploaded is not recorded here. Confirm before assuming." If it *was*
submitted, the paragraph above is false and must be rewritten.

`DECIDE:` if it was submitted, TMLR's exception for overlapping work requires
the other venue to be "publicly declared, in writing, to be non-archival". The
live CODE@MIT page on 2026-09-15 carries no call for papers and no statement of
archival status either way; an earlier reading of the 2026 call recorded
"accepted abstracts distributed as informal working notes", which is not the
same as a written non-archival declaration. Obtaining one from the organizers,
or disclosing the overlap to the TMLR action editor and letting them rule, are
the two clean routes. Do not resolve this by omission: TMLR retracts for
undisclosed redundant publication.

`DECIDE:` no arXiv or other preprint of this work is posted. TMLR permits
preprints at any time, but the double-blind submission must not link to a
version carrying author names.

## Licensing

TMLR submissions are licensed CC BY 4.0 from submission through publication;
copyright stays with the authors. No action needed, but the authors should know
this applies from the moment of submission.

## Broader impact

The paper contains a Broader Impact Statement. TMLR requires one only when the
work carries significant risk of harm; this one is short and factual about
exploration exposing users to under-vetted actions.

## LLM / AI-assistance disclosure

TMLR's policy states that LLMs may be used as general-purpose assistive tools,
that authors are fully responsible for all content, and that LLMs are not
eligible for authorship. It does not currently mandate a disclosure field. The
following is accurate for this manuscript and should be offered if the form asks
or if the authors choose to state it:

> AI assistance was used beyond grammar and copy-editing. It contributed to
> mathematical review and to the exposition of proofs, to review of the
> experimental methodology, to code and test development for the verification
> tooling, and to interpretation of results. All content is the authors'
> responsibility. The authors do not claim that every proof line was
> independently checked by a human, and do not claim that the reported
> experiments were independently reproduced.

`DECIDE:` whether the authors want to state more or less than this. Do not
weaken it into "AI was used only for grammar", which would be false, and do not
strengthen it into claims about human verification that nobody has recorded.

## Supplementary material

Upload `supplement.zip` from the build output. It is anonymous, is well inside
the 100 MB limit, and its `README.md` states plainly what it does and does not
let a reviewer check.

## Files to upload

| Upload | File |
|---|---|
| Manuscript PDF | `main.pdf` |
| Supplementary material | `supplement.zip` |

`source.zip` is not requested by TMLR at submission time. Keep it: it is what
makes the PDF reproducible, and a camera-ready will need it.

**Do not upload** `FINALIZATION_REPORT.md`, this file, or anything under
`submissions/code_mit_2026/`.
