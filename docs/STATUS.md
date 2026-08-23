# Project Status

**Date:** 2026-08-23 · **Phase reached:** end of Phase 3 (scaffold). Phase 5 (security
implementation) and Phase 6 (evaluation) are not started.

Everything below was verified by running it in the session that produced this repo,
except where explicitly marked **UNVERIFIED**.

---

## 1. What works

### Verified by execution

| Area | Evidence |
|---|---|
| **Dependency locks** | Three locks generated from `pyproject.toml` and resolved: api (46 pins), dev, ml (405 pins). `pillow==12.3.0` throughout. |
| **Install** | `uv venv` + dev lock installed; package installed editable; all imports resolve. |
| **Database** | PostgreSQL 16.13 live; Alembic migration applied and **round-tripped up/down/up/down/up** cleanly. |
| **Migration rollback** | Initially broken — `downgrade` left ENUM types behind, so re-upgrade failed. Fixed with explicit `Enum(...).drop()`. |
| **Q-2 minors exclusion** | `eligible_for_training` is a Postgres **generated column**. A minor with research opt-in returns ineligible, and `UPDATE ... SET eligible_for_training = true` is refused by the database. |
| **Q-5 retention** | `originals_expire_at` is NOT NULL and set to upload + 90 days on every upload. |
| **API** | 9 routes live under uvicorn; `/healthz` and `/readyz` (real DB round-trip) both 200. |
| **Worker** | arq worker consumed a real job in 0.13 s and persisted a transcription. |
| **End-to-end** | register → login → upload → enqueue → worker → transcription retrieved over real HTTP against real Postgres and Redis. |
| **Upload defences** | GPS+EXIF destroyed on the live path; polyglot payload destroyed by re-encode; SVG, decompression bomb, oversize dimensions, GIF, truncated and empty files all rejected. |
| **Security headers** | CSP with per-response nonce and no `unsafe-inline`, `nosniff`, `X-Frame-Options: DENY`, Referrer-Policy, Permissions-Policy, COOP/CORP — confirmed on live responses. |
| **Docker image** | API image **built and run**; served `/healthz` and `/readyz` from inside the container against host Postgres. |
| **C-45 in the image** | `torch`, `paddle`, `surya`, `kraken`, `onnxruntime`, `cv2` all absent from the built image; `pillow 12.3.0` present. |
| **Frontend** | `npm install`, `tsc --noEmit` and `next build` all clean; standalone output. |
| **Quality gates** | ruff clean, ruff-format clean, **mypy strict clean on 36 files**, 92 tests passing, `pip-audit` clean, secret scan clean, `docker compose config` valid. |

### Implemented pipeline stages

| Stage | State |
|---|---|
| 1 — Illumination correction | **Real.** Background-field division; acceptance test asserts a synthetic shadow gradient is measurably flattened. |
| 5 — Reading order + assembly | **Real.** Region ordering, Markdown/JSON emission, OCR text escaped before entering Markdown. |
| Ethiopic module | **Real.** 523 codepoints, four homophone families folding 35 codepoints across all 7 vowel orders, `[\s፡]+` tokenisation. |
| Evaluation metrics | **Real.** CER, normalisation-aware CER, WER, NED, Kendall's tau, layout mAP, field-level F1. |

---

## 2. What is stubbed

Every stub marks its own output. `StageResult.stub` and `stub_reason` propagate through
assembly, into the database (`contains_stub_stages`), and out through the API response.
**No stub fabricates content.**

| Stub | Why | Unblocked by |
|---|---|---|
| **Stage 1 dewarping** | UVDoc weights (MIT) not vendored and not checksum-verified | Fetch + checksum the weights (ADR-0002) |
| **Stage 2 layout** | Needs PP-DocLayoutV3 weights + the paddle container | Verify weight format/licence (ADR-0003 is still **Provisional**) |
| **Stage 3 line segmentation** | Needs kraken from the ml extra. **Deliberately does not fall back to projection profiles** — ADR-0004 rejects them for ruled paper | Install ml extra, fine-tune `blla` |
| **Stage 4 recognition** | No checkpoint; both tracks need Fidel. Returns **empty text, not plausible Amharic** | Dataset access, then train |
| **`data/fidel.py`** | Schema never observed; raises `FidelNotAvailableError` with an actionable message | Unblock Hugging Face, or supply files out of band |
| **`make train` / `make eval`** | Exit 1 with an explanation rather than pretending | Same as above |

