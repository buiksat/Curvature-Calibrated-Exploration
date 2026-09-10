# Current-candidate checksum changes

The existing `submissions/code_mit_2026/SHA256SUMS` entries for historical files remain
unchanged. Only the current-candidate entries below change, and the final manifest adds the
new PDF plus this review directory's own manifest.

| Path | Baseline SHA-256 | Candidate SHA-256 | Reason |
| --- | --- | --- | --- |
| `README.md` | `53759042a40dad3f2b4f57e2e44b94ef6cbe827f4419df5ac1d6f213c2ec1d45` | `c1e231f6f3b3eead48cee098bba0c5e1047a4cc45686ae5978c4f57d520540ab` | Current-status notice and post-review pointer |
| `author_review/README.md` | `d5d037b742906396e41876ca0db94269a8dff9bb95aa7af4441f7390df340cd1` | `9cc4e511a9594a874639c16f6f96d5161cb0d68dec11014ba8bdf62b5dd41c61` | Dated candidate pointer |
| `main.tex` | `c5aaafdcb5049e5b91b1d92582cf149f50dc7a271d5a3d90175c6a62467cf1cc` | `d0e11b291743e576dd69d40da0c027fdb556a19320e74a479d9585801cf6ffae` | Cleared packet-01 manuscript blocks |
| `main.pdf` | not present | `3270827506f2775f99e93c860ee1623780998d4fbe0da6a52a16aac559b8e336` | Built four-page author-review candidate |

The parent manifest does not hash itself. The new post-review manifest hashes every file in
the review directory except itself; the parent manifest hashes that nested manifest.

## AUTH01 and commit-authorization update

| Path | Pre-AUTH01 SHA-256 | AUTH01 candidate SHA-256 | Reason |
| --- | --- | --- | --- |
| `README.md` | `c1e231f6f3b3eead48cee098bba0c5e1047a4cc45686ae5978c4f57d520540ab` | `abc8b08b0fa05c87f3069370c091e9b22f8dcbda944bb65f6bfac75565fa5ae1` | Record AUTH01 resolution and commit authorization |
| `author_review/README.md` | `9cc4e511a9594a874639c16f6f96d5161cb0d68dec11014ba8bdf62b5dd41c61` | `2611bb40f8d0f1cc804821c9c6ddc670a9b2147138159bf622234b48dc2e7985` | Update the current-candidate pointer and open approvals |
| `main.tex` | `d0e11b291743e576dd69d40da0c027fdb556a19320e74a479d9585801cf6ffae` | `582fc40fd849d16e6d7ab890e8c41ab83db524064a7836827b17d2c0bf2bc673` | Add Bahram Behzadian, Meta, and remove the obsolete AUTH01 placeholder |
| `main.pdf` | `3270827506f2775f99e93c860ee1623780998d4fbe0da6a52a16aac559b8e336` | `fe6799215f9ad7152bfb347c8e64f92509e5daf06eda7064930697c6aa8e0e66` | Rebuild after AUTH01 |
| `postreview_20260910/README.md` | `a0e50cd0cb98a24ad1f7d560d332cc8d668f551bdc690d2c2d9daa0236e82f4c` | `1b8fa5e5f1cc19e3181ca51747c29e8fc680317174d93aba86bb0e0ad0f02063` | Record AUTH01 and commit authorization |
| `postreview_20260910/APPROVAL_ADDENDUM.md` | `b27f435b49b3f97a72621149957691140f099b60eb2a8ea6ed9c3869f46699d5` | `fd4fda3d6e2b417ca04cf2d929a28d6945524c50713e38b9b973a2c5ec5a54a9` | Resolve AUTH01 and record the bounded release authorization |
| `postreview_20260910/CHANGELOG.md` | `27b5edbe7b332aedebe48741b98e9d56d549684126ed2238b39a6c46816c584b` | `6c3666628456c365ff475f6a191a497139ca6374925bf49a1e4d4f21c9563c3b` | Add AUTH01 and refresh candidate line numbers |
| `postreview_20260910/CLAIM_TO_SOURCE.md` | `db77783e632c8c1aa45ad11be6c08d93ceb4c93ddc1ae85d7e69bc0f8fb812ab` | `17b610f73f108274d6b4145189459648e3613c9c7dfa57ca2bbc72f7dd6b5a47` | Record candidate blob IDs before the authorized commit |
| `postreview_20260910/BUILD_VALIDATION.md` | `aa5bec5f9bd939122e4e75778218ded6939f69e8923738bd365a4d1f9019407e` | `0e7ab988eba7d571b6e78ce381c4ab433bc7ecfde5e3122fe66524c5e1d3c14f` | Add the AUTH01 rebuild and visual check |
| `postreview_20260910/PROVENANCE.md` | `3c701c53580f70d84af2722c94f27bde6271dfb3a9f6bb09074ca9465f5c437e` | `2b7e3876ba615a7e8ee039352ced99b341db1a925f42fdc408ba3ed56327c64c` | Record commit authorization without extending release scope |
| `postreview_20260910/VALIDATION.md` | `e8d823a0a8e6bc2e1b62fa7a814cec425dea74378f5be976d3674a06fbb74344` | `f230bfea1a08d1ee84d6c3b27a838f233eef0f2eefb6c3f0de12ebc354a126bb` | Record AUTH01 and the refreshed render inspection |
| `postreview_20260910/main.after.numbered.txt` | `9675d853a46dc88fd673ae17b133a0c9c2bf1991801c0019543affb8e13c1405` | `50a3e5c13242e4def566b261aed80dfb0e95baba4ca160c13cd554cbf43a4292` | Refresh the numbered candidate source |
| `postreview_20260910/main.patch` | `517f35712680d541c685251871241a4bab9568f16b663d0173d49c81c33d68f3` | `21b1582deb1bc2517f7e2359fd933d0665e6247703d627d7a2dee3b9136b59b5` | Refresh the baseline-to-candidate patch |
| `postreview_20260910/renders/page-1.png` | `e0c2a4f1422d8c839da662a2f73b9972c36d10fe50b84e2bbf46a82d2afb546a` | `56bd26f9c071f1ccc52e9737e34c2965ae10c9432a1657815fe2999866a5fcae` | Re-render author and affiliation |
| `postreview_20260910/renders/page-2.png` | `a864b98d9c1b72929881679846f3d0135b25bbfe1adea6ab3b756ac7b8b3f1ca` | same | Re-rendered; bytes unchanged |
| `postreview_20260910/renders/page-3.png` | `58f2331c3374ac62e81890b40c03b2cea244a4a7ee33ebb56b60532a0a92c7af` | same | Re-rendered; bytes unchanged |
| `postreview_20260910/renders/page-4.png` | `99c273ae0605665020a4d1380305069659b259e513dcf27fc42cbb87fc2d6220` | same | Re-rendered; bytes unchanged |
| `postreview_20260910/build/auth01-main.log` | not present | `ac0bb5a84d044429cf23e5b1b6465121c837ca7ff1831a74f54b93ae526b9b4b` | New AUTH01 build log |
| `postreview_20260910/build/auth01-main.txt` | not present | `e4760cd2cf3c38bf9773242085620e424c57ede421f46001ca80664e5bdf1b18` | New Ghostscript text extraction |

`HASH_CHANGES.md` cannot embed its own final digest without creating a cycle. Its final
digest is recorded in the post-review manifest, whose digest is recorded by the parent
manifest. The same rule applies to the manifest files themselves.
