# Claude Code Build Prompt — Amharic Document AI

Paste everything below the line into Claude Code as your first message in an empty directory.

---

## ROLE

You are acting as a four-in-one senior engineer on this project, and you must hold all four roles simultaneously for every decision you make:

1. **Staff-level ML engineer** specialising in document AI, OCR, and low-resource scripts. You have shipped OCR systems to production and you know that line-level CER on a clean benchmark is not the same as a working product.
2. **Senior backend/full-stack engineer.** Python, FastAPI, PostgreSQL, Next.js, Docker. You write code that has tests, migrations, and a rollback path.
3. **Application security engineer.** You threat-model before you build. You assume every uploaded file is hostile, every string is injection, and every model checkpoint is a pickle bomb until proven otherwise.
4. **Pragmatic tech lead.** You cut scope loudly rather than shipping something half-wired. When you are blocked, you say so and propose two options rather than inventing a plausible-looking stub and moving on.

State at the start of your first response which role is driving each phase. Re-state the relevant role at the top of each phase as you enter it.

---

## THE PROJECT

Build **Amharic Document AI**: a system that turns an ordinary phone photo of an Ethiopian document (handwritten exam paper, shop ledger, handwritten form, textbook page) into structured, correctly-ordered, machine-readable output — Markdown and JSON — not an unordered wall of characters.

The Ethiopic script is an abugida: roughly 34 base consonants × 7 vowel orders ≈ 238 core syllables, plus labialised forms, Ge'ez numerals, and Ethiopic punctuation. The vowel order is encoded as a small stroke or loop attached to the base glyph, so visually adjacent characters differ by a few pixels. This is the central recognition difficulty and every design decision should be traceable back to it.

**What is already solved and must NOT be rebuilt from scratch:** line-level recognition on clean, pre-cropped, deskewed lines. Public datasets and baselines exist. Use them.

**What is unsolved and is therefore the actual project:** the full page, under real capture conditions — warp, shadow, ruled paper, bleed-through, multi-column layout, tables, marginalia, mixed Ethiopic/Latin/digit text, and correct reading order.

---

## PHASE 0 — RESEARCH BEFORE YOU WRITE ANY CODE

Do not scaffold anything until this phase is complete and written up.

Use `WebSearch` and `WebFetch` aggressively. Read actual README files and source, not just abstracts. For each item below, record: what it does, licence, last commit date, Python/CUDA/framework version constraints, install method, model weight format, and whether it is maintained.

**Datasets to investigate**
- `upanzi/fidel-dataset` on Hugging Face — sentence-level Amharic OCR, ~40k handwritten + ~28k typed line images from 411 writers, plus synthetic. Read the dataset card, the label JSON schema, and the licence.
- `OCR-Ethiopic/HHD-Ethiopic` on Hugging Face and `github.com/bdu-birhanu/HHD-Ethiopic` — ~80k historical handwritten line images with an IID test set and a harder out-of-distribution 18th-century test set. Note: its content skews to classical Ge'ez calligraphy and transfers imperfectly to modern everyday handwriting. Record that limitation.
- Search for ADOCR (Belay et al.) printed/synthetic Amharic database availability.

**Repositories to investigate**
- `VikParuchuri/surya` — detection, layout analysis, reading order, OCR. Read the README fully, including its licence terms, which are unusual and may constrain commercial use. Report the licence explicitly.
- PaddleOCR and `PaddlePaddle/PP-DocLayoutV3` — layout analysis designed for non-planar documents; predicts multi-point boxes and reading order for skewed/curved pages in one pass. Assess whether PaddlePaddle as a dependency is acceptable or a liability.
- Document dewarping: UVDoc, `pstwh/docuwarp` (ONNX UVDoc inference, has CPU and CUDA extras), DocTr. Pick one and justify.
- Line/baseline segmentation for handwriting: search for ARU-Net, Kraken, eScriptorium.
- Recognition architectures: CRNN+CTC references, PARSeq, TrOCR. Also find the Belay et al. attention-CTC Amharic work and any factored/decomposed-output Ethiopic recognisers.

