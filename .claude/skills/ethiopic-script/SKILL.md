---
name: ethiopic-script
description: >
  Authoritative rules for handling Ethiopic/Amharic/Ge'ez text in this project - the
  supported codepoint inventory, the four homophone equivalence classes, word
  tokenisation across the space/wordspace split, Ge'ez numerals, and the normalisation
  that metrics depend on. Use this skill whenever you touch Amharic, Ethiopic, Ge'ez,
  Tigrinya or "fidel" text, compute or compare CER/WER, write a tokeniser, choose a
  character vocabulary for a model, normalise or compare transcriptions, or handle
  Ethiopic in a database, frontend or regex - even if the request never says "Ethiopic"
  and just says "the text" or "the transcription". Getting these rules wrong does not
  crash anything; it silently corrupts every metric in the project, so check here first.
---

# Ethiopic script handling

Ethiopic is an abugida: a base consonant carries a vowel marker as a small stroke or
loop, so visually adjacent characters differ by a few pixels. That single fact drives
most of this project's difficulty and all of the rules below.

**Never reimplement any of this.** `src/adai/ethiopic/` is the single owner. If two
modules disagree about what a character or a word is, every metric silently becomes
incomparable — and nothing fails loudly to tell you.

```python
from adai.ethiopic import (
    ethiopic_codepoints, is_ethiopic,          # inventory
    to_nfc, fold_homophones, normalise_for_metrics,  # normalisation
    split_words,                                # tokenisation
)
```

## The four rules that matter most

### 1. Report raw CER and normalisation-aware CER together, always

Four sets of Ethiopic characters are orthographically interchangeable in modern Amharic.
Two careful annotators transcribing the same image will disagree on them, and every
disagreement is scored as a substitution against a model that read the glyph *correctly*.

So raw CER overstates error. But normalisation-aware CER hides real recognition
mistakes behind the fold. **Neither number alone is honest**, which is why
`EvalReport` carries both fields and the harness prints both columns.

```python
character_error_rate("ሰላም", "ሠላም")        # 0.25 - penalised
normalisation_aware_cer("ሰላም", "ሠላም")     # 0.0  - equivalent
```

### 2. Split words on space **and** U+1361, never one alone

"Word" has no single definition in this script:

| Convention | Separator | Where you meet it |
|---|---|---|
| Classical Ge'ez | `፡` U+1361 ETHIOPIC WORDSPACE | HHD-Ethiopic ground truth, liturgical text |
| Modern Amharic | U+0020 space | Fidel, exam papers, ledgers, most real documents |
| Real pages | both, sometimes in one line | anything scanned from the wild |

Splitting classical text on whitespace alone yields **one token per line**, so a
near-perfect transcription scores WER ≈ 1.0. `split_words` splits on `[\s፡]+`.

Report WER **per corpus**. Averaging a `፡`-delimited corpus with a space-delimited one
produces a number that describes neither.

### 3. Fold homophones for metrics only — never mutate stored text

The user's document says what it says. Orthographic choice is research signal and, in
some contexts, meaning. `fold_homophones` exists for comparison; nothing should write
its output back to the database.

### 4. The script is astral — do not assume the BMP

Ethiopic Extended-B lives at U+1E7E0–U+1E7FF, above U+FFFF. Python strings are fine.
JavaScript `.length`, fixed-width column assumptions, and some database collations are
not. Test with a character from that block, not just `ሀ`.

## The homophone equivalence classes

Four families, folded across all seven vowel orders — **35 codepoints** collapse.
The canonical target is the lowest codepoint in the family.

| Family | Sound | Order-1 members | Canonical |
|---|---|---|---|
| H | /h/ | ሀ U+1200 · ሐ U+1210 · ኀ U+1280 | ሀ |
| S | /s/ | ሠ U+1220 · ሰ U+1230 | ሠ |
| TS | /tsʼ/ | ጸ U+1338 · ፀ U+1340 | ጸ |
| GLOTT | /ʔ/ | አ U+12A0 · ዐ U+12D0 | አ |

The families are declared by their order-1 base only, because the block is a strict
8-column grid: order *n* is `base + n`. That regularity is why the table is four rows
rather than thirty-five, and it is the same property that makes factored decoding work
(ADR-0005).

## The supported inventory

**523 assigned codepoints** across five blocks, computed from UCD 17.0.0 — not copied
from a web page.

| Block | Range | Assigned |
|---|---|---|
| Ethiopic | U+1200–U+137F | 358 |
| Ethiopic Supplement | U+1380–U+139F | 26 |
| Ethiopic Extended | U+2D80–U+2DDF | 79 |
| Ethiopic Extended-A | U+AB00–U+AB2F | 32 |
| Ethiopic Extended-B | U+1E7E0–U+1E7FF | 28 (**astral**) |

Of these, 481 are `ETHIOPIC SYLLABLE`; the rest are 9 punctuation marks, 20 numerals,
10 tonal marks and 3 combining marks.

Re-derive any figure here with:

```bash
python docs/research/verify_ethiopic_inventory.py
```

It exits non-zero if a number quoted in `docs/RESEARCH.md` has gone stale.

## Punctuation and numerals

```
፠ U+1360 SECTION MARK      ፣ U+1363 COMMA       ፦ U+1366 PREFACE COLON
፡ U+1361 WORDSPACE         ፤ U+1364 SEMICOLON   ፧ U+1367 QUESTION MARK
። U+1362 FULL STOP         ፥ U+1365 COLON       ፨ U+1368 PARAGRAPH SEPARATOR
```

**Ge'ez numerals (U+1369–U+137C) are non-positional.** `int("፩")` raises. There is no
place-value: the system composes from units, tens, hundred and ten-thousand. Anything
parsing a ledger needs a dedicated numeral parser — and one does not exist yet in this
repo, so write it rather than assuming `int()` will do.

## Common mistakes this skill exists to prevent

| Mistake | What actually happens |
|---|---|
| Whitespace-only tokenisation | WER ≈ 1.0 on classical text; the model looks broken |
| Reporting only normalisation-aware CER | Real errors hidden; results look better than they are |
| Reporting only raw CER | Annotator disagreement counted as model error |
| Folding homophones before storage | The user's document is silently rewritten |
| Assuming ~300 flat syllable classes | Misses the base×vowel structure the contribution depends on |
| `int()` on a Ge'ez numeral | ValueError, or worse, a silent fallback to 0 |
| Testing only with U+1200-range characters | Astral handling bugs ship undetected |

## Further reading

- `references/inventory.md` — full per-block breakdown, the 8-column grid, and the
  complete fold table. Read it when choosing a model vocabulary or debugging a
  normalisation mismatch.
- `docs/adr/0006-ethiopic-normalisation-and-tokenisation.md` — the decision record,
  including the alternatives that were rejected.
- `docs/RESEARCH.md` §5 — how the figures were computed and why the UCD was used
  instead of unicode.org.
