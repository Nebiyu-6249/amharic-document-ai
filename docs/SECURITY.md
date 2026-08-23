# Phase 5 — Security Controls

**Date:** 2026-08-23 · **Author role:** Application security engineer.

Every control in this document maps to a threat in
[THREAT_MODEL.md](THREAT_MODEL.md), and every implemented control has a test that
**fails when the control is removed**. That last property is the standard this project
holds itself to: a test that still passes with the control deleted is worse than no
test, because it manufactures confidence.

Status vocabulary, used strictly:

| Status | Meaning |
|---|---|
| **Implemented** | Code exists, is on a live code path, and has a failing-without-it test. |
| **Partial** | Something real is implemented, but the control is not fully discharged. The gap is stated. |
| **Deferred** | Implemented and tested, but wired behind a disabled flag with no route mounted. |
| **N/A** | Does not apply to this architecture. The reason is given. |

---

## 1. Mutation testing

Claiming "each control has a test that fails without it" is only meaningful if it has
been checked. Each control below was removed or inverted in turn, the suite was re-run,
and the control was restored. Results:

| Mutation | Outcome |
|---|---|
| CSRF `validate_token` always returns True | **caught** |
| `session_epoch` not bumped on password change | **caught** |
| Spend breaker fails **open** on a Redis error | **caught** |
| All checkpoint format checks removed | **caught** (9 tests) |
| Decryption swallows tampering and returns `""` | **caught** (2 tests) |
| Redaction reports `is_complete = True` | **caught** |
| Page text concatenated into the system role | **caught** |
| Webhook replay protection removed | **caught** |
| `FORCE ROW LEVEL SECURITY` dropped on `documents` | **caught** (4 tests) |
| RLS policy replaced with `USING (true)` | **caught** (3 tests) |
| Redaction processor removed from the log pipeline | **caught** |
| EXIF-destroying re-encode removed | **caught** |
| SVG/markup rejection removed | **caught** |
| Upload dimension cap removed | **caught** |
| IDOR ownership predicate removed | **caught** (2 tests) |
| Argon2 short-circuits on a missing account | **caught** |

One instructive near-miss: removing only the pickle-suffix branch of C-34 did **not**
fail the suite, because the second branch (`suffix != ".safetensors"`) still rejects the
file. That is layered defence working, not a gap — removing the whole gate fails nine
tests. It is recorded because "the mutation survived" deserved an explanation rather
than a silent re-run.

---

## 2. Control register

### 2.1 Transport and headers

| ID | Control | Threats | Where | Test | Status |
|---|---|---|---|---|---|
| **C-01** | Force HTTPS, redirect HTTP (308) | T-11, T-23 | `security/headers.py` | `test_plain_http_is_redirected_when_https_is_forced` | Implemented |
| **C-02** | HSTS, 2-year max-age, `includeSubDomains`, **no preload** | T-23, T-11 | `security/headers.py` | `test_hsts_is_sent_on_https_with_a_long_max_age`, `test_no_hsts_on_plain_http` | Implemented |
| **C-03** | CSP with per-response nonce and no `unsafe-inline`; `nosniff`; `frame-ancestors 'none'`; Referrer-Policy; Permissions-Policy; COOP/CORP | T-12, T-10, T-03 | `security/headers.py` | `test_security_headers_present_on_every_response` | Implemented |
| **C-04** | CORS explicit allowlist; wildcard rejected at startup; `Origin` never reflected | T-11 | `config.py`, `api/main.py` | `test_wildcard_cors_origin_is_refused` | Implemented |
| **C-05** | No directory listing | T-18 | — | `test_no_staticfiles_mount` | Implemented |

**On C-05:** the API mounts no static directory at all, so there is nothing to list.
Uploads are served only through an authenticated, authorising endpoint (C-30). The test
asserts the absence of `StaticFiles`, which is what makes the property durable.

**On C-02:** `preload` is deliberately absent. Preloading is effectively irreversible
and the domain is not stable; the brief says not to preload until it is.

### 2.2 Authentication and session

