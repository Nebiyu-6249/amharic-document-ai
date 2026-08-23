# Phase 0 — Research

**Status:** complete. No code has been scaffolded yet.
**Date:** 2026-08-23
**Author role:** Staff ML engineer (document AI / OCR), with the application-security role performing the licence and supply-chain audit.

---

## 0. How to read this document, and what "verified" means here

Every claim below is tagged:

| Tag | Meaning |
|---|---|
| **[V]** | **Verified by execution or by fetching the primary artefact** in this session. A resolver was run, a file was fetched and read, or the Unicode database was queried locally. Reproduce with the command given. |
| **[P]** | **Primary source read**, but not executed — e.g. a `pyproject.toml` or `LICENSE` fetched verbatim from `raw.githubusercontent.com`. |
| **[S]** | **Secondary source only** — a web-search summary. Not independently confirmed. Treat as a lead, not a fact. |
| **[BLOCKED]** | Could not be verified because the source is unreachable from this environment. Stated as unknown, not guessed. |

### 0.1 Research environment constraints — read this first

This session runs behind a policy-enforcing egress proxy with a **narrow allowlist**. I probed it directly:

```
github.com                 reachable        pypi.org                  reachable
raw.githubusercontent.com  reachable        files.pythonhosted.org    reachable
gitlab.com                 reachable        api.github.com            scoped to this repo only (403 otherwise)

huggingface.co             403 CONNECT      arxiv.org                 403 CONNECT
zenodo.org                 blocked          openreview.net            403 CONNECT
unicode.org                blocked          link.springer.com         blocked
researchsquare.com         403 CONNECT      paddlepaddle.github.io    403 CONNECT
inria.hal.science          403 CONNECT      en.wikipedia.org          blocked
```

**[V]** — `curl -sS "$HTTPS_PROXY/__agentproxy/status"` recorded `connect_rejected … "gateway answered 403 to CONNECT (policy denial)" host: huggingface.co:443`.

This has three hard consequences, and I am flagging them rather than papering over them:

1. **I could not read either dataset card.** Both `upanzi/fidel-dataset` and `OCR-Ethiopic/HHD-Ethiopic` live on Hugging Face. Everything about the Fidel label schema and licence below is **[S]**. This is the single largest gap in Phase 0 and it must be closed before any training code is written. See §8.
2. **I could not read any paper PDF.** arXiv, Springer, OpenReview, HAL and ResearchGate are all blocked. Published CER/WER numbers below are **[S]**.
3. **I compensated where a better primary source existed.** The Unicode data in §5 is *not* from unicode.org — it is computed locally from the Unicode Character Database via `unicodedata2` (UCD **17.0.0**) installed from PyPI. That is a stronger source than a web page, and it is reproducible.

The pattern throughout: where GitHub or PyPI carries the primary artefact, I fetched and ran it. Where only a blocked host carries it, I said so.

---

## 1. Component comparison

| Component | Role in our pipeline | Ethiopic support | Maintained? | Verdict |
|---|---|---|---|---|
| **kraken** 7.1 | Line/baseline segmentation, trainable layout + reading order, recognition | Script-agnostic; built for non-Latin & historical | **Yes** — released 2026-08-04, ~3 weeks old **[V]** | **ADOPT** for line segmentation (ADR-0004) |
| **surya** (`surya-ocr` 0.22.1) | Detection, layout, reading order, OCR | **Yes — `am` Amharic, 74.6% pass rate** in its own 93-language table **[P]** | Yes — released 2026-07-20 **[V]** | **ADOPT as VLM baseline only**, quarantined. Licence + CVE issues (ADR-0007, ADR-0010) |
| **PP-DocLayoutV3** / PaddleOCR 3.7.0 | Layout analysis on non-planar pages, multi-point boxes + reading order in one pass | Layout is script-agnostic; PaddleOCR *recognition* does not list Amharic **[P]** | Yes — released 2026-06-11 **[V]** | **ADOPT layout model only**, isolated container (ADR-0003) |
| **UVDoc** (`tanguymagne/UVDoc`) | Dewarping (neural grid-based unwarping) | N/A (geometry) | Research repo, SIGGRAPH Asia 2023 | **ADOPT** — MIT licence **[P]** (ADR-0002) |
| **docuwarp** 1.0.2 | ONNX UVDoc inference wrapper | N/A | **No** — last release 2024-07-15 **[V]** | **REJECT** — no licence at all (ADR-0002) |
| **DocTr** | Dewarping + illumination correction | N/A | Research repo | Reject as dependency; keep illumination idea (ADR-0002) |
| **ARU-Net** | Baseline detection (U-Net) | N/A | Stale; TF1-era | Reject — superseded by kraken's `blla` **[S]** |
| **eScriptorium** | Annotation UI over kraken | Same as kraken | Active | **Adopt for annotation only**, not runtime (ADR-0004) |
| **PARSeq** (`strhub` 1.2.0) | Permuted-autoregressive STR | Script-agnostic, needs retraining | Apache-2.0 **[P]** | Candidate for recognition track (ADR-0005) |
| **TrOCR** (via `transformers`) | Encoder-decoder OCR | Needs full retraining for Ethiopic | Active | Fallback; heavy (ADR-0005) |
| **CRNN + CTC** | Recognition baseline | Reference architecture | N/A | **ADOPT as baseline track** (ADR-0005) |

