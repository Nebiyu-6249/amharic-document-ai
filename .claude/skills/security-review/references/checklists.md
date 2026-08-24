# Control checklists

Generated from `docs/SECURITY.md` by
`.claude/skills/security-review/scripts/regenerate_checklists.py`.
Do not hand-edit: regenerate it.

Status vocabulary is used strictly. **Partial** means something real is
implemented but the control is not fully discharged, and the gap is stated in
docs/SECURITY.md §4. Treat Partial as an open item, not a pass.


## Transport and headers

| ID | Control | Threats | Implementation | Test | Status |
|---|---|---|---|---|---|
| C-01 | Force HTTPS, redirect HTTP (308) | T-11, T-23 | `security/headers.py` | `test_plain_http_is_redirected_when_https_is_forced` | Implemented |
| C-02 | HSTS, 2-year max-age, `includeSubDomains`, **no preload** | T-23, T-11 | `security/headers.py` | `test_hsts_is_sent_on_https_with_a_long_max_age`, `test_no_hsts_on_plain_http` | Implemented |
| C-03 | CSP with per-response nonce and no `unsafe-inline`; `nosniff`; `frame-ancestors 'none'`; Referrer-Policy; Permissions-Policy; COOP/CORP | T-12, T-10, T-03 | `security/headers.py` | `test_security_headers_present_on_every_response` | Implemented |
| C-04 | CORS explicit allowlist; wildcard rejected at startup; `Origin` never reflected | T-11 | `config.py`, `api/main.py` | `test_wildcard_cors_origin_is_refused` | Implemented |
| C-05 | No directory listing | T-18 | — | `test_no_staticfiles_mount` | Implemented |

## Authentication and session

| ID | Control | Threats | Implementation | Test | Status |
|---|---|---|---|---|---|
| C-06 | Argon2id, 64 MiB / t=3 / p=4 | T-08 | `security/passwords.py` | `test_hash_is_argon2id_not_a_fast_hash` | Implemented |
| C-07 | `HttpOnly`, `Secure`, `SameSite=Lax`, host-only, bounded expiry | T-11, T-12 | `api/routes/auth.py` | `test_session_cookie_flags` | Implemented |
| C-08 | CSRF **synchroniser** tokens on state-changing requests | T-11 | `security/csrf.py`, `api/deps.py` | `test_state_change_without_csrf_token_is_refused` + 4 more | Implemented |
| C-09 | Invalidate **all** sessions on password change and reset | T-10, T-11 | `models.User.session_epoch` | `test_password_change_invalidates_existing_sessions` | Implemented |
| C-10 | Reset tokens: CSPRNG, hashed at rest, 30-min expiry, single use | T-10 | `security/tokens.py` | `test_crypto_and_tokens.py` (6 tests) | Implemented |
| C-11 | Reset rate limit, per-account **and** per-IP | T-10, T-08 | `security/ratelimit.py` | `test_reset_request_is_rate_limited_per_account` | Implemented |
| C-12 | Anti-enumeration: identical body, status **and** timing | T-09 | `api/routes/auth.py`, `security/passwords.py` | `test_registration_does_not_reveal_existing_accounts`, `test_missing_account_still_does_real_argon2_work` | Implemented |
| C-13 | Progressive delay + challenge, **never a hard lock** | T-08 | `security/ratelimit.py` | `test_there_is_no_hard_lockout` + 3 more | Implemented |
| C-14 | Bot protection on registration, login, reset, upload | T-08, T-01, T-06 | `security/ratelimit.py` | `test_challenge_is_demanded_only_after_repeated_failures` | **Partial** |
| C-15 | Authn/authz enforced server-side on every route | T-02, T-17, T-01 | `api/deps.py` | `test_upload_requires_authentication` | Implemented |

## Authorisation and data access

| ID | Control | Threats | Implementation | Test | Status |
|---|---|---|---|---|---|
| C-16 | Object-level authorisation on every record fetch | T-02, T-18, T-07 | `api/deps.py:owned_document` | `test_idor.py` (4 tests) | Implemented |
| C-17 | Postgres RLS on all user-data tables, **FORCE**d | T-02, T-07 | `migrations/0002` | `test_rls.py` (6 tests) | Implemented |
| C-18 | Least-privilege database roles | T-02, T-21, T-24 | `scripts/db_roles.sql` | `test_worker_role_has_bypassrls_and_the_app_role_does_not` | Implemented |
| C-19 | Public/anon key only in the browser; service key server-side | T-16, T-13 | — | — | **N/A** |
| C-20 | Mass-assignment allowlists; no ORM binding of request bodies | T-14 | `schemas.py` (`extra="forbid"`) | `test_mass_assignment_is_rejected` | Implemented |
| C-21 | Explicit response schemas; no internal ids, hashes, paths or traces | T-15, T-16, T-18, T-19 | `schemas.py` | `test_document_response_omits_internal_fields`, `test_unhandled_errors_do_not_leak_stack_traces` | Implemented |
| C-22 | No default admin routes; admin behind separate auth | T-17 | `api/main.py` | `test_no_admin_or_doc_surface_in_non_dev` | Implemented |

## Input, uploads and storage

