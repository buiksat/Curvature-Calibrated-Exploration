# Vendored LaTeX packages

These are verbatim, unmodified copies of four third-party LaTeX packages the
submission compiles against. They are here so that the build depends on no
bytes outside the project that a user account could rewrite.

## Why they are vendored rather than taken from the system

`submissions/tmlr_2026/package.py` accepts an external compiled input only from
a TeX distribution tree that is write-protected at every path component, not a
symlink anywhere, already canonical, and outside the project. A user tree such
as `TEXMFHOME` is not acceptable: anything found there is bytes the account
running the build can change, and the submitted PDF would then depend on files
that appear in no audited record.

The build host's TeX Live 2020 (el9 packaging) does not ship `pgfplots`,
`microtype`, `cleveref` or `mathtools`. Installing them into a user tree is how
they got onto the machine, and that is precisely what the rule rejects. An
unprivileged account cannot install into a root-owned tree, so the remaining
option is to carry the files with the submission.

The build stages these files flat beside `main.tex` and compiles with
`TEXMFHOME`, `TEXMFVAR` and `TEXMFCONFIG` pointed away from the user's trees, so
the staged copies are what pdfTeX reads and no user tree can shadow the system
distribution. Every staged copy is bound to a pinned SHA-256 in
`package.VENDORED_PACKAGE_DIGESTS`; a changed byte fails the build.

They are also a reproducibility gain. A reviewer who unpacks `source.zip` and
runs `latexmk -pdf main.tex` compiles against these exact versions, not against
whatever their own TeX Live happens to carry.

## What is here, and under what licence

| Package | Files | Licence | Text |
|---|---:|---|---|
| `pgfplots` | 37 | GNU GPL v3 or later | `LICENSE-gpl-3-0` |
| `microtype` | 6 | LPPL 1.3c or later | `LICENSE-lppl-1-3c` |
| `mathtools` (with `mhsetup`) | 2 | LPPL 1.3c or later | `LICENSE-lppl-1-3c` |
| `cleveref` | 1 | LPPL 1.2 or later | `LICENSE-lppl-1-2` |

Every licence text is the copy shipped by this host's TeX Live under
`/usr/share/texlive/licenses/`. The three licence files travel in `source.zip`
alongside the code they cover.

No font is vendored. Everything here is `.sty`, `.tex`, `.def` or `.cfg` source,
redistributable under the licences above, and byte-identical to the upstream
release it came from.

## Modifying these files

Do not. They are third-party code held at a pinned digest, and the number audit
does not read them: their role in the compiled-source closure is
`vendored-package`, which is exempt from the per-literal audit for the same
reason the venue template is — the numbers in them are code, not claims about
this study. Both the layout gate and packaging verify them against
`package.VENDORED_PACKAGE_DIGESTS` instead. Upgrading a package means replacing
the files and regenerating the digests, deliberately, in one reviewable change.