### 1.1 The surya finding that matters

The project brief assumed surya might not cover Amharic. **It does.** From `static/docs/multilingual.md` at `master` **[P]**:

```
| `am` | Amharic           | 74.6% |
```

That is a 74.6% pass rate on their internal multilingual benchmark (93 language rows in the table). This is *not* a CER and is not comparable to a CER — it is surya's own pass/fail metric, undefined for our purposes. But it changes the project's framing: **an off-the-shelf system already claims non-trivial Amharic capability.** That is precisely why the brief's "VLM baseline runner" (Phase 6) is not optional — it is the control that tells us whether this project is worth building. See ADR-0010.

Note also the repository has **moved to `datalab-to/surya`** **[V]** — `VikParuchuri/surya` redirects. Pin the new path.

---

## 2. Licence audit

| Artefact | Licence | Source | Commercial use | Risk |
|---|---|---|---|---|
| **surya — code** | Apache-2.0 | `LICENSE` @ master **[P]** | Yes | Low |
| **surya — model weights** | **Modified AI Pubs Open RAIL-M** | README L67-69 **[P]** | **Restricted** | **HIGH** |
| **PaddleOCR** | Apache-2.0 | README **[P]** | Yes | Low |
| **paddlepaddle** | Apache-2.0 | PyPI metadata **[V]** | Yes | Low (licence) / High (weight, §3.2) |
| **kraken** | **Apache-2.0** | `pyproject.toml` L10 **[P]** | Yes | **Low — cleanest option** |
| **UVDoc** | **MIT**, © 2023 Tanguy MAGNE | `LICENSE` **[P]** | Yes | Low |
| **docuwarp** | **NONE FOUND** | 404 on LICENSE/.md/.txt/COPYING **[V]** | **NO** | **BLOCKER** |
| **PARSeq** (`strhub`) | Apache-2.0 | `LICENSE` **[P]** | Yes | Low |
| **HHD-Ethiopic** | **CC-BY-4.0** | README "License" section **[P]** | Yes, with attribution | Low |
| **Fidel** | CC-BY-4.0 | **[S] — unverified, HF blocked** | Presumed yes | **Must confirm** |

### 2.1 surya weights — the exact wording

Quoted verbatim from the README, because a paraphrase would be dangerous here **[P]**:

> The Surya code is licensed under Apache 2.0. The model weights use a modified AI Pubs Open Rail-M license (free for research, personal use, and startups under $5M funding/revenue). For broader commercial licensing of the model weights, visit our pricing page.

**Reading:** the *code* is genuinely Apache-2.0 and unencumbered. The *weights* are not open source — OpenRAIL-M is a responsible-AI licence with use restrictions, and this variant adds a **$5M funding/revenue ceiling**. For a university research project this is fine. For anything that later commercialises, it is a tripwire.

**Decision:** surya is confined to the evaluation harness as a baseline (ADR-0010). It never becomes a load-bearing production dependency, so the threshold can never silently become a problem.

### 2.2 docuwarp — the blocker

The brief named `pstwh/docuwarp` as a dewarping candidate. It must be rejected, and the reason is legal, not technical:

- **[V]** `LICENSE`, `LICENSE.md`, `LICENSE.txt`, `COPYING` all return **HTTP 404** on `main`.
- **[P]** `setup.py` declares no `license=` field.