| ID | Control | Threats | Where | Test | Status |
|---|---|---|---|---|---|
| **C-06** | Argon2id, 64 MiB / t=3 / p=4 | T-08 | `security/passwords.py` | `test_hash_is_argon2id_not_a_fast_hash` | Implemented |
| **C-07** | `HttpOnly`, `Secure`, `SameSite=Lax`, host-only, bounded expiry | T-11, T-12 | `api/routes/auth.py` | `test_session_cookie_flags` | Implemented |
| **C-08** | CSRF **synchroniser** tokens on state-changing requests | T-11 | `security/csrf.py`, `api/deps.py` | `test_state_change_without_csrf_token_is_refused` + 4 more | Implemented |
| **C-09** | Invalidate **all** sessions on password change and reset | T-10, T-11 | `models.User.session_epoch` | `test_password_change_invalidates_existing_sessions` | Implemented |
| **C-10** | Reset tokens: CSPRNG, hashed at rest, 30-min expiry, single use | T-10 | `security/tokens.py` | `test_crypto_and_tokens.py` (6 tests) | Implemented |
| **C-11** | Reset rate limit, per-account **and** per-IP | T-10, T-08 | `security/ratelimit.py` | `test_reset_request_is_rate_limited_per_account` | Implemented |
| **C-12** | Anti-enumeration: identical body, status **and** timing | T-09 | `api/routes/auth.py`, `security/passwords.py` | `test_registration_does_not_reveal_existing_accounts`, `test_missing_account_still_does_real_argon2_work` | Implemented |
| **C-13** | Progressive delay + challenge, **never a hard lock** | T-08 | `security/ratelimit.py` | `test_there_is_no_hard_lockout` + 3 more | Implemented |
| **C-14** | Bot protection on registration, login, reset, upload | T-08, T-01, T-06 | `security/ratelimit.py` | `test_challenge_is_demanded_only_after_repeated_failures` | **Partial** |
| **C-15** | Authn/authz enforced server-side on every route | T-02, T-17, T-01 | `api/deps.py` | `test_upload_requires_authentication` | Implemented |

**C-14 is Partial, and the gap matters.** The challenge *threshold* is implemented and
enforced — after five failures the endpoint returns 429 and demands a challenge — but no
CAPTCHA or proof-of-work provider is integrated, so there is nothing to actually solve.
As it stands C-14 is a throttle, not bot protection. Wiring a provider is a Phase 6 task
and is listed in STATUS.md. Do not read the green test as "bots are stopped".

**On C-13, the tradeoff (THREAT_MODEL §6.2):** a hard lock after N failures turns an
authentication control into a denial-of-service weapon — anyone who knows an email
address could lock that account at will, for free. We accept weaker resistance to a
patient distributed attacker (residual risk **R-02**) and compensate with Argon2 cost,
dual-axis limits, and alerting.

### 2.3 Authorisation and data access

| ID | Control | Threats | Where | Test | Status |
|---|---|---|---|---|---|
| **C-16** | Object-level authorisation on every record fetch | T-02, T-18, T-07 | `api/deps.py:owned_document` | `test_idor.py` (4 tests) | Implemented |
| **C-17** | Postgres RLS on all user-data tables, **FORCE**d | T-02, T-07 | `migrations/0002` | `test_rls.py` (6 tests) | Implemented |
| **C-18** | Least-privilege database roles | T-02, T-21, T-24 | `scripts/db_roles.sql` | `test_worker_role_has_bypassrls_and_the_app_role_does_not` | Implemented |
| **C-19** | Public/anon key only in the browser; service key server-side | T-16, T-13 | — | — | **N/A** |
| **C-20** | Mass-assignment allowlists; no ORM binding of request bodies | T-14 | `schemas.py` (`extra="forbid"`) | `test_mass_assignment_is_rejected` | Implemented |
| **C-21** | Explicit response schemas; no internal ids, hashes, paths or traces | T-15, T-16, T-18, T-19 | `schemas.py` | `test_document_response_omits_internal_fields`, `test_unhandled_errors_do_not_leak_stack_traces` | Implemented |
| **C-22** | No default admin routes; admin behind separate auth | T-17 | `api/main.py` | `test_no_admin_or_doc_surface_in_non_dev` | Implemented |

**C-19 is N/A by decision (Q-4):** PostgreSQL is self-hosted and no database key of any
kind reaches the browser. There is no anon/service key split to get wrong. Recorded
rather than silently dropped, because "N/A" is only honest if the reason is stated.

**IDOR returns 404, never 403.** A 403 confirms the id exists, which is an enumeration
oracle. The IDOR tests assert 404 specifically.

**On C-17 and the four problems it surfaced.** Enabling RLS is not a one-line change,
and the fixes are worth recording because each is a trap:

1. Registration cannot satisfy an ownership `WITH CHECK` — there is no user yet. Solved
   with per-command policies: INSERT is open (creating a row leaks nothing, uniqueness
   is a constraint, and the API already returns an identical response either way),
   while SELECT/UPDATE/DELETE stay scoped.
