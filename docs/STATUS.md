# Project Status

**Date:** 2026-08-23 · **Phase reached:** all phases complete (0–6). The remaining work is blocked on dataset
access, not on engineering — see §6.

Everything below was verified by running it in the session that produced this repo,
except where explicitly marked **UNVERIFIED**.

---

## 1. What works

### Verified by execution

| Area | Evidence |
|---|---|
| **Dependency locks** | Three locks generated from `pyproject.toml` and resolved: api **47**, dev **111**, ml **132** pins. `pillow==12.3.0` throughout. (An earlier revision of this document quoted 46/405; those were line counts including `# via` annotations, not pins.) |
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
| **Quality gates** | ruff clean, ruff-format clean, **mypy strict clean on 57 files**, **246 tests passing**, `pip-audit` clean, secret scan clean, `docker compose config` valid. |

### Implemented pipeline stages

| Stage | State |
|---|---|
| 1 — Illumination correction | **Real.** Background-field division; acceptance test asserts a synthetic shadow gradient is measurably flattened. |
| 5 — Reading order + assembly | **Real.** Region ordering, Markdown/JSON emission, OCR text escaped before entering Markdown. |
| Ethiopic module | **Real.** 523 codepoints, four homophone families folding 35 codepoints across all 7 vowel orders, `[\s፡]+` tokenisation. |
| Evaluation metrics | **Real.** CER, normalisation-aware CER, WER, NED, Kendall's tau, layout mAP, field-level F1. |


### Security controls (Phase 5)

45 controls: **38 Implemented, 4 Partial, 2 Deferred, 1 N/A** — full register with threat
references and per-control tests in [SECURITY.md](SECURITY.md).

| Area | Verified |
|---|---|
| **Row Level Security (C-17)** | Enabled and FORCEd on all six user-data tables. Proven at the SQL layer: an unscoped session sees 0 rows, user A cannot read user B's document even by direct id, and the app role cannot read the audit log at all. |
| **Least-privilege roles (C-18)** | Four roles with different jobs; test asserts `adai_app` is NOBYPASSRLS and `adai_worker` is BYPASSRLS. |
| **CSRF (C-08)** | Synchroniser tokens; missing, forged and cross-session tokens all refused. |
| **Session invalidation (C-09)** | `session_epoch` bump kills every issued cookie on password change. |
| **Reset tokens (C-10)** | CSPRNG, SHA-256 at rest, 30-minute expiry, single use. |
| **Progressive delay (C-13)** | Exponential backoff capped at 8s on both account and IP axes; **no hard lockout** by design. |
| **Prompt injection (C-31)** | Role separation, fenced untrusted data, schema-constrained output; 4 injection payloads and 7 malformed responses all refused. |
| **Spend breaker (C-32)** | **Fails closed** when Redis is unreachable — tested against a dead Redis. |
| **Model supply chain (C-34)** | Every pickle format refused; checksum mismatch refuses to load; floating revisions rejected at construction. |
| **Encryption at rest (C-37)** | AES-256-GCM; tampering and wrong keys rejected; **no plaintext copy stored beside the ciphertext**. |
| **Mutation testing** | 16 controls removed or inverted in turn; every one caught by its test. Table in SECURITY.md §1. |
| **Dependency audit (C-39)** | Two tiers. `api` and `dev` are strict and clean. The `ml` extra carries two advisories that `kraken 7.1` pins in place (`click<8.3`, `lightning==2.6.1`, the latter with **no published fix**) — proven unfixable by resolver error, listed by id so new findings still fail the build. |


### Evaluation harness (Phase 6)

| Component | State |
|---|---|
| **Metric set** | CER, normalisation-aware CER, WER, NED, layout mAP by class, reading-order Kendall's tau, field-level F1 — all implemented and unit-tested. |
| **Harness** | `evaluate()` runs any system implementing `transcribe()`, so our pipeline and an off-the-shelf VLM go through identical code on identical samples. Reports **per corpus**, never pooled. |
| **Three splits** | `build_splits()` produces IID, unseen-writer and unseen-capture. Writers are held out **whole** — a test asserts no writer appears on both sides. Splits are deterministic (SHA-256 buckets, not salted `hash()`). |
| **CLI** | `adai-eval`, with meaningful exit codes: 0 a real result, 1 a stubbed run, 2 a refusal. |
| **Baselines** | `pipeline`, `surya` (quarantined container only), `openai-vlm` (consent-gated). |

Four refusals are built in, each preventing a specific way of reporting a number that is
wrong in a flattering direction:

- an **empty corpus** is refused, because zero samples score 0.0 on everything, which
  reads as a perfect system;
- an **empty split** is refused for the same reason, and `Splits.gaps` names it;
- a **stubbed run** is flagged in the report, in `notes`, and by exit code 1;
- a **failed sample** is scored as total error rather than skipped, because skipping
  failures quietly improves the mean.