No licence grant means **all rights reserved by default**. We have no right to redistribute it, and shipping it in a Docker image is redistribution. This is not a technicality to wave through — it is exactly the kind of thing that surfaces in an institutional review.

It is also technically unfit independently of the licence (§3.3). UVDoc, the upstream model it wraps, is **MIT** — so we take the model and drop the wrapper.

---

## 3. Dependency compatibility matrix

**All rows [V]** — obtained from the PyPI JSON API and confirmed with real resolutions via `uv pip compile --python-version 3.11`. Nothing here is guessed.

### 3.1 Package facts

| Package | Latest | requires-python | Released | Note |
|---|---|---|---|---|
| `surya-ocr` | 0.22.1 | `>=3.10,<4` | 2026-07-20 | **caps `pillow<11`** |
| `kraken` | 7.1 | `>=3.10,<3.14` | 2026-08-04 | `torch>=2.9.0,<=2.13` |
| `paddleocr` | 3.7.0 | `>=3.8` | 2026-06-11 | pulls `paddlex` |
| `paddlepaddle` | 3.3.1 | *(none declared)* | 2026-03-26 | separate DL framework |
| `docuwarp` | 1.0.2 | `>=3.5,<4` | **2024-07-15** | **2 years stale** |
| `torch` | 2.13.0 | `>=3.10` | 2026-07-08 | |
| `onnxruntime` | 1.29.0 | **`>=3.11`** | 2026-08-17 | |
| `transformers` | 5.15.1 | `>=3.10.0` | 2026-08-19 | |
| `pillow` | 12.3.0 | `>=3.10` | 2026-07-01 | |
| `fastapi` | 0.141.1 | `>=3.10` | 2026-07-29 | |

**Target: Python 3.11.** It is the intersection of every constraint (`onnxruntime>=3.11`, `kraken<3.14`, everything else `>=3.10`) and matches the local interpreter (3.11.15).

### 3.2 Resolutions actually executed

| # | Requirement set | Result | Consequence |
|---|---|---|---|
| A | Core app stack (FastAPI, SQLAlchemy, alembic, psycopg, arq, redis, argon2, pillow) | **OK**, 103 pkgs, `pillow==12.3.0` | Clean |
| B | Core stack **+ surya-ocr** | **OK**, 228 pkgs — but **`pillow` downgraded 12.3.0 → 10.4.0** | **Unacceptable, see §3.4** |
| D | `paddleocr + paddlepaddle` | OK, 189 pkgs | Works standalone |
| E | `paddleocr + paddlepaddle + torch` | **OK**, 256 pkgs | Both frameworks *can* co-install |
| F | `kraken` | OK, 284 pkgs | Clean |
| G | `kraken + surya-ocr` | OK, 392 pkgs | Resolvable but bloated |

**The decisive constraint, proven by resolver error:**

```
× No solution found when resolving dependencies:
╰─▶ Because all versions of surya-ocr depend on pillow>=10.2.0,<11.0.0
    and you require pillow>=12, we can conclude that your requirements
    are unsatisfiable.
```

By contrast, **kraken and paddleocr both accept `pillow>=12`** and resolve to `pillow==12.3.0` **[V]**. surya is the sole offender.

### 3.3 The pillow finding — this drives the architecture

`surya-ocr` forces `pillow==10.4.0`. I audited that pin:

```
$ pip-audit -r  (pillow==10.4.0)
Found 24 known vulnerabilities in 1 package
pillow 10.4.0  PYSEC-2026-165, -2249, -2250, -2252 … -3496   Fix: 12.1.1 / 12.2.0 / 12.3.0
```

**[V] — 24 known vulnerabilities, every one fixed in a 12.x release.**

Pillow is *the image decoder*. In this system it is the component that will be handed hostile, attacker-supplied phone photos. Running a two-year-old decoder with 24 open advisories on exactly that input is the worst possible placement of a vulnerable dependency.

**This is not a dependency-hygiene nit; it is an architectural constraint.** It means:

> **The upload-handling API and any surya-based code can never share a Python environment.**

Recorded as **ADR-0007**. It maps to threat **T-03 (malicious image file)** in Phase 1.

### 3.4 HHD-Ethiopic reference code is not reproducible

