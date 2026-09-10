# Bibliographic verification and support ledger

Only four citations appear in the candidate. Shared `paper/references.bib` was not changed. Metadata verification is distinguished from support for a technical assertion.

## 1. Abbasi-Yadkori, Pál, Szepesvári

Authors: Yasin Abbasi-Yadkori; Dávid Pál; Csaba Szepesvári.
Exact title: **Improved Algorithms for Linear Stochastic Bandits**.
Venue/year: Advances in Neural Information Processing Systems 24, 2011 (then NIPS; commonly NeurIPS).
Publisher metadata: https://proceedings.neurips.cc/paper_files/paper/2011/hash/e1d5be1c7f2f456670de3d53c7b54f4a-Abstract.html
Original paper: https://proceedings.neurips.cc/paper_files/paper/2011/file/e1d5be1c7f2f456670de3d53c7b54f4a-Paper.pdf

Verified technical support: Section 3, Theorem 1, self-normalized vector martingale inequality, and Section 4, Theorem 2, confidence ellipsoid. Candidate line 109. Supports the sentence beginning “For delta in (0,1), self-normalization ... and the Taylor envelopes give ...”. The new corrected-center algebra and envelope term are from the canonical CCE theorem/proof, not attributed to this prior paper.

## 2. Zhou, Li, Gu

Authors: Dongruo Zhou; Lihong Li; Quanquan Gu.
Exact title: **Neural Contextual Bandits with UCB-based Exploration**.
Venue/year: 37th International Conference on Machine Learning, PMLR 119, 2020, pages 11492 to 11502.
Publisher metadata: https://proceedings.mlr.press/v119/zhou20a.html
Original paper: https://proceedings.mlr.press/v119/zhou20a/zhou20a.pdf

Candidate line 41. Supports only “Learned reward models also appear in neural contextual bandits.” The original abstract and algorithms establish that context. Algorithm 2 explicitly returns the result of J gradient steps. No claim that this method assumes exact convergence or an a posteriori stationarity certificate is made. No comparative theorem statement was added, so a metadata entry is not being used as proof of such a comparison.

## 3. Riquelme, Tucker, Snoek

Authors: Carlos Riquelme; George Tucker; Jasper Snoek.
Exact title: **Deep Bayesian Bandits Showdown: An Empirical Comparison of Bayesian Deep Networks for Thompson Sampling**.
Venue/year: International Conference on Learning Representations, 2018, poster.
DBLP record: https://dblp.org/rec/conf/iclr/RiquelmeTS18.html
Original author paper: https://arxiv.org/abs/1802.09127

DBLP indexed metadata verified the complete title, authors, venue and year; the direct DBLP open encountered a cache/robots limitation. The author paper's abstract independently confirms the subject. Candidate line 41. Supports the same learned-reward-model context sentence as citation 2. No “frozen-feature” label is applied to this method. The baseline short title was expanded to the exact verified title.

## 4. Nussbaum

Author: Roger D. Nussbaum.
Exact title: **Finsler structures for the part metric and Hilbert's projective metric and applications to ordinary differential equations**.
Venue/year: Differential and Integral Equations, volume 7, 1994, pages 1649 to 1707.
Publisher issue contents: https://ade-die.com/DIE/die007.html
Author-hosted published paper: https://sites.math.rutgers.edu/~nussbaum/Pubs/Finsler.pdf

Publisher search-index content verified the title, author, journal, volume, year and pages; direct issue-page open timed out. The published paper's first page confirms them. Its issue is printed as number 6; some secondary metadata uses 5-6, so the candidate does not add that ambiguous issue field. Section 1 defines the part/Thompson metric, Theorem 1.2 and Remark 1.5 give its path-length/Finsler treatment. Those pages were inspected. Candidate line 67. Supports attribution of the **Thompson Finsler length**, not a claim that CCE invented this geometry. The AC SPD path-to-Loewner result used here is also traced to the canonical CCE lemma and proof.

## Search leads not inserted

A. C. Thompson's 1963 positive-cone metric paper was located in the canonical bibliography, but attempts to retrieve its AMS publisher page and PDF returned 403; its DOI endpoint could not be opened. No unverified new entry was inserted. Nussbaum's verified treatment supplies the geometry attribution in this candidate.

The other suggested search leads (Bandit Algorithms; deep representation/shallow exploration; adaptive policy-evaluation intervals; batched-bandit inference; Neural Thompson Sampling; Neural Contextual Bandits without Regret) were not inserted. No statement in the candidate requires those comparisons, and they would displace definitions within the three-page limit. They are not listed here as verified references. No arXiv identifier, venue, result, or self-citation was invented.