| ID | Control | Threats | Implementation | Test | Status |
|---|---|---|---|---|---|
| C-23 | Strict input schemas: type, length, range, format | T-01, T-13, T-14 | `schemas.py` | `test_config.py`, `test_mass_assignment_is_rejected` | Implemented |
| C-24 | Parameterised queries everywhere, including scripts and migrations | T-13 | whole tree | `test_no_fstring_or_percent_built_sql`, `test_migrations_interpolate_only_module_level_literals` | Implemented |
| C-25 | Contextual output encoding; OCR output treated as untrusted | T-12, T-04 | `pipeline/assemble.py` | `test_ocr_text_is_escaped_before_entering_markdown` | Implemented |
| C-26 | Sanitise before storing; retain the original for provenance | T-12, T-04 | `security/uploads.py`, `worker/main.py` | `test_polyglot_payload_does_not_survive_reencode` | **Partial** |
| C-27 | Magic-byte allowlist, re-encode, **reject SVG** | T-03, T-01 | `security/uploads.py` | `test_svg_is_rejected` + 4 more | Implemented |
| C-28 | Pixel, dimension and byte caps; decompression-bomb limits | T-03, T-01, T-22, T-06 | `security/uploads.py` | `test_decompression_bomb_is_rejected` + 2 more | Implemented |
| C-29 | Strip all EXIF, especially GPS | T-03, T-07 | `security/uploads.py` | `test_all_exif_and_gps_are_destroyed` | Implemented |
| C-30 | Uploads outside web root, non-guessable names, authenticated endpoint | T-18, T-02, T-03, T-21 | `api/routes/documents.py` | `test_blob_keys_are_unpredictable` | Implemented |

## AI-specific

| ID | Control | Threats | Implementation | Test | Status |
|---|---|---|---|---|---|
| C-31 | Prompt injection: role separation, fenced+labelled untrusted data, schema-constrained output, validate before use | T-04, T-26 | `ai/guard.py` | `test_ai_guard.py` (12 tests) | Implemented |
| C-32 | Per-request token ceiling, per-user daily quota, **fail-closed** global spend breaker | T-06, T-04, T-22 | `ai/budget.py` | `test_breaker_fails_closed_when_redis_is_unreachable` + 2 | Implemented |
| C-33 | Inference endpoint rate-limited separately and more tightly | T-06, T-01, T-22 | `security/ratelimit.py` | `test_inference_limit_is_tighter_than_the_general_one` | **Partial** |
| C-34 | safetensors only; never `torch.load`; pin by revision; verify checksums | T-05, T-04 | `security/model_supply.py` | 9 tests incl. every pickle suffix | Implemented |

## Secrets, dependencies, logging

| ID | Control | Threats | Implementation | Test | Status |
|---|---|---|---|---|---|
| C-35 | No secrets in code, config or the frontend bundle | T-16, T-05, T-21 | `config.py`, `.env.example` | `test_no_hardcoded_secret_defaults_in_settings` | Implemented |
| C-36 | Scan git history, purge findings, document rotation | T-16 | CI, `.secrets.baseline` | CI `security` job over full history | Implemented |
| C-37 | Encrypt sensitive fields at rest (AES-256-GCM) | T-07, T-24, T-26 | `security/crypto.py`, `worker/main.py` | `test_transcription_is_redacted_and_encrypted_at_rest` + 8 | Implemented |
| C-38 | Log security events; never secrets, tokens or document content | T-08, T-09, T-10, T-16, T-19, T-24 | `logging.py`, `security/audit.py` | `test_logging_redaction.py` (7 tests) | Implemented |
| C-39 | CI dependency scanning with a build-failing threshold, SBOM | T-03, T-05, T-21, T-27 | `.github/workflows/ci.yml` | CI job; `make security` | Implemented |

## Data protection

| ID | Control | Threats | Implementation | Test | Status |
|---|---|---|---|---|---|
| C-40 | Consent record per document, documented lawful basis, research opt-in separate | T-07, T-26, T-20, T-01, T-06 | `models.ConsentRecord` | `test_full_upload_flow`, DB generated column | Implemented |
| C-41 | Automated PII redaction on stored transcriptions | T-07, T-20, T-26 | `security/redaction.py`, `worker/main.py` | `test_redaction.py` (8 tests) | **Partial** |
| C-42 | Retention with automatic expiry; deletion purges blobs | T-07, T-20 | `worker/main.py`, `api/routes/documents.py` | `test_deletion_purges_the_blob`, `test_retention_deadline_is_set_on_every_upload` | Implemented |

## Deferred, and the isolation control

| ID | Control | Threats | Implementation | Test | Status |
|---|---|---|---|---|---|
| C-43 | Webhook signature verification + replay protection | T-25, T-26 | `payments/webhooks.py` | 4 tests | **Deferred** |
| C-44 | Server-side price authority | T-25 | `payments/webhooks.py` | `test_price_comes_from_the_server_not_the_client` | **Deferred** |
| C-45 | API image contains no ML stack | T-03, T-05, T-21, T-27 | `scripts/check_api_isolation.py` | `test_api_lockfile_has_no_ml_dependency`, CI | Implemented |

---

**45 controls** in the register.

Currently **Partial**, with the gap described in docs/SECURITY.md §4:

- C-14 (Authentication and session)
- C-26 (Input, uploads and storage)
- C-33 (AI-specific)
- C-41 (Data protection)