The brief said to reproduce published numbers first to prove the harness is correct. The published baseline code **cannot be installed**. Two independent failures **[V]**:

```
# 1. requirements.txt has a literal syntax error
error: no such comparison operator "=", must be one of ~= == != <= >= < > ===
editdistance=0.60
            ^^^^^

# 2. after fixing that, the pin is impossible on any modern Python
× Because tensorflow==2.10.0 has no wheels with a matching Python ABI tag (cp311)
  hint: we only found wheels for tensorflow (v2.10.0) with tags: cp37m, cp38, cp39, cp310
```

Its `requirements.txt` pins `tensorflow==2.10.0`, `keras==2.10.0`, `numpy==1.23.4` **and** `torch==2.0.0` — both frameworks, all from 2022–23.

**Consequence, stated plainly:** "reproduce the published HHD numbers" is **not achievable by running the authors' code**. We reimplement the architecture in PyTorch and reproduce the *numbers*, accepting that any gap is confounded by reimplementation. I am flagging this now rather than discovering it in Phase 6. See ADR-0005.

### 3.5 Runtime environment [V]

`Python 3.11.15` · `Ubuntu 24.04.4` · `Docker 29.3.1` · `Compose v5.1.1` · `Node v22.22.2` · `psql 16.13` · **no GPU (`nvidia-smi` absent)**.

**Scope cut, called out loud:** every dependency claim in Phase 3 will be verified on **CPU only**. I cannot execute a CUDA install here. Anything GPU-specific will be marked untested rather than claimed working.

---

## 4. Datasets

| Dataset | Content | Licence | Reachable? |
|---|---|---|---|
| **Fidel** (`upanzi/fidel-dataset`) | ~40k handwritten + ~28k typed line images, 411 writers, + synthetic **[S]** | CC-BY-4.0 **[S]** | **[BLOCKED]** — HF 403 |
| **HHD-Ethiopic** | ~80k line images, 18th–20th c., ENALA archives **[P]** | **CC-BY-4.0 [P]** | Repo yes; data on HF/Zenodo, both blocked |
| **ADOCR** (Belay et al.) | Printed + synthetic Amharic line images **[S]** | Unknown | **Not located** |

### 4.1 Fidel — primary target, unverified

Sentence/line-level modern Amharic; the closest match to our target domain. **[S]** reports splits with `metadata.json`, `train_labels.json`, `test_labels.json` mapping filename → text. Published in IJDAR (`10.1007/s10032-026-00593-7`), preprint Research Square `rs-8118465`.

**I have not seen the dataset card, the schema, or the licence file.** Do not write a loader against the schema above — confirm it first (§8, Task 1).

### 4.2 HHD-Ethiopic — and why its skew is real, with evidence

The brief warned this dataset skews to classical Ge'ez calligraphy. **I can now confirm that from the ground truth itself.** The README's own samples **[P]**:

```
ወጽራኅየኒ፡ቦአ፡ቅድሜሁ፡ውስተ፡ዕዘኒሁ
ፍራስ፡እሳት፡ወጽሩዓን
ወአድኅነከ፡ይትፌሥሑ።
```

Every word boundary is **`፡` U+1361 ETHIOPIC WORDSPACE**, not a space. That is the classical Ge'ez convention. Modern everyday Amharic — the exam papers and shop ledgers this project targets — uses the ASCII space and reserves `፡` for decorative or archaic use.

So the transfer gap is not only handwriting style; it is **tokenisation**. A model trained on HHD learns that words are `፡`-delimited. Our WER definition must not inherit that assumption. See §5.3 and ADR-0006.

Splits **[S]**: ~6k IID test, ~16k 18th-century OOD test. Source: ENALA. Paper: **ICDAR 2024** (`Supplementary_file/ICDAR_2024_full_paper.pdf` in-repo **[P]**); search results also describe a NeurIPS 2023 Datasets & Benchmarks submission **[S]** — likely submitted there and published at ICDAR. Both citations noted; neither PDF readable.

### 4.3 ADOCR

**Not located.** Referenced across Belay et al. **[S]** as printed + synthetic Amharic line images. I found no canonical, fetchable download. Recorded as an open question (§8), **not** assumed available.

---

## 5. The Ethiopic script — computed inventory

**Everything in §5 is [V]**, computed locally from **UCD 17.0.0** (`unicodedata2`, PyPI). Reproducible; no web source involved.

