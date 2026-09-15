# Official TMLR style files (unmodified)

Source: <https://github.com/JmlrOrg/tmlr-style-file>, the repository the TMLR
author guidelines link to as the mandatory LaTeX stylefile and template.

- Upstream revision: `7bf90efe3a0debbba703c05c43f3ff7e4d4a2992` (`main`, committed
  2023-06-30, message "Removed duplicated line in tmlr.sty"); this was `main`'s
  head when the files were downloaded on 2026-09-15.
- Downloaded from `https://github.com/JmlrOrg/tmlr-style-file/archive/refs/heads/main.zip`
  on 2026-09-15.

SHA-256 of the files as shipped here, byte-identical to upstream:

```
816214ff5919aa457b6b443bee52b15d9561421417b7f8a50cc84651519f0002  tmlr.sty
306fd454cf40771bee01293eeb98d2c1cd5f4e11ed0cd7296b335f354fc45206  tmlr.bst
3d2922548e0e5f1a6c5676eda6ebb6dc20d7d305b4d8c2be5f1c833fb1084e6d  fancyhdr.sty
c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4  LICENSE
```

Nothing in this directory is edited.  TMLR states that "Any changes to the
stylefile or template that alters the formatting, font, or layout of the
manuscript may result in rejection without review", so the submission build
places this directory on `TEXINPUTS`/`BSTINPUTS` rather than patching anything.

Licensing: `LICENSE` is the Apache License 2.0 that covers the upstream
repository.  The bundled `fancyhdr.sty` carries its own LaTeX Project Public
License v1.3 header (Copyright (C) 1994-2021 Pieter van Oostrum) and is
redistributed under that license.  `fancyhdr.sty` is shipped because
`tmlr.sty` does `\RequirePackage{fancyhdr}` and the upstream template bundles a
specific copy; shipping it keeps the submission build independent of the
reviewer's TeX Live version.