---

## 3. What is untested or unverified

| Item | Status | Why |
|---|---|---|
| **GPU inference** | **UNVERIFIED** | No GPU in this environment (`nvidia-smi` absent). Every claim here is CPU-only. |
| **ml extra install** | **UNVERIFIED** | Resolves to 405 pins, but torch/kraken were never downloaded or imported. Only resolution is proven. |
| **worker-ml image** | **UNVERIFIED** | `docker/worker.Dockerfile` accepts `LOCKFILE=ml.lock.txt`; that variant was never built. |
| **`docker compose up` (full stack)** | **PARTIAL** | See §4. Compose file validates; the API image builds and runs. postgres/redis/frontend images were never pulled here. |
| **Frontend against a live API** | **UNVERIFIED** | Builds and typechecks; never rendered against a running backend. |
| **CI workflow** | **UNVERIFIED** | Never executed — no CI run has happened on this branch yet. |
| **Postgres RLS (C-17)** | **NOT IMPLEMENTED** | Phase 5. Application-level authorisation (C-16) is implemented and IDOR-tested. |
| **Least-privilege DB roles (C-18)** | **NOT IMPLEMENTED** | Phase 5. The dev role currently owns its schema. |

---

## 4. `docker compose up` — what actually happened

The instruction was that Phase 3 must end with `docker compose up` bringing the stack
live. **It does not, in this environment, and the reason is external.**

The egress policy permits container *manifest* APIs but denies the CDN hosts that serve
layer blobs:

```
registry-1.docker.io           401 → auth ok, then 429 rate-limited
production.cloudfront.docker.com   403  ← layer CDN denied
public.ecr.aws  → d2glxqk2uabbnd.cloudfront.net  403  ← layer CDN denied
mcr.microsoft.com              200  ← the only registry that serves layers
```

`postgres:16-alpine`, `redis:7-alpine`, `python:3.11-slim` and `node:22-alpine` cannot
be pulled here. Retrying does not help; this is policy, not transient.

**What I did instead of claiming success:**

1. Validated the compose file properly — `docker compose config` passes, six services.
2. Parameterised the base image (`ARG BASE_IMAGE`) and **actually built the API image**
   against the one reachable registry, then **ran it** and served `/healthz` and
   `/readyz` from inside the container against real Postgres.
3. Brought the same stack up **natively** — PostgreSQL 16, Redis 7, uvicorn, arq — and
   drove the complete upload → worker → transcription path over real HTTP.

So the application is proven live and the container path is proven to build and serve.
The one unproven link is compose orchestrating images it cannot download.

**On a machine with normal registry access, `make dev` should work as written** — but I
have not run it, and I am not claiming I have.

---

## 5. Bugs found and fixed during this phase

Recorded because each was found by running something, not by reading it.

1. **Migration rollback was broken.** `downgrade` dropped tables but left ENUM types, so
   re-upgrade failed. Fixed with explicit enum drops; now round-trips five times.
2. **Three redaction tests passed vacuously.** structlog caches the stderr handle, so
   `redirect_stderr` captured nothing and every "secret is absent" assertion was trivially
   true. Added a stream seam plus a guard test that fails if capture breaks.
3. **The upload endpoint never enqueued a job.** Found only by running the end-to-end flow.
4. **Transcription endpoint returned 500.** Stored stages carry `duration_ms`, which the
   response schema forbids. Fixed by projecting onto declared fields; regression test added.