2. `INSERT ... RETURNING` is evaluated against the **SELECT** policy. Registration sets
   the context to the new user's own id before inserting; audit writes use
   `insert(...).inline()` to suppress implicit RETURNING.
3. Login must find a user by email before an identity exists. Solved with a narrowly
   scoped `adai_auth` role (SELECT on `users`, nothing else), not by weakening the policy.
4. `current_setting(..., true)` returns `''`, and `''::uuid` **raises** instead of
   matching nothing. Policies use `NULLIF(...)` so an unscoped session is *denied*
   rather than erroring — denial is the correct failure direction.

**On C-18, the role split:**

| Role | Privileges | Why |
|---|---|---|
| `adai_migrator` | DDL, owns the schema | Only role that can change structure |
| `adai_app` | DML, **NOBYPASSRLS** | The API. RLS contains request-handling mistakes. |
| `adai_worker` | DML + **BYPASSRLS** | Legitimately processes every user's documents; has no request-handling path for an IDOR to arrive through. |
| `adai_auth` | SELECT on `users` only + BYPASSRLS | Pre-authentication credential lookup, nothing else. |

### 2.4 Input, uploads and storage

| ID | Control | Threats | Where | Test | Status |
|---|---|---|---|---|---|
| **C-23** | Strict input schemas: type, length, range, format | T-01, T-13, T-14 | `schemas.py` | `test_config.py`, `test_mass_assignment_is_rejected` | Implemented |
| **C-24** | Parameterised queries everywhere, including scripts and migrations | T-13 | whole tree | `test_no_fstring_or_percent_built_sql`, `test_migrations_interpolate_only_module_level_literals` | Implemented |
| **C-25** | Contextual output encoding; OCR output treated as untrusted | T-12, T-04 | `pipeline/assemble.py` | `test_ocr_text_is_escaped_before_entering_markdown` | Implemented |
| **C-26** | Sanitise before storing; retain the original for provenance | T-12, T-04 | `security/uploads.py`, `worker/main.py` | `test_polyglot_payload_does_not_survive_reencode` | **Partial** |
| **C-27** | Magic-byte allowlist, re-encode, **reject SVG** | T-03, T-01 | `security/uploads.py` | `test_svg_is_rejected` + 4 more | Implemented |
| **C-28** | Pixel, dimension and byte caps; decompression-bomb limits | T-03, T-01, T-22, T-06 | `security/uploads.py` | `test_decompression_bomb_is_rejected` + 2 more | Implemented |
| **C-29** | Strip all EXIF, especially GPS | T-03, T-07 | `security/uploads.py` | `test_all_exif_and_gps_are_destroyed` | Implemented |
| **C-30** | Uploads outside web root, non-guessable names, authenticated endpoint | T-18, T-02, T-03, T-21 | `api/routes/documents.py` | `test_blob_keys_are_unpredictable` | Implemented |

**C-24 is verified by static analysis, not by exercising an endpoint** — the claim is
that no such construction exists *anywhere*, which only an AST sweep can show. The check
is strict over `src/` and `scripts/` (every path that can see user input). Migrations are
checked separately: SQL cannot bind an *identifier*, so a table name in DDL must be
interpolated; the test asserts every interpolation resolves to a module-level literal,
and a migration takes no user input at all.

**C-26 is Partial, and this is a deliberate deviation.** The original *image* is
retained (encrypted blob, 90-day expiry), but the **unredacted transcription text is not
retained**. The brief asks to keep the original alongside the sanitised form for research
provenance. Keeping unredacted text would directly undermine C-41 and the Q-2 position on
minors: a research corpus containing the very identifiers we redacted defeats the purpose.
If provenance on raw text later proves necessary, the right design is a separately
encrypted, separately access-controlled store with its own consent basis — not a plaintext
column beside the redacted one. Flagged for your decision.

### 2.5 AI-specific

| ID | Control | Threats | Where | Test | Status |
|---|---|---|---|---|---|
| **C-31** | Prompt injection: role separation, fenced+labelled untrusted data, schema-constrained output, validate before use | T-04, T-26 | `ai/guard.py` | `test_ai_guard.py` (12 tests) | Implemented |
| **C-32** | Per-request token ceiling, per-user daily quota, **fail-closed** global spend breaker | T-06, T-04, T-22 | `ai/budget.py` | `test_breaker_fails_closed_when_redis_is_unreachable` + 2 | Implemented |
| **C-33** | Inference endpoint rate-limited separately and more tightly | T-06, T-01, T-22 | `security/ratelimit.py` | `test_inference_limit_is_tighter_than_the_general_one` | **Partial** |
| **C-34** | safetensors only; never `torch.load`; pin by revision; verify checksums | T-05, T-04 | `security/model_supply.py` | 9 tests incl. every pickle suffix | Implemented |

