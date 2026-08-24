# Ethiopic inventory reference

Generated from the Unicode Character Database, UCD 17.0.0, by
`.claude/skills/ethiopic-script/scripts/regenerate_inventory.py`.
Do not hand-edit: regenerate it.

## Contents

- [Per-block counts](#per-block-counts)
- [The 8-column grid](#the-8-column-grid)
- [Complete homophone fold table](#complete-homophone-fold-table)
- [Punctuation and numerals](#punctuation-and-numerals)

## Per-block counts

| Block | Range | Slots | Assigned | Categories |
|---|---|---|---|---|
| Ethiopic | U+1200–U+137F | 384 | **358** | Lo:326, Mn:3, No:20, Po:9 |
| Ethiopic Supplement | U+1380–U+139F | 32 | **26** | Lo:16, So:10 |
| Ethiopic Extended | U+2D80–U+2DDF | 96 | **79** | Lo:79 |
| Ethiopic Extended-A | U+AB00–U+AB2F | 48 | **32** | Lo:32 |
| Ethiopic Extended-B | U+1E7E0–U+1E7FF | 32 | **28** | Lo:28 |
| **TOTAL** | | | **523** | |

## The 8-column grid

The core block U+1200–U+1357 is laid out as a strict grid: the base consonant sits
at `cp % 8 == 0`, vowel orders 1–7 occupy offsets 0–6, and offset 7 holds a
labialised or extra form. Order *n* of a base is simply `base + n`.

This regularity is what makes factored decoding viable (ADR-0005): a 37-way base
head and a 7-way vowel head cover 259 syllables with 44 output classes, so a rare
syllable is rare only as a *pair* while its components stay common.

- grid rows: **43**
- rows with a complete 7-vowel series: **37**  ← the base-consonant inventory
- rows with the 8th (labialised) slot filled: **34**

First six complete series:

| Base | 1-ä | 2-u | 3-i | 4-a | 5-e | 6-ə | 7-o |
|---|---|---|---|---|---|---|
| U+1200 | ሀ | ሁ | ሂ | ሃ | ሄ | ህ | ሆ |
| U+1208 | ለ | ሉ | ሊ | ላ | ሌ | ል | ሎ |
| U+1210 | ሐ | ሑ | ሒ | ሓ | ሔ | ሕ | ሖ |
| U+1218 | መ | ሙ | ሚ | ማ | ሜ | ም | ሞ |
| U+1220 | ሠ | ሡ | ሢ | ሣ | ሤ | ሥ | ሦ |
| U+1228 | ረ | ሩ | ሪ | ራ | ሬ | ር | ሮ |

## Complete homophone fold table

Metrics only. Never write these substitutions back to stored text.

| Family | Order | Members | Canonical |
|---|---|---|---|
| H | 1 | ሀ U+1200 · ሐ U+1210 · ኀ U+1280 | ሀ |
| H | 2 | ሁ U+1201 · ሑ U+1211 · ኁ U+1281 | ሁ |
| H | 3 | ሂ U+1202 · ሒ U+1212 · ኂ U+1282 | ሂ |
| H | 4 | ሃ U+1203 · ሓ U+1213 · ኃ U+1283 | ሃ |
| H | 5 | ሄ U+1204 · ሔ U+1214 · ኄ U+1284 | ሄ |
| H | 6 | ህ U+1205 · ሕ U+1215 · ኅ U+1285 | ህ |
| H | 7 | ሆ U+1206 · ሖ U+1216 · ኆ U+1286 | ሆ |
| S | 1 | ሠ U+1220 · ሰ U+1230 | ሠ |
| S | 2 | ሡ U+1221 · ሱ U+1231 | ሡ |
| S | 3 | ሢ U+1222 · ሲ U+1232 | ሢ |
| S | 4 | ሣ U+1223 · ሳ U+1233 | ሣ |
| S | 5 | ሤ U+1224 · ሴ U+1234 | ሤ |
| S | 6 | ሥ U+1225 · ስ U+1235 | ሥ |
| S | 7 | ሦ U+1226 · ሶ U+1236 | ሦ |
| TS | 1 | ጸ U+1338 · ፀ U+1340 | ጸ |
| TS | 2 | ጹ U+1339 · ፁ U+1341 | ጹ |
| TS | 3 | ጺ U+133A · ፂ U+1342 | ጺ |
| TS | 4 | ጻ U+133B · ፃ U+1343 | ጻ |
| TS | 5 | ጼ U+133C · ፄ U+1344 | ጼ |
| TS | 6 | ጽ U+133D · ፅ U+1345 | ጽ |
| TS | 7 | ጾ U+133E · ፆ U+1346 | ጾ |
| GLOTT | 1 | አ U+12A0 · ዐ U+12D0 | አ |
| GLOTT | 2 | ኡ U+12A1 · ዑ U+12D1 | ኡ |
| GLOTT | 3 | ኢ U+12A2 · ዒ U+12D2 | ኢ |
| GLOTT | 4 | ኣ U+12A3 · ዓ U+12D3 | ኣ |
| GLOTT | 5 | ኤ U+12A4 · ዔ U+12D4 | ኤ |
| GLOTT | 6 | እ U+12A5 · ዕ U+12D5 | እ |
| GLOTT | 7 | ኦ U+12A6 · ዖ U+12D6 | ኦ |

**35 codepoints** are folded away in total.

## Punctuation and numerals

| Codepoint | Char | Category | Name |
|---|---|---|---|
| U+1360 | ፠ | Po | SECTION MARK |
| U+1361 | ፡ | Po | WORDSPACE |
| U+1362 | ። | Po | FULL STOP |
| U+1363 | ፣ | Po | COMMA |
| U+1364 | ፤ | Po | SEMICOLON |
| U+1365 | ፥ | Po | COLON |
| U+1366 | ፦ | Po | PREFACE COLON |
| U+1367 | ፧ | Po | QUESTION MARK |
| U+1368 | ፨ | Po | PARAGRAPH SEPARATOR |
| U+1369 | ፩ | No | DIGIT ONE |
| U+136A | ፪ | No | DIGIT TWO |
| U+136B | ፫ | No | DIGIT THREE |
| U+136C | ፬ | No | DIGIT FOUR |
| U+136D | ፭ | No | DIGIT FIVE |
| U+136E | ፮ | No | DIGIT SIX |
| U+136F | ፯ | No | DIGIT SEVEN |
| U+1370 | ፰ | No | DIGIT EIGHT |
| U+1371 | ፱ | No | DIGIT NINE |
| U+1372 | ፲ | No | NUMBER TEN |
| U+1373 | ፳ | No | NUMBER TWENTY |
| U+1374 | ፴ | No | NUMBER THIRTY |
| U+1375 | ፵ | No | NUMBER FORTY |
| U+1376 | ፶ | No | NUMBER FIFTY |
| U+1377 | ፷ | No | NUMBER SIXTY |
| U+1378 | ፸ | No | NUMBER SEVENTY |
| U+1379 | ፹ | No | NUMBER EIGHTY |
| U+137A | ፺ | No | NUMBER NINETY |
| U+137B | ፻ | No | NUMBER HUNDRED |
| U+137C | ፼ | No | NUMBER TEN THOUSAND |

The `No` entries are **non-positional**: there is no place value, so `int()` will
not parse them and a dedicated Ge'ez numeral parser is required.