5. **arq pool was bound to one event loop.** Cross-loop `RuntimeError`. Made loop-aware.
6. **`ADAI_CORS_ALLOW_ORIGINS` crashed at startup.** pydantic-settings JSON-decodes complex
   types before validators run; fixed with `NoDecode` plus a CSV validator.
7. **Duplicate `Server` header** — uvicorn appends its own after middleware. Suppressed at
   the uvicorn layer.
8. **`arq` caps redis-py at 5.x** (8.1.0 is current). Audited: no known CVEs, so recorded
   in ADR-0011 with a revisit trigger rather than switching queues.
9. **`RUF001` flagged every Ethiopic character** as "ambiguous Unicode, did you mean Latin
   U?". Exempted with justification — the rule fights this project's domain.

Each security control was also **mutation-tested**: redaction, EXIF stripping, SVG
rejection, dimension caps, the IDOR ownership predicate and the Argon2 timing path were
each removed in turn, the corresponding test was confirmed to fail, and the control was
restored.

---

## 6. The next three tasks

1. **Unblock the Fidel dataset (blocks everything ML).** Either allowlist
   `huggingface.co` + `cdn-lfs.huggingface.co`, or drop the card and a sample shard into
   `data/raw/fidel/`. Then write the loader against the **observed** schema and delete
   `FidelNotAvailableError`. Until this happens, stage 4 cannot be trained and no
   published number can be reproduced.
2. **Phase 5 — implement the remaining controls with failing-without-them tests.** The
   large gaps are CSRF synchroniser tokens (C-08), progressive delay + challenge (C-13),
   bot protection (C-14), password reset (C-10/C-11), Postgres RLS (C-17), least-privilege
   DB roles (C-18), AI quotas and the fail-closed spend breaker (C-32/C-33), and PII
   redaction before anything crosses TB-06 (C-41).
3. **Phase 6 — stand up the VLM baseline runner (ADR-0010).** surya reports Amharic at
   74.6%. Until we know how an off-the-shelf VLM scores on our splits, we do not know
   whether the pipeline is worth building. This is a decision gate, and it should run
   before more pipeline effort.

---

## 7. Known risks

| Risk | Severity | Position |
|---|---|---|
| **An off-the-shelf VLM may already be good enough** | **High** | ADR-0010 exists to find out early. If the baseline wins, say so and re-scope to the factored-decoding result plus the application layer. |
| **Fidel is unverified in every respect** | **High** | Licence, schema and contents all come from search snippets. Nothing is built on it yet, deliberately. |
| **ADR-0003 is Provisional** | Medium | PP-DocLayoutV3's weight format and licence are unverifiable while HF is blocked. If the weights are pickle-only, C-34's safetensors-only rule forces a rethink. |
| **HHD-Ethiopic transfers poorly** | Medium | Classical Ge'ez, `፡`-tokenised, 18th–20th c. Pretraining only; never a headline metric. |
| **No unseen-capture-condition data exists** | Medium | The split that matters most for the product claim must be collected by us, with consent. Not started. |
| **Reimplementation confounds reproduction** | Medium | HHD's published code does not install (`tensorflow==2.10.0` has no cp311 wheel), so any gap to published numbers is confounded. Must be stated in any writeup. |
| **surya baseline container carries 24 CVEs** | Low, contained | Accepted risk R-01: offline only, never on the request path, never sees user data. |
| **arq pins redis-py to 5.x** | Low | No known CVEs today. Revisit trigger recorded in ADR-0011. |
| **Ethiopic Extended-B is astral** | Low | Handled in Python; the frontend and DB collation paths are **not yet tested** for it. |

---

## 8. How to run what exists

```bash
make install          # venv + dev lock + editable install
make migrate          # apply migrations (needs Postgres)
make test             # 92 tests
make lint typecheck   # ruff + mypy strict
make security         # audit, secret scan, C-45, doc invariants
make dev              # docker compose up  (needs registry access; see section 4)
```

Native equivalent, which is what was actually verified here:

```bash
uvicorn adai.api.main:app --host 127.0.0.1 --port 8000 --no-server-header
arq adai.worker.main.WorkerSettings
```
