# ADR-0005: CRNN+CTC baseline plus factored (base × vowel) decoding as the contribution

**Status:** Accepted · **Date:** 2026-08-23 · **Driver:** Staff ML engineer

## Context
This is the project's actual research contribution, so the justification must be structural, not hopeful.

**Measured from UCD 17.0.0 [V]** (RESEARCH.md §5.2): the Ethiopic core block is a strict 8-column grid — base consonant at `cp % 8 == 0`, vowel orders 1–7 at offsets 0–6, an 8th labialised slot. **37 rows carry a complete 7-vowel series; 34 have a labialised form; 86 labialised syllables script-wide.** The factorisation is *perfectly regular* — there are no exceptions in the grid.

A conventional recogniser treats each of ~259 syllables as an atomic class. Two consequences:
1. Classes that differ by a **few pixels** of diacritic must be separated by a flat softmax with no shared structure — the model gets no architectural hint that ሀ/ሁ/ሂ share a base.
2. A syllable that is rare in the corpus is a **low-support class**, even though its base consonant and its vowel order are individually common.

Factored decoding attacks both: predict base (37) and vowel order (7) from **separate heads**, plus a labialisation head. **44 output classes cover 259 syllables.** A rare syllable is rare only as a *pair*; its components are well-supported. This is a direct architectural attack on the reported failure mode, which is why it is the contribution rather than a tweak.

**Constraint discovered [V]:** the HHD-Ethiopic reference implementation **cannot be installed** — `requirements.txt` has a literal syntax error (`editdistance=0.60`), and after fixing it, `tensorflow==2.10.0` has no cp311 wheel (max cp310). "Reproduce the published numbers by running the authors' code" is therefore not achievable.

## Decision
Two tracks behind one interface, with a shared ablation harness:

- **Track A (baseline):** CRNN + CTC, flat syllable vocabulary. Purpose is to **prove the harness is correct** before claiming anything about the contribution. Reproduce published numbers as closely as a reimplementation allows.
- **Track B (contribution):** shared CNN+RNN trunk, **three heads** — base (37-way), vowel order (7-way), labialisation — each CTC-decoded, recombined into codepoints via the grid mapping from §5.2.

Both trained and evaluated on identical data and identical metrics. The ablation harness is built **before** Track B, so the comparison cannot be tuned after the fact.

Because the authors' code will not run, we **reimplement in PyTorch** and state explicitly in any writeup that reproduction gaps are confounded by reimplementation. That caveat is not optional.

## Alternatives rejected
| Alternative | Why rejected |
|---|---|
| Flat ~300-class CTC only | This is Track A. It is the baseline to beat, not the answer. |
| TrOCR | Encoder-decoder, needs full retraining for Ethiopic, heavy. Kept as a fallback if CRNN plateaus. |
| PARSeq | Apache-2.0 **[P]**, strong for scene text; permuted-AR training is a good fit for a syllabary. **Kept as a live Track C candidate** if the CRNN trunk underperforms — not rejected, deferred. |
| Character-level Latin transliteration then map back | Lossy and ambiguous — the homophone families (§5.3) collapse under transliteration and cannot be recovered. |
| Predicting a combining diacritic sequence | Ethiopic syllables are precomposed codepoints, not base+combining marks. Only 3 `Mn` marks exist in the block **[V]**. This would invent an encoding the script does not use. |

## Consequences
- **Positive:** 44 classes instead of 259; rare syllables become compositions of common parts; the architecture encodes the abugida structure rather than hoping the model infers it.
- **Positive:** the base/vowel split gives **diagnostic output** — we can report whether errors are base confusions or vowel-order confusions. That is exactly the measurement the project needs.
- **Negative:** three heads can disagree, producing an invalid (base, vowel) pair. Recombination must handle unmapped pairs explicitly — never silently emit a wrong codepoint.
- **Negative:** CTC alignment across three heads is more delicate than one; the heads must stay time-synchronised.
- **Risk:** the contribution may simply not beat the baseline. The ablation harness is built to be capable of reporting that honestly.

## Revisit when
The ablation shows no significant gain on the unseen-writer split, or head disagreement proves unmanageable.