> Re-derive every figure in this section with
> `pip install unicodedata2 && python docs/research/verify_ethiopic_inventory.py`.
> It exits non-zero if any number quoted here has gone stale.

### 5.1 Complete codepoint inventory

| Block | Range | Slots | **Assigned** | Categories |
|---|---|---|---|---|
| Ethiopic | U+1200–U+137F | 384 | **358** | 326 Lo, 3 Mn, 9 Po, 20 No |
| Ethiopic Supplement | U+1380–U+139F | 32 | **26** | 16 Lo, 10 So |
| Ethiopic Extended | U+2D80–U+2DDF | 96 | **79** | 79 Lo |
| Ethiopic Extended-A | U+AB00–U+AB2F | 48 | **32** | 32 Lo |
| Ethiopic Extended-B | U+1E7E0–U+1E7FF | 32 | **28** | 28 Lo |
| **TOTAL** | | 592 | **523** | |

Of these, **481 are `ETHIOPIC SYLLABLE`**; the remainder are punctuation (9), digits/numbers (20), tonal marks (10), combining marks (3), and supplement symbols.

**This 523-codepoint set is the project's supported inventory.** Note it spans the **astral plane** (Extended-B, U+1E7E0+) — so every layer must be UTF-8 clean and must not assume BMP. Python 3 strings are fine; JS `.length`, Postgres collations, and any fixed-width char assumption are not.

### 5.2 The abugida grid — why factored decoding is well-founded

The core block is a strict 8-column grid: base at `cp % 8 == 0`, vowel orders 1–7 at offsets 0–6, offset 7 a labialised/extra slot.

- **43** grid rows in U+1200–U+1357
- **37** rows carry a **complete 7-vowel series** ← the base-consonant inventory
- **34** rows have the 8th (labialised) slot filled
- **86** labialised syllables script-wide

```
U+1200 HA  : HA  HU  HI  HAA  HEE  HE  HO
U+1208 LA  : LA  LU  LI  LAA  LEE  LE  LO
U+1210 HHA : HHA HHU HHI HHAA HHEE HHE HHO
```

The brief said "~34 base consonants × 7 ≈ 238". The measured figure is **37 complete series (259 syllables)** in the core block; the 34 figure corresponds to those with a labialised form, and to the modern-Amharic working set. Both are right about different things — this is a definitional difference, not a contradiction, and the code will use the computed 37 with an explicit modern-Amharic subset.

**Why this matters for the contribution:** the factorisation is *perfectly regular*. Every family decomposes into (base, order) with no exceptions in the grid. A model with a 37-way base head and a 7-way vowel head covers 259 syllables with 44 output classes. A rare syllable is rare only as a *pair*; its components are common. This is the direct attack on the "few-pixel diacritic" failure mode. ADR-0005.

### 5.3 Homophones — computed equivalence classes

Four families are orthographically interchangeable in modern Amharic. Derived across all 7 orders **[V]**:

| Family | Sound | Members (order 1) | Canonical |
|---|---|---|---|
| H | /h/ | ሀ U+1200 · ሐ U+1210 · ኀ U+1280 | ሀ |
| S | /s/ | ሠ U+1220 · ሰ U+1230 | ሠ |
| TS | /tsʼ/ | ጸ U+1338 · ፀ U+1340 | ጸ |
| GLOTT | /ʔ/ | አ U+12A0 (GLOTTAL A) · ዐ U+12D0 (PHARYNGEAL A) | አ |

Extended across all seven vowel orders, normalisation **folds away 35 codepoints** (e.g. H-order4: ሃ U+1203 · ሓ U+1213 · ኃ U+1283 → ሃ).

**Why this inflates CER.** These glyphs are historically distinct but phonemically merged in modern Amharic. A writer choosing ሰ where the "correct" spelling is ሠ is not making an error a reader would notice. Two annotators transcribing the same image will disagree, and **[S]** confirms homophone normalisation is standard practice in Amharic NLP. Every such disagreement is scored as a substitution error against a model that read the glyph *correctly*.

**Therefore CER alone is a misleading headline number for this script**, and normalisation-aware CER is mandatory (the brief already requires it — this is the quantified justification). We report **both**, never normalisation-aware alone: raw CER is what a user sees; normalised CER is what the model actually got wrong. Reporting only the flattering one would be dishonest.

