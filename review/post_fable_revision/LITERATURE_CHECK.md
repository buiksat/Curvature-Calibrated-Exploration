# Bounded weighted/nonstationary-bandit lookup

2026-10-14. Candidate supplied for checking: Russac, Vernade, and Cappé, *Weighted Linear Bandits for Non-Stationary Environments*, suspected NeurIPS 2019. Its metadata and contents remain unverified in this check. No new BibTeX record was added.

All five requests in `literature-retrieval-log.json` failed with `Tunnel connection failed: 403 Forbidden`. The standard verified SSL context remained enabled; the proxy rejected the tunnel before an origin TLS session or response body could be inspected. No insecure transport, paid service, or substitute source was used. The candidate article locators below were not validated and must not be cited as verified publication metadata.

Attempted sources:

- Official proceedings indexes: `https://papers.nips.cc/paper/2019` and `https://proceedings.neurips.cc/paper/2019`.
- Unverified arXiv candidate locator: `https://arxiv.org/abs/1909.09146`.
- Unverified official-site candidate abstract locator: `https://papers.nips.cc/paper/2019/hash/26337353b7962f533d78c762373b3318-Abstract.html`.
- Unverified official-site candidate PDF locator: `https://papers.nips.cc/paper_files/paper/2019/file/26337353b7962f533d78c762373b3318-Paper.pdf`.

Retrieval-log SHA-256: `25e148c6d59a6be91d23b2f0997bc89510d009c9752ff89f9734dcc794a9d9d9`.

## Supported fallback and manuscript change

The already retrieved official PMLR source for Lattimore, Szepesvári, and Weisz (2020), *Learning with Good Feature Representations in Bandits and in RL with a Generative Model*, provides a directly verified weighted-Gram connection. Section 4 and Proposition 4.5 define a design-weighted Gram and weighted least-squares estimator and bound deterministic misspecification error. This is an experimental-design result, not verification of the unaccessed nonstationary-bandit paper.

- Publisher metadata: https://github.com/mlresearch/v119/blob/500846bfc432506177d62479931d030063010517/_posts/2020-11-21-lattimore20a.md
- Publisher PDF: https://github.com/mlresearch/v119/blob/500846bfc432506177d62479931d030063010517/lattimore20a/lattimore20a.pdf
- PDF SHA-256: `e7311ae0769bcd4a0e55adf550a9fe2660cb356774e43bf44afb6b95adbaf42c`.
- Supplement PDF SHA-256: `f3ac559ca4bcf2f4a3da0610e8574ad490b78113ae2453f64421c158fc7381c4` (Appendix E is the previously verified misspecified contextual-bandit connection).

Added one concise paragraph to `paper/body_related.tex`: weighted Grams already occur in experimental design; the manuscript's scaled-tanh certificate compares positive weights on fixed directions by elementary termwise PSD bounds; its reward model stays fixed while relinearization changes the weights. It makes no statistical claim for nonstationary rewards and no priority claim for weighted-Gram comparison. The paragraph cites the existing verified `lattimore2020learning` entry.

`paper/references.bib` is unchanged, including the two unused historical 2026 records. No unverified Russac citation was introduced. `git diff --check` passes. The numerical-pin owner was notified that related-work text is final. No commits or pushes were made.
