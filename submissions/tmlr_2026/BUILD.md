# Build the anonymous manuscript

With TeX Live and latexmk installed, run from this directory:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

In Overleaf, set the Main document to `main.tex` and use pdfLaTeX.
The official TMLR style, bibliography style, bundled fancyhdr, and license
are included unchanged. Use the default anonymous mode, without `accepted`
or `preprint` options.

Required TeX packages include the AMS packages, mathtools, algorithm,
algorithmic, cleveref, booktabs, tabularx, rotating, pgfplots, enumitem,
microtype, float, placeins, aliascnt, and Latin Modern fonts. A TeX Live
installation with latex-extra, science, pictures, and recommended fonts
provides these. No experiment runtime is needed to compile the paper.

This source archive contains manuscript inputs and the plotted CSV data.
It is not an experiment-code or raw-data supplement.
