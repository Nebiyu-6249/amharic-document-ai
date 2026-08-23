# ADR-0006: Ethiopic charset, homophone normalisation, and word tokenisation

**Status:** Accepted · **Date:** 2026-08-23

## Context
Three script-level decisions would otherwise be made inconsistently in different modules, silently corrupting metrics.

**1. Charset [V].** UCD 17.0.0 gives **523 assigned Ethiopic codepoints** across five blocks — Ethiopic (358), Supplement (26), Extended (79), Extended-A (32), **Extended-B (28, astral plane U+1E7E0+)**. 481 are syllables; the rest are 9 punctuation, 20 numerals, 10 tonal marks, 3 combining marks.

**2. Homophones [V].** Four families are orthographically interchangeable in modern Amharic — H (ሀ/ሐ/ኀ), S (ሠ/ሰ), TS (ጸ/ፀ), GLOTT (አ U+12A0 / ዐ U+12D0). Across all 7 vowel orders, **normalisation folds 35 codepoints**. Annotators genuinely disagree on these; each disagreement scores as a substitution against a model that read the glyph correctly.

**3. Word separation [V].** `፡` U+1361 ETHIOPIC WORDSPACE is the classical separator; modern Amharic uses U+0020. HHD-Ethiopic ground truth uses `፡` throughout **[P]**. Splitting classical text on whitespace yields one giant "word" → WER ≈ 100% for a near-perfect transcription.

## Decision
One module owns all three, and every other module calls it. No local reimplementation anywhere.

- **Charset:** support all **523** codepoints plus Latin and ASCII digits. UTF-8 clean end to end; **no BMP assumption** — Extended-B is astral, so JS `.length`, fixed-width char assumptions, and DB collation must all be checked.
- **Unicode form:** normalise to **NFC** on ingest. Store the original alongside the normalised form where provenance matters (the brief requires this for research).
- **Homophones:** fold to the lowest codepoint in each family, for **metrics only**. Never mutate stored transcriptions — the user's document says what it says.
- **Tokenisation:** split words on `[\s፡]+` (space and wordspace, collapsed).
- **Numerals:** the 20 Ge'ez numerals (U+1369–U+137C) are category `No` and **non-positional**; `int()` will not parse them. A dedicated parser is required, and it is not optional if ledgers are in scope.

**Reporting rule:** always report **raw CER and normalisation-aware CER together**, and WER **per corpus** (classical vs modern), never pooled. Reporting only the normalised number would flatter the model; reporting only raw would penalise it for annotator disagreement. Both, always.

## Alternatives rejected
| Alternative | Why rejected |
|---|---|
| Normalise homophones in stored output | Destroys the user's actual document and any orthographic research value. Metrics-only is the correct scope. |
| Report only normalisation-aware CER | Flattering and misleading — hides real recognition errors behind the fold. |
| Report only raw CER | Penalises the model for disagreements a human reader would not notice; makes the script look harder than it is. |
| Split words on whitespace only | WER ≈ 100% on classical text. Straightforwardly wrong. |
| Split on `፡` only | Fails on modern Amharic, which is the primary target. |
| Support only the main Ethiopic block | Drops 165 codepoints including all of Extended-B; guarantees silent data loss on documents that use them. |

## Consequences
- **Positive:** metrics are comparable across corpora and sessions; no module can quietly disagree about what a character or a word is.
- **Positive:** this module is the natural content of the `ethiopic-script` skill (Phase 4), so future sessions inherit it.
- **Negative:** two CER numbers to explain in every report. Accepted — the alternative is a misleading single number.
- Commits us to astral-plane-safe handling in the frontend and database, which must be tested, not assumed.

## Revisit when
Native-speaker review disputes an equivalence class, or a target corpus uses a convention not covered here.