**Web research on difficulties — search for and summarise**
- Ethiopic homophone characters that are orthographically interchangeable in modern Amharic (the several glyphs read "ha", the two "sä", the two "tsä", the two "ʾä"). Determine how annotators disagree on these and why this inflates CER.
- Ethiopic Unicode block coverage: the main block plus Supplement, Extended, and Extended-A. Produce the complete codepoint inventory you will support.
- Ethiopic punctuation and word separation (the historical word-separator vs the modern space) and what that means for defining WER.
- Known failure modes of OCR on ruled paper, ink bleed-through, and phone-flash shadow.

**Deliverable for Phase 0:** write `docs/RESEARCH.md` containing a component comparison table, a licence audit table, a dependency compatibility matrix (Python version, torch version, CUDA version, ONNX runtime, OS), and a "top 10 difficulties and how we mitigate each" section. Also write `docs/adr/0001-*.md` through `000N-*.md` as short Architecture Decision Records for each major choice, each with the alternatives you rejected and why.

**Stop after Phase 0 and show me the research summary before proceeding.**

---

## PHASE 1 — THREAT MODEL

Before scaffolding, write `docs/THREAT_MODEL.md`. Enumerate assets, trust boundaries, and attackers. Cover at minimum:

- Anonymous internet user hitting the upload endpoint
- Authenticated user attempting to read another user's documents (IDOR / broken object-level authorisation)
- Malicious image file (polyglot, decompression bomb, EXIF payload, SVG with script)
- Malicious *content within* a document — text on the page crafted to hijack the LLM post-correction step
- Supply-chain: a poisoned model checkpoint or a typosquatted package
- Cost attack: an attacker burning your GPU budget or LLM API quota
- Data-protection: uploaded documents contain real student names, grades, and business records

Map every mitigation in Phase 5 to a specific threat here. A control with no threat is scope creep; a threat with no control is a bug.

---

## PHASE 2 — ARCHITECTURE

Five independently testable stages. Build them as separate modules with clean interfaces. Do **not** attempt an end-to-end model first.

1. **Geometric rectification** — dewarp + illumination correction. Acceptance: a straight ruled line in the input is straight in the output, measured quantitatively.
2. **Layout analysis** — detect and classify regions: paragraph, heading, table, figure, marginal note, page number.
3. **Line segmentation** — baseline-detection approach within regions. Projection profiles are not acceptable for handwriting; justify if you disagree.
4. **Line recognition** — two tracks:
   - *Baseline:* CRNN + CTC trained on Fidel. Reproduce published numbers first to prove the harness is correct.
   - *Contribution:* **factored decoding.** Predict base consonant (~34 classes) and vowel order (7 classes) as separate heads rather than treating each of ~300 syllables as an atomic class, with an additional head for labialised forms. Rationale: it directly attacks the reported failure mode (small, visually similar diacritics) and makes rare syllables non-rare, since their components are common. Implement both and build the ablation harness to compare them.
5. **Reading order + structure assembly** — serialise regions, reconstruct tables, emit Markdown/JSON, with an optional LM rescoring pass over beam candidates.

**Application layer:** FastAPI backend, PostgreSQL, background job queue for GPU inference, Next.js frontend. Inference must be async — never block an HTTP request on a GPU job.

**Deployment target:** frontend static-hostable; model inference behind a GPU-backed endpoint. Everything containerised with Docker Compose for local dev.

---

## PHASE 3 — REPO SCAFFOLD

Produce a real, runnable repository. Not a sketch.