**C-33 is Partial:** the tighter limiter is implemented and tested, but **there is no
inference endpoint to attach it to yet** — recognition is a stub (ADR-0005) and LLM
post-correction is off by default (ADR-0009). The limiter must be wired at the moment
either goes live. Stated plainly so nobody assumes an unprotected endpoint is protected.

**On C-32 failing closed:** if Redis is unreachable we cannot read the spend meter, so we
refuse. Failing open risks an unbounded bill, which ends the project (T-06); failing
closed makes an off-by-default feature unavailable. That is the right way round.

**On C-31:** the defence does not make injection impossible. It makes a successful
injection *useless*: the model's only output channel is a fixed JSON schema, the response
is validated before it can reach the database or UI, and anything unparsable is discarded
in favour of the original transcription. Tested against four injection payloads and seven
malformed responses.

### 2.6 Secrets, dependencies, logging

| ID | Control | Threats | Where | Test | Status |
|---|---|---|---|---|---|
| **C-35** | No secrets in code, config or the frontend bundle | T-16, T-05, T-21 | `config.py`, `.env.example` | `test_no_hardcoded_secret_defaults_in_settings` | Implemented |
| **C-36** | Scan git history, purge findings, document rotation | T-16 | CI, `.secrets.baseline` | CI `security` job over full history | Implemented |
| **C-37** | Encrypt sensitive fields at rest (AES-256-GCM) | T-07, T-24, T-26 | `security/crypto.py`, `worker/main.py` | `test_transcription_is_redacted_and_encrypted_at_rest` + 8 | Implemented |
| **C-38** | Log security events; never secrets, tokens or document content | T-08, T-09, T-10, T-16, T-19, T-24 | `logging.py`, `security/audit.py` | `test_logging_redaction.py` (7 tests) | Implemented |
| **C-39** | CI dependency scanning with a build-failing threshold, SBOM | T-03, T-05, T-21, T-27 | `.github/workflows/ci.yml` | CI job; `make security` | Implemented |

**C-39 runs in two tiers, and the second one is a real finding.**

`scripts/audit_dependencies.sh` audits `api` and `dev` **strictly** — any advisory fails
the build, and both are clean. The `ml` extra is audited with two explicitly listed
exceptions, because `kraken 7.1` pins them and they cannot be moved:

| Package | Version | Advisory | Fix | Blocked by |
|---|---|---|---|---|
| `click` | 8.2.1 | PYSEC-2026-2132 | 8.3.3 | `kraken 7.1` requires `click>=8.1,<8.3` |
| `lightning` | 2.6.1 | PYSEC-2026-3624 | **none published** | `kraken 7.1` requires `lightning==2.6.1` |

Both were proven unfixable by resolver error, not assumed. The exceptions are listed by
id in the script, so a **new** ml advisory still fails the build — this is a tracked
exception, not a disabled check. It is tolerable rather than urgent only because the ml
stack never runs in the API container (ADR-0007 / C-45); review it whenever kraken is
upgraded.

This tier also caught a live issue during Phase 5: `cryptography` had to be raised
through 48.0.1 and 49.0.0 to **50.0.0**, each bump revealing the next advisory. The
original constraint (`<48`) would have blocked the fix.

**C-36 baseline:** the full history was scanned at Phase 1 and again here — two commits at
the time, no secret-shaped content in any blob. Nothing has needed purging, so **no
rotation has been necessary**. If that ever changes, the rotation goes in this section.

**C-37 nearly shipped as decoration.** The first implementation stored the redacted
transcription in a plaintext column *and* its ciphertext beside it, which protects
nothing. Now the plaintext columns hold only provenance (which stages ran) and all page
content lives solely in the ciphertext, decrypted on read for the document's owner. The
test asserts `markdown == ""` and that no region text appears in the plaintext JSONB —
the assertion that would have caught the original mistake.

**Scope of C-37:** it defends against someone who obtains the database alone — a stolen
backup, a misdirected dump, an operator with table read access (T-24). It does **not**
defend against an attacker holding the application's key material, because the running
application must be able to read these values.

### 2.7 Data protection

