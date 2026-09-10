# Build and page-budget record

All builds used:

```text
export PATH="/home/buiksat/bin:$PATH"
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

Toolchain: latexmk 4.70b; pdfTeX 3.14159265-2.6-1.40.21 (TeX Live 2020).

| Build | Content | Exit | Pages | PDF bytes | PDF SHA-256 |
| --- | --- | ---: | ---: | ---: | --- |
| Baseline | Unmodified `5718995` source | 0 | 3 | 212,379 | `9e65b1cc850a9c0d1b3fa3c7430e99825ee5d47e83639c89a6361aec2c456c56` |
| Batch 1 | A02, A01, F02, F01 | 0 | 4 | 212,411 | `d191fa86ecd2f092195806781614eb11d76785b8c14a0862e7320b7a892cbfe8` |
| Cleared candidate | All cleared manuscript blocks before AUTH01 | 0 | 4 | 215,794 | `3270827506f2775f99e93c860ee1623780998d4fbe0da6a52a16aac559b8e336` |
| AUTH01 candidate | Author name and affiliation; obsolete placeholder removed | 0 | 4 | 215,584 | `fe6799215f9ad7152bfb347c8e64f92509e5daf06eda7064930697c6aa8e0e66` |

Page counts used Ghostscript:

```text
gs -q -dNODISPLAY -dNOSAFER -c "(main.pdf) (r) file runpdfbegin pdfpagecount = quit"
```

The AUTH01 build log (`build/auth01-main.log`) contains no unresolved citations or references, package warnings,
errors, overfull boxes, or underfull boxes. Ghostscript text extraction contains the
author name, affiliation, review banner, and completed Nussbaum page range.

All four AUTH01 pages were rendered at 150 dpi with Ghostscript and inspected. Text,
mathematical displays, the result table, citations, the author line, and the review banner are visible and
legible. No clipping, overlap, broken symbol, or table overflow was found. The results
paragraph continues normally from page 3 to page 4.
The executor could view the PNG renders directly.

## Page-budget decision

**PAGE-BUDGET BLOCKED.** The established format permits at most three pages including
references and the author-review banner. The baseline occupies three pages; the first
coherent edit batch, the cleared candidate, and the AUTH01 candidate occupy four. AUTH01
did not change the page count. No font, margin,
hypothesis, theorem condition, or required qualification was reduced to force a fit.