### 5.4 Punctuation and word separation [V]

```
U+1360 ፠ SECTION MARK        U+1365 ፥ COLON
U+1361 ፡ WORDSPACE           U+1366 ፦ PREFACE COLON
U+1362 ። FULL STOP           U+1367 ፧ QUESTION MARK
U+1363 ፣ COMMA               U+1368 ፨ PARAGRAPH SEPARATOR
U+1364 ፤ SEMICOLON
```

Plus **20 numeral codepoints** U+1369–U+137C (digits 1–9, tens, hundred, ten-thousand) — category `No`, a **non-positional** system. `int()` will not parse them; a dedicated Ge'ez numeral parser is required.

**The WER problem, stated precisely.** "Word" has no single definition here:

- Classical / HHD-Ethiopic: words separated by `፡` U+1361.
- Modern Amharic: words separated by U+0020, with `፡` rare or decorative.
- Mixed real-world pages: **both**, sometimes in one document.

Splitting on whitespace alone gives one giant "word" for classical text — WER ≈ 100% for a near-perfect transcription. Splitting on `፡` alone fails on modern text.

**Decision (ADR-0006):** tokenise on `[\s፡]+` (space *and* wordspace, collapsed), report WER under that rule, and report it **per corpus** so classical and modern splits are never averaged into a meaningless single number.

---

## 6. Top 10 difficulties and how we mitigate each

| # | Difficulty | Why it is hard here | Mitigation | Stage |
|---|---|---|---|---|
| 1 | **Vowel order is a few pixels** | ~238–259 syllables differ by a small stroke/loop. Flat 300-way softmax makes each rare syllable its own low-support class. | **Factored decoding**: 37-way base head + 7-way vowel head + labialisation head. 44 classes cover 259 syllables; components stay common. Ablated against flat CTC. | 4 |
| 2 | **Homophone annotator disagreement** | 4 families, 35 foldable codepoints; two honest annotators disagree. Inflates CER against a correct read. | Report raw **and** normalisation-aware CER using the §5.3 classes. Never report only one. | 6 |
| 3 | **"Word" is undefined** | `፡` vs space; WER≈100% on classical text under whitespace splitting. | Tokenise on `[\s፡]+`; report WER per corpus, never pooled. | 6 |
| 4 | **Warp on phone photos** | Curved baselines break line segmentation; **[S]** phone capture raises CER 3–8× vs flatbed. | UVDoc dewarp as stage 1, with a **quantitative** gate: straight ruled line in → straight out, measured as max deviation from fitted line. | 1 |
| 5 | **Flash shadow / uneven illumination** | **[S]** global Otsu over-thresholds bright regions (ink vanishes) and under-thresholds shadow (false characters). | Illumination correction + CLAHE local contrast; never a single global threshold. Feed greyscale to recognition, not a binarised image. | 1 |
| 6 | **Ruled paper** | Horizontal rules are mistaken for baselines/strokes; can merge or split lines. | Baseline-detection segmentation (kraken `blla`), which learns text baselines, not ink projections. Rule-suppression as a preprocessing option, ablated. | 3 |
| 7 | **Bleed-through** | **[S]** verso ink shows through, creating overlapping text and uneven background. | Illumination/contrast normalisation; train with synthetic bleed-through augmentation so the recogniser learns to ignore low-contrast mirrored strokes. | 1, 4 |
| 8 | **Reading order** | Multi-column, marginalia, tables. Wrong order = correct characters, useless output. | Dedicated stage; PP-DocLayoutV3 predicts order jointly with layout. Scored with **Kendall's tau**, not accuracy. | 2, 5 |
| 9 | **Dataset domain gap** | HHD is classical Ge'ez with `፡` tokenisation; Fidel is modern. Training on HHD and testing on phone photos measures the wrong thing. | Three splits: IID, unseen-writer, unseen-capture-condition. Fidel is the primary modern source; HHD is pretraining only, never the headline metric. | 6 |
| 10 | **Mixed scripts and Ge'ez numerals** | Ethiopic + Latin + ASCII digits on one page; 20 non-positional Ge'ez numerals `int()` cannot parse. | Charset spans all 523 codepoints + Latin + digits. Dedicated Ge'ez numeral parser; astral-plane-safe handling end to end. | 4, 5 |