| ID | Control | Threats | Where | Test | Status |
|---|---|---|---|---|---|
| **C-40** | Consent record per document, documented lawful basis, research opt-in separate | T-07, T-26, T-20, T-01, T-06 | `models.ConsentRecord` | `test_full_upload_flow`, DB generated column | Implemented |
| **C-41** | Automated PII redaction on stored transcriptions | T-07, T-20, T-26 | `security/redaction.py`, `worker/main.py` | `test_redaction.py` (8 tests) | **Partial** |
| **C-42** | Retention with automatic expiry; deletion purges blobs | T-07, T-20 | `worker/main.py`, `api/routes/documents.py` | `test_deletion_purges_the_blob`, `test_retention_deadline_is_set_on_every_upload` | Implemented |

**C-41 is Partial and this is the most important caveat in the document.**

Implemented: emails, Ethiopian and international phone numbers, long digit runs (IDs,
account numbers) and numeric dates are removed deterministically, before anything is
persisted and therefore before anything could cross TB-06 to OpenAI (Q-3).

**Not implemented: person-name detection.** Amharic personal names are ordinary Ethiopic
words with no case marking, no honorific requirement and no reliable surface pattern. A
regex cannot find them, and one that pretended to would be actively harmful — a
transcription would be flagged "redacted" while a student's name sat in it. So
`RedactionResult.is_complete` is hard-coded `False` and there is a test asserting it stays
that way. Name redaction needs a trained Amharic NER model, which does not exist here.

**Consequence:** no transcription produced by this system may currently be treated as
de-identified. That constrains the research corpus and it should be stated to the ethics
board rather than discovered by them.

**On Q-2 (minors):** enforced in the **schema**, not in application code.
`consent_records.eligible_for_training` is a Postgres generated column over
`research_opt_in AND NOT subject_is_minor`, and `subject_is_minor` defaults to `true` so
unknown means excluded. Verified: a minor with research opt-in is ineligible, and
`UPDATE ... SET eligible_for_training = true` is refused by the database.

**On Q-5 (retention):** originals expire 90 days after upload (`originals_expire_at`,
NOT NULL on every row); the retention sweep runs in the worker; user-initiated deletion
purges the blob as well as the row.

### 2.8 Deferred, and the isolation control

| ID | Control | Threats | Where | Test | Status |
|---|---|---|---|---|---|
| **C-43** | Webhook signature verification + replay protection | T-25, T-26 | `payments/webhooks.py` | 4 tests | **Deferred** |
| **C-44** | Server-side price authority | T-25 | `payments/webhooks.py` | `test_price_comes_from_the_server_not_the_client` | **Deferred** |
| **C-45** | API image contains no ML stack | T-03, T-05, T-21, T-27 | `scripts/check_api_isolation.py` | `test_api_lockfile_has_no_ml_dependency`, CI | Implemented |

**C-43/C-44 are wired, tested and disabled.** `ADAI_PAYMENTS_ENABLED` defaults to false
and no route mounts them. The signature covers the timestamp (otherwise an attacker keeps
a valid signature and moves the clock), replay protection uses atomic `SET NX`, and the
price comes from a server-side catalogue with no code path accepting a client amount.

**C-45 exists because of a measurement**, not a principle: `surya-ocr` caps `pillow<11`,
forcing `pillow 10.4.0` — 24 known CVEs — onto the code path that decodes hostile uploads.
Verified inside the built image: no `torch`, `paddle`, `surya`, `kraken`, `onnxruntime` or
`cv2`, and `pillow 12.3.0`.

---

## 3. Coverage

All 45 controls are accounted for: **38 Implemented**, **4 Partial** (C-14, C-26, C-33,
C-41), **2 Deferred** (C-43, C-44), **1 N/A** (C-19).

`docs/research/verify_threat_coverage.py` enforces the bidirectional invariant from
THREAT_MODEL.md §8.9 — every threat cites a control, every control cites a threat, and
the two agree. It runs in CI and in `make security`.

---

## 4. Known gaps, stated plainly

1. **No person-name redaction (C-41).** Nothing produced here is de-identified.
2. **No real bot challenge (C-14).** The throttle is real; the challenge is a threshold
   with no provider behind it.
3. **C-33 has no endpoint to protect yet.** Wire it the moment inference goes live.
4. **Unredacted transcription text is not retained (C-26).** A deliberate deviation from
   the brief; the provenance question needs your decision.
5. **RLS does not protect against a superuser or the schema owner.** It contains
   application mistakes (T-02), not a compromised DBA (T-24), which is why C-37 and C-38
   exist alongside it.
6. **Field encryption is only as good as key custody.** `ADAI_SECRET_KEY` is not yet in a
   secret manager, and key rotation is designed for (versioned ciphertexts) but not
   implemented.
