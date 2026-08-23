# ADR-0008: Dataset strategy — Fidel primary, HHD pretraining only

**Status:** Accepted, with a blocking dependency · **Date:** 2026-08-23

## Context
Three datasets were in scope. What I could establish:

| Dataset | Licence | Verified? |
|---|---|---|
| **Fidel** — ~40k handwritten + ~28k typed lines, 411 writers **[S]** | CC-BY-4.0 **[S]** | **No** — `huggingface.co` returns 403 CONNECT (org egress policy) |
| **HHD-Ethiopic** — ~80k lines, 18th–20th c., ENALA | **CC-BY-4.0 [P]** | Yes, README read directly |
| **ADOCR** (Belay et al.) | Unknown | **Not located** anywhere fetchable |

**The HHD skew is confirmed, not assumed.** Its own README ground-truth samples **[P]**:
```
ወጽራኅየኒ፡ቦአ፡ቅድሜሁ፡ውስተ፡ዕዘኒሁ
ወአድኅነከ፡ይትፌሥሑ።
```
Every word boundary is `፡` U+1361, the classical Ge'ez convention. Modern Amharic — the exam papers and shop ledgers we target — uses the space. **The domain gap is not only handwriting style; it is tokenisation.** A model trained on HHD learns that words are `፡`-delimited, which is wrong for our target documents.

## Decision
- **Fidel is the primary training and evaluation corpus** — it is modern, sentence-level, and multi-writer, matching the target domain.
- **HHD-Ethiopic is pretraining only.** It is 80k lines of real Ethiopic handwriting and that transfer is worth having, but it **never produces a headline metric** and never defines the tokenisation.
- **ADOCR is treated as unavailable.** No plan depends on it. If a copy surfaces, it is a bonus.
- Both usable datasets are **CC-BY**, so attribution is mandatory: a `DATASETS.md` with citation and licence per corpus, shipped with the repo and reproduced in any writeup.
- **No dataset is ever committed to the repo.** Fetch scripts with pinned revisions and checksums only.

**Three evaluation splits** (per the brief): IID, unseen-writer, unseen-capture-condition. The third is the one that matters for the product claim and is the one no public dataset provides — we must **capture it ourselves** (phone photos of real documents under real conditions, with consent per Phase 5). That is a data-collection task, and I am flagging it as such rather than pretending a public split covers it.

## Alternatives rejected
| Alternative | Why rejected |
|---|---|
| HHD as primary (it is 80k lines, the largest) | Classical Ge'ez, `፡`-tokenised, 18th–20th c. calligraphy. Optimising for it optimises for the wrong document. |
| Pool Fidel + HHD and report one number | Averages two different tokenisation conventions into a meaningless metric. Report per corpus (ADR-0006). |
| Synthetic data only | Cannot reproduce warp, shadow, ruled paper, or bleed-through convincingly enough to be the sole source. Valuable as *augmentation*, not as the corpus. |
| Proceed by guessing the Fidel schema from search results | Would mean writing a loader against an unverified schema. Explicitly refused — see below. |

## Consequences
- **BLOCKING:** I cannot write a Fidel loader until the schema and licence are verified. **[S]** suggests `metadata.json` / `train_labels.json` / `test_labels.json`, but I have not seen the card. Writing a loader against a guessed schema is exactly the "plausible-looking stub" this project forbids.
  - **Option A (preferred):** allowlist `huggingface.co` and `cdn-lfs.huggingface.co` on the egress proxy.
  - **Option B:** download the dataset card and one sample shard out-of-band and place them in `data/raw/fidel/`.
- Attribution obligations (CC-BY) must be discharged in docs and UI.
- The unseen-capture-condition split is **our** responsibility to collect, with consent records (Phase 5 data protection).

## Revisit when
Fidel is verified (then this ADR is updated with real counts and schema), or ADOCR becomes available.