---

## 7. Security findings surfaced during Phase 0

Recorded here because they were discovered during research; they feed Phase 1 and Phase 5.

1. **`pillow==10.4.0` — 24 known CVEs [V].** Forced by surya. Sits on the hostile-input path. → process isolation, ADR-0007.
2. **`docuwarp` has no licence [V]** and **vendors `.onnx` weights inside the wheel** (`package_data={"docuwarp": ["artifacts/*.onnx"]}`) with no checksum. A model blob shipped through PyPI with no integrity verification is a supply-chain hazard independent of the licence problem. → rejected.
3. **surya weights are not open source [P]** — OpenRAIL-M with a $5M ceiling. → baseline-only, never load-bearing.
4. **`paddlepaddle` declares no `requires_python` [V].** Metadata that loose means the resolver cannot protect us; it must be pinned exactly and isolated.
5. **Every model download needs revision pinning + checksum.** No `torch.load` of untrusted checkpoints — safetensors only. (`PP-DocLayoutV3_safetensors` appears to exist **[S]**; unverifiable, HF blocked.)

---

## 8. Open questions — what I could not verify

These are **blockers on Phase 3+**, not cosmetic gaps. Each needs a decision or an unblock.

| # | Question | Why blocked | Proposed resolution |
|---|---|---|---|
| 1 | **Fidel licence, schema, and splits** | HF 403 | **Two options: (a)** allowlist `huggingface.co` + `cdn-lfs.huggingface.co` on the egress proxy — cleanest; **(b)** you download the card + a sample shard out-of-band and drop them in `data/`. Cannot write a loader until one happens. |
| 2 | **Fidel actually contains what [S] claims** | HF 403 | Same as 1. All counts are unconfirmed. |
| 3 | **ADOCR availability** | Not located anywhere fetchable | Treat as unavailable. Do not plan on it. Revisit only if you have a direct contact/copy. |
| 4 | **Published CER/WER to reproduce** | All paper hosts blocked | Need the ICDAR 2024 PDF (it is *in* the HHD repo but binary). Either allowlist, or you supply the numbers. |
| 5 | **GPU behaviour** | No GPU in this container | All Phase 3 verification is CPU-only and will be labelled as such. |
| 6 | **PP-DocLayoutV3 weight format/licence** | HF blocked, Paddle docs blocked | Verify before adopting; ADR-0003 is provisional on this. |

**The honest summary of §8:** I can build and verify the entire application, security, and evaluation-harness layer without unblocking anything. I **cannot** write a Fidel data loader or reproduce a published number without resolving Q1 and Q4.

---

## 9. Sources

Primary, fetched this session: [datalab-to/surya](https://github.com/datalab-to/surya) · [VikParuchuri/surya](https://github.com/VikParuchuri/surya) · [PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) · [mittagessen/kraken](https://github.com/mittagessen/kraken) · [tanguymagne/UVDoc](https://github.com/tanguymagne/UVDoc) · [pstwh/docuwarp](https://github.com/pstwh/docuwarp) · [baudm/parseq](https://github.com/baudm/parseq) · [bdu-birhanu/HHD-Ethiopic](https://github.com/bdu-birhanu/HHD-Ethiopic) · [PyPI JSON API](https://pypi.org) · Unicode Character Database 17.0.0 via `unicodedata2`.

Secondary (search summaries; unverified): [Fidel — IJDAR](https://link.springer.com/article/10.1007/s10032-026-00593-7) · [Fidel — Research Square](https://www.researchsquare.com/article/rs-8118465/v1) · [HHD-Ethiopic — OpenReview](https://openreview.net/forum?id=dUFf0pgkC7) · [HHD-Ethiopic — HAL](https://inria.hal.science/hal-04223188v1) · [Blended Attention-CTC (SciTePress)](https://www.scitepress.org/Papers/2021/102842/102842.pdf) · [Homophone normalisation (IEEE)](https://ieeexplore.ieee.org/document/9672229/) · [RT-DocLayout](https://arxiv.org/pdf/2606.23344) · [upanzi/fidel-dataset](https://huggingface.co/datasets/upanzi/fidel-dataset) · [OCR-Ethiopic/HHD-Ethiopic](https://huggingface.co/datasets/OCR-Ethiopic/HHD-Ethiopic)