The **unseen-capture split is empty and will stay empty** until data is collected: Fidel
and HHD-Ethiopic are both pre-cropped line images, so neither contains warped, shadowed
or ruled-paper page captures. `build_splits` returns an empty split rather than
substituting IID data — a visible gap beats a false result.

### Project skills (Phase 4)

Three skills under `.claude/skills/`, so a future session inherits these conventions
without being told:

| Skill | Covers |
|---|---|
| `ethiopic-script` | 523-codepoint inventory, four homophone families, `[\s፡]+` tokenisation, Ge'ez numerals, astral-plane warning |
| `ocr-eval` | Mandatory metrics, the three splits, the reporting rules, baseline constraints |
| `security-review` | Per-surface checklists, the mutation-testing standard, how to add a control |

Both reference files are **generated** — from the Unicode database and from
`docs/SECURITY.md` respectively — so they cannot drift. `make skills` regenerates them
and a test fails if either is stale. 19 tests check frontmatter, trigger-phrase
presence, the progressive-disclosure line budget, that every referenced file exists, and
that the quoted figures still match the code.

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
| **`make train`** | Exits 1 with an explanation rather than pretending | Same as above |
| **`make eval`** | Runs, then exits 2 because no corpus exists. The harness itself is real and tested | Same as above |

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

Phase 5 added nine more, all found by running things:

10. **RLS blocked registration.** The `WITH CHECK` predicate cannot be satisfied before
    an identity exists. Split into per-command policies.
11. **`INSERT ... RETURNING` is evaluated against the SELECT policy.** Broke both
    registration and audit writes; fixed by scoping the context first and using
    `.inline()` for audit inserts.
12. **Login could not read `users`** — the row is hidden by RLS before authentication.
    Added a narrowly scoped `adai_auth` role.
13. **`current_setting` returns `''`, and `''::uuid` raises** instead of matching
    nothing. Policies now use `NULLIF` so an unscoped session is denied, not errored.
14. **The Redis client was bound to one event loop**, same class of bug as the arq pool.
15. **CSRF tokens were keyed to the wrong session string** — `issue_session` stamps a
    timestamp and was called twice, so the stored token never matched the cookie.
16. **C-37 was decoration.** The first version stored the redacted transcription in a
    plaintext column *and* its ciphertext beside it. Now only the ciphertext carries
    content, asserted by a test.
17. **`cryptography` had to be bumped 47 → 50** through three chained advisories; the
    original `<48` upper bound would have blocked the fix. Caught by C-39.
18. **`pyproject.toml` declared the `adai-eval` console script before the module
    existed.** Nothing caught it for two phases; a test now imports it.
19. **A missing `ADAI_AUTH_DATABASE_URL` makes every login fail** with "invalid
    credentials", which looks like a password problem. Now a startup error outside dev.

Each security control was also **mutation-tested**: 16 controls — redaction, EXIF stripping, SVG rejection,
dimension caps, the IDOR predicate, the Argon2 timing path, CSRF validation, session
epoch, the fail-closed breaker, checkpoint format gates, authenticated decryption,
redaction completeness, prompt-injection role separation, webhook replay protection,
RLS FORCE, and the RLS policy itself — were each removed or inverted in turn, the
corresponding test confirmed failing, and the control restored. Table in
[SECURITY.md](SECURITY.md) §1.

---

## 6. The next three tasks

1. **Unblock the Fidel dataset (still blocks everything ML).** Either allowlist
   `huggingface.co` + `cdn-lfs.huggingface.co`, or drop the card and a sample shard into
   `data/raw/fidel/`. Then write the loader against the **observed** schema and delete
   `FidelNotAvailableError`. Nothing in stage 4 can be trained until this happens.
2. **Phase 6 — the VLM baseline runner (ADR-0010).** surya reports Amharic at 74.6%.
   Until we know how an off-the-shelf VLM scores on our splits we do not know whether the
   pipeline is worth building. This is a decision gate and should run before more
   pipeline effort.
3. **Close the four Partial controls** (SECURITY.md §4): an Amharic NER model for name
   redaction (C-41), a real bot challenge provider (C-14), wiring the inference limiter
   when an endpoint exists (C-33), and your decision on raw-text provenance (C-26).

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
| **No transcription is de-identified (C-41)** | **High** | Person names are not detected and cannot be by regex. `is_complete` is hard-coded False. This constrains the research corpus and must be stated to the ethics board. |
| **C-14 is a throttle, not bot protection** | Medium | The challenge threshold fires but no provider is integrated, so there is nothing to solve. |
| **ml extra carries two unfixable advisories** | Medium | `kraken 7.1` pins `click<8.3` and `lightning==2.6.1`; lightning's has no published fix. Contained because the ml stack never runs in the API container (C-45). Revisit on any kraken upgrade. |
| **Key custody for C-37** | Medium | `ADAI_SECRET_KEY` is not in a secret manager. Ciphertexts are versioned for rotation, but rotation is not implemented. |
| **RLS does not stop a superuser** | Medium | It contains application mistakes (T-02), not a compromised DBA (T-24). C-37 and C-38 exist alongside it for that reason. |

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