- `pyproject.toml` with pinned, resolvable dependencies. Verify the versions actually co-install — run it, don't guess.
- `docker-compose.yml` bringing up API, worker, Postgres, and frontend with one command.
- Alembic migrations from the first commit.
- `.env.example` with every variable documented and **no real values**.
- `Makefile` with `make dev`, `make test`, `make lint`, `make security`, `make train`, `make eval`.
- Pre-commit hooks: ruff, mypy, and a secrets scanner.
- CI workflow running tests, lint, type-check, dependency audit, and secret scan on every push.

---

## PHASE 4 — CLAUDE SKILLS

At the start of the build, enumerate the skills available to you in this environment. For any that are relevant to this work, use them rather than improvising — in particular any skill covering frontend design, document handling, PDF reading, or data analysis.

Then create project-specific skills under `.claude/skills/` so future sessions inherit this context automatically. At minimum:

- `ethiopic-script/` — the full codepoint inventory, homophone equivalence classes, punctuation and tokenisation conventions, and the normalisation rules this project uses. Every future session must apply these consistently.
- `ocr-eval/` — how to run the evaluation harness and which metrics are mandatory to report.
- `security-review/` — the checklist from Phase 5, formatted so a future session can re-audit a new endpoint against it.

Each skill needs a proper `SKILL.md` with a description precise enough to trigger correctly. If a skill-creator skill is available, use it rather than hand-rolling the format.

---

## PHASE 5 — SECURITY (MANDATORY, NOT OPTIONAL)

Implement every control below. For each one, write the control, write a test that fails without it, and record it in `docs/SECURITY.md` with its threat-model reference.

**Transport & headers**
- Force HTTPS; redirect HTTP.
- HSTS with a long max-age and `includeSubDomains`. Do not preload until the domain is stable.
- Full security header set: CSP (no `unsafe-inline`; use nonces), `X-Content-Type-Options: nosniff`, `X-Frame-Options`/`frame-ancestors`, `Referrer-Policy`, `Permissions-Policy`.
- Lock down CORS to an explicit origin allowlist. No wildcards, no reflecting the Origin header.
- Disable directory listing on every static path.

**Authentication & session**
- Argon2id password hashing with tuned parameters. Never MD5, SHA, or bcrypt-by-default.
- Session cookies: `HttpOnly`, `Secure`, `SameSite=Lax` or `Strict`, host-only, sensible expiry.
- CSRF tokens on all state-changing requests when using cookie-based sessions. Double-submit or synchroniser pattern — state which and why.
- Invalidate **all** existing sessions on password change and on password reset.
- Password reset links: single-use, short expiry, cryptographically random, hashed at rest, invalidated on use.
- Rate-limit password reset requests per-account and per-IP.
- Prevent user enumeration: identical response body, status code, **and timing** for existing vs non-existing accounts, on login, registration, and reset.
- Account lockout after repeated failures — but implement it as progressive delay plus a challenge rather than a hard lock, so an attacker cannot lock out a legitimate user by name. Explain this tradeoff in the docs.
- Bot protection on registration, login, reset, and upload.
- Enforce authentication and authorisation **server-side** on every route. No client-side-only gating anywhere.

**Authorisation & data access**
- Object-level authorisation on every record fetch. Every document read must verify ownership. Write explicit IDOR tests.
- Postgres Row Level Security enabled on all user-data tables, with policies as defence in depth behind application checks.
- Least-privilege database roles. The application role gets no DDL, no superuser, no access to tables it does not need.
- If using a hosted DB with client-side keys, the public/anon key must be the only key ever reaching the browser. The service key stays server-side and is never bundled.
- Block field tampering / mass assignment: explicit allowlists on every input schema. Never bind request bodies straight to ORM models.
- Trim API responses: explicit response schemas. Never return internal IDs, hashes, file paths, model internals, or stack traces.
- Remove all default/framework admin routes; if an admin surface exists, put it behind separate auth and IP restriction.

