# Vendored LaTeX packages

These are verbatim, unmodified copies of five third-party LaTeX packages the
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

The Debian 13 build host also lacks `algorithm.sty` and `algorithmic.sty` in
its protected distribution. The `algorithms` bundle is therefore carried by
the same project-local, hash-pinned mechanism. Its `float`, `ifthen`, and
`keyval` dependencies remain external protected distribution inputs; no trust
check is relaxed.

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
| `algorithms` | 2 runtime files + 2 corresponding source files | LGPL 2 or later (upstream wording) | `LICENSE-lgpl-2-1` |

The original three licence texts are the copies shipped by the original host's
TeX Live under `/usr/share/texlive/licenses/`. The added LGPL 2.1 text is the
upstream `COPYING` from the authenticated Debian documentation package. All
four licence texts and the corresponding `algorithms.dtx` and `algorithms.ins`
sources travel in `source.zip` alongside the code they cover.

No font is vendored. The 50 code/source files have extensions `.sty`, `.tex`,
`.def`, `.cfg`, `.dtx` or `.ins`, are redistributable under the licences above,
and are byte-identical to their documented upstream origins.

## Algorithms bundle provenance and source verification

The two runtime files are version `2009/08/24 v0.1`, extracted unchanged from
Debian `texlive-science_2024.20250309-2_all.deb`, SHA-256
`452596eb7ab5ee08ff1664a8586e243e561ff675abb88d2f764b38113c688adc`.
The license text is the decompressed `latex/algorithms/COPYING.gz` from
`texlive-science-doc_2024.20250309-2_all.deb`, SHA-256
`d84c7fd37c8d27381664fef193e16708083aa2a223f30e3037f2abb60d2ccbe6`.
Both archives were checked against the retained Debian trixie `Packages`
index, SHA-256
`4f2c68d67001d595fbd343f6dbad44468953a51c4d9dec3a4803249f6e295940`.
Its digest was checked against `InRelease` after signature verification with
`sqv` and the installed Debian archive keyring, using the default cryptographic
policy. Downloads used ordinary verified HTTPS.

Debian's runtime and documentation packages omit the `.dtx` and `.ins` files.
These come unchanged from the maintainer's
[upstream repository](https://github.com/rbrito/algorithms/tree/127edbf0426e5d75ccd8b84c38952d80db2e7787),
commit `127edbf0426e5d75ccd8b84c38952d80db2e7787`. In a disposable directory,
copy `algorithms.dtx` and `algorithms.ins`, then run:

```sh
tex -8bit -interaction=nonstopmode -halt-on-error algorithms.ins
```

Both generated style files reproduce the authenticated Debian bytes exactly.
The `-8bit` option preserves the original Latin-1 copyright comment; omitting
it makes modern TeX escape that one non-ASCII character. No source or comment
was rewritten. The pinned digests cover the runtime, corresponding source,
generation script, and LGPL text; the regeneration test checks their agreement.

## Modifying these files

Do not. They are third-party code held at a pinned digest, and the number audit
does not read them: their role in the compiled-source closure is
`vendored-package`, which is exempt from the per-literal audit for the same
reason the venue template is — the numbers in them are code, not claims about
this study. Both the layout gate and packaging verify them against
`package.VENDORED_PACKAGE_DIGESTS` instead. Upgrading a package means replacing
the files and regenerating the digests, deliberately, in one reviewable change.
