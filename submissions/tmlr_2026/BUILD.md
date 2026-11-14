# Build the anonymous manuscript

From the repository root, with TeX Live, latexmk and Poppler installed:

```bash
openout_any=a TMLR_OUT=/tmp/cce-tmlr bash submissions/tmlr_2026/build.sh
```

`TMLR_OUT` must be outside the checkout. This command creates `main.pdf` and
`source.zip`, checks the unchanged official style hashes, and rejects undefined
references/citations and missing characters. `openout_any=a` permits BibTeX's
out-of-tree log/output writes on TeX Live installations that restrict them.

From a standalone manuscript source archive, run:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

In Overleaf, set the Main document to `main.tex` and use pdfLaTeX. Keep the
anonymous TMLR mode without `accepted` or `preprint`. The official TMLR style,
bibliography style, bundled fancyhdr and license are unchanged.

Required packages include AMS, mathtools, algorithm, algorithmic, cleveref,
booktabs, tabularx, pgfplots, enumitem, microtype, float, placeins, aliascnt and
Latin Modern fonts. A TeX Live installation with latex-extra, science, pictures
and recommended fonts provides these. No experiment runtime is needed to
compile the manuscript.

The source archive includes active manuscript inputs and rendered figures.
The retained CSV inputs are available in the repository; they are not included
in this archive.
It is not an experiment-code or raw-data supplement. Repository terminal-table
regeneration and verification commands are documented in `README.md`.