**Input, uploads, and storage**
- Validate every input with strict schemas — type, length, range, format, and charset.
- Parameterised queries everywhere. No string-built SQL, ever, including in analytics or migration scripts.
- Escape and contextually encode all user content on output. Treat OCR output as untrusted user content — it is.
- Sanitise before storing, and store the original alongside the sanitised form where provenance matters for research.
- **Upload allowlist by content, not extension:** verify magic bytes, then re-encode every image through a decoder before storage so any embedded payload is destroyed. Reject SVG entirely.
- Cap image pixel dimensions and set decompression-bomb limits. Cap total request size and per-file size at the reverse proxy *and* in the application.
- Strip all EXIF metadata, especially GPS — this is both a security and a subject-privacy control.
- Store uploads outside the web root, with non-guessable names, served only through an authenticated, authorising endpoint. Never serve user uploads from the same origin as the app if it can be avoided.

**AI-specific**
- **Prompt-injection defence:** OCR'd page text is attacker-controlled. Never concatenate it into an instruction context. Use strict role separation, delimit and label it as untrusted data, constrain the model to a structured output schema, and validate that output before it touches the database or the UI.
- Cap AI usage: per-user quotas, per-request token ceilings, a global daily spend circuit breaker that fails closed.
- Rate-limit the inference endpoint separately and more tightly than normal routes — it is your most expensive surface.
- **Model supply chain:** load `safetensors` only. Never `torch.load` an untrusted checkpoint — pickle deserialisation is arbitrary code execution. Pin every model by revision hash and verify checksums on download.

**Secrets, dependencies, logging**
- No secrets in code, config, or the frontend bundle. Everything through environment variables or a secret manager.
- Scan git history for previously committed secrets and purge anything found; document the rotation.
- Encrypt sensitive fields at rest. Uploaded documents contain names and grades — treat them accordingly.
- Log security events: auth attempts, authorisation failures, upload rejections, rate-limit trips, admin actions. Never log secrets, tokens, or document content.
- Dependency scanning in CI with a build-failing threshold, plus automated update PRs and a generated SBOM.

**Data protection (added — your list did not cover this and AURAK ethics review will ask)**
- Consent records tied to each uploaded document, with a documented lawful basis.
- Automated PII redaction pass on stored transcriptions.
- Data retention policy with automatic expiry, and a working user-initiated deletion path that actually purges blobs and backups.

**Deferred (implement as stubs behind a feature flag, wired but disabled)**
- Payment webhook signature verification and replay protection.
- Server-side price authority — never trust a client-supplied amount.

---

## PHASE 6 — TESTING & EVALUATION

- Unit tests for every pipeline stage; integration tests for the full page path; end-to-end test from upload to structured output.
- A dedicated security test suite: IDOR, CSRF, upload bypass attempts, prompt injection, rate-limit enforcement, enumeration timing.
- Evaluation harness reporting, mandatorily: CER, WER, **normalisation-aware CER** (using the homophone equivalence classes), NED, layout mAP by class, reading-order Kendall's tau, and end-to-end field-level F1.
- Three evaluation splits: IID, unseen-writer, unseen-capture-condition.
- A baseline runner that evaluates a general-purpose vision-language model on the same benchmark, so we know from day one whether an off-the-shelf VLM already solves this.

---

## OPERATING RULES

- **Verify, don't assume.** Run the install. Run the tests. If you claim a version works together, you have executed it.
- **Never fabricate.** If a repository, dataset, model, or API does not exist or you cannot reach it, say so plainly. Do not invent a plausible URL or a plausible API signature.
- **Gate between phases.** Stop after Phase 0 and after Phase 1 and show me your output before continuing.
- **Cut scope out loud.** If something cannot be completed properly, tell me what you are deferring and why, and leave a documented stub — never a silent fake.
- **Every security control gets a test.** A control without a failing-without-it test does not count as implemented.
- Commit in logical units with clear messages. Never commit a secret, a dataset, or a model weight.
- Finish with `docs/STATUS.md`: what works, what is stubbed, what is untested, what the next three tasks are, and every known risk.
