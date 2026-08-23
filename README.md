# Amharic Document AI

Turn an ordinary phone photo of an Ethiopian document — a handwritten exam paper, a
shop ledger, a form, a textbook page — into structured, correctly-ordered,
machine-readable Markdown and JSON.

> **Project status: scaffold.** The application, security and evaluation layers are
> real and tested. The recognition models are not trained and several pipeline stages
> are explicit, marked stubs. Read [docs/STATUS.md](docs/STATUS.md) before assuming any
> capability. Nothing in this repository fabricates a transcription.

## Why this is hard

Ethiopic is an abugida: roughly 34 base consonants × 7 vowel orders, plus labialised
forms, Ge'ez numerals and its own punctuation. The vowel order is a small stroke or loop
attached to the base glyph, so visually adjacent characters differ by a few pixels.
Measured from the Unicode database, the supported inventory is **523 codepoints across
five blocks**, one of which is astral.

Line-level recognition on clean, pre-cropped lines is largely solved and is not what
this project builds. The unsolved part is the **full page under real capture
conditions**: warp, shadow, ruled paper, bleed-through, multi-column layout, tables,
marginalia, mixed scripts, and correct reading order.

## Architecture

Five independently testable stages ([ADR-0001](docs/adr/0001-staged-pipeline-not-end-to-end.md)):

| # | Stage | Status |
|---|---|---|
| 1 | Geometric rectification | illumination correction **implemented**; dewarping stubbed |
| 2 | Layout analysis | stub — needs PP-DocLayoutV3 weights |
| 3 | Line segmentation | stub — needs kraken in the ml extra |
| 4 | Line recognition | stub — needs a trained checkpoint |
| 5 | Reading order + assembly | **implemented** |

The API process contains **no ML dependencies**, enforced in CI. See
[ADR-0007](docs/adr/0007-process-isolation-of-ml-stacks.md): the alternative drags a
decoder with 24 known CVEs onto the path that parses hostile uploads.

## Quick start

```bash
make dev        # docker compose up: api, worker, postgres, redis, frontend
make migrate    # apply alembic migrations
make test       # unit + security tests
make lint       # ruff + mypy
make security   # pip-audit, secret scan, API isolation check, SBOM
```

Copy `.env.example` to `.env` first and fill it in. No secret in that file is real.

## Documentation

| Document | Contents |
|---|---|
| [docs/RESEARCH.md](docs/RESEARCH.md) | Component comparison, licence audit, dependency matrix, script analysis, top-10 difficulties |
| [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) | 27 threats, 45 controls, machine-checked coverage |
| [docs/adr/](docs/adr/) | 11 architecture decision records |
| [docs/STATUS.md](docs/STATUS.md) | What works, what is stubbed, what is untested, known risks |

## Licence

Apache-2.0. Datasets and model weights carry their own terms — see the licence audit in
[docs/RESEARCH.md](docs/RESEARCH.md) §2, particularly the OpenRAIL-M restriction on
surya's weights.
