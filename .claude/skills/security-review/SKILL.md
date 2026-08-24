---
name: security-review
description: >
  Audit new or changed code in this project against its 45 security controls - the
  per-surface checklists for endpoints, database access, uploads, AI calls and
  dependencies, plus the mutation-testing standard every control has to meet. Use this
  skill whenever you add or modify an API route, a database query, a model, a migration,
  an upload path, an LLM call or a dependency; whenever you write or review a security
  test; and whenever asked to "check this is safe", review a diff, or before opening a
  PR that touches user data. Also use it when adding a control, so it lands with a
  threat reference and a failing-without-it test rather than as unmapped scope creep.
---

# Security review

Two documents define the ground truth: `docs/THREAT_MODEL.md` (27 threats, 45 controls,
machine-checked coverage) and `docs/SECURITY.md` (per-control status, location, test).
This skill is the working procedure for applying them to a change.

The invariant everything hangs off:

> **A control with no threat is scope creep; a threat with no control is a bug.**

`python docs/research/verify_threat_coverage.py` enforces it — every threat cites a
control, every control cites a threat, and the two agree. It runs in CI and in
`make security`.

## The standard a control must meet

A control counts as implemented when **its test fails if the control is removed.**
Not "there is a test nearby". Not "the endpoint returns 200". The specific test must go
red when you delete the specific control.

This is worth the effort because the alternative is worse than nothing: three of this
project's redaction tests once passed while asserting against an empty string, so they
would have passed with redaction entirely deleted. A test that cannot fail manufactures
confidence.

Verify it the direct way:

```bash
cp src/adai/security/uploads.py /tmp/backup           # 1. snapshot
# 2. delete or invert the control
python -m pytest tests/security/test_uploads.py -q    # 3. confirm RED
cp /tmp/backup src/adai/security/uploads.py           # 4. restore
python -m pytest tests -q                             # 5. confirm GREEN
```

If step 3 stays green, either the test is wrong or another layer is covering for it.
Both are worth knowing; work out which before moving on.

## Reviewing by surface

Jump to the checklist for what changed. Full detail per control is in
`references/checklists.md`.

### A new or changed API endpoint

- [ ] **Authentication** enforced server-side via `Depends(current_user)` — never client-side gating (C-15)
- [ ] **Object-level authorisation**: ownership is in the `WHERE` clause, not a check after fetching (C-16)
- [ ] Another user's record returns **404, not 403** — a 403 confirms the id exists (T-02)
- [ ] **CSRF**: state-changing routes carry `Depends(require_csrf)` (C-08)
- [ ] **Request schema** subclasses `StrictModel` (`extra="forbid"`); no request body binds to an ORM model (C-20)
- [ ] **Response schema** is explicit and omits `blob_key`, `sha256`, `owner_id`, hashes and paths (C-21)
- [ ] **Rate limited** if it is expensive; inference gets its own tighter bucket (C-33)
- [ ] **Audit event** recorded for security-relevant outcomes (C-38)
- [ ] An **IDOR test** exists proving a second user gets 404

### A database query or migration

- [ ] **Parameterised** — no f-string or `%` formatting containing SQL (C-24)
- [ ] New user-data table has **RLS enabled AND forced**, with an owner-scoped policy (C-17)
- [ ] The predicate uses `NULLIF(current_setting(...), '')::uuid` so an unscoped session is *denied*, not errored
- [ ] Runtime roles get DML only; DDL belongs to the migrator (C-18)
- [ ] Watch for **`INSERT ... RETURNING`** — it is evaluated against the SELECT policy and will fail where you do not expect it
- [ ] Sensitive columns encrypted, with **no plaintext copy beside the ciphertext** (C-37)

### An upload or file path

- [ ] Content type from **magic bytes, never the extension**; SVG refused outright (C-27)
- [ ] Image **re-encoded** from decoded pixels — this is what destroys a polyglot (C-27)
- [ ] Pixel, dimension and byte caps enforced before decoding (C-28)
- [ ] **All EXIF stripped**, GPS included (C-29)
- [ ] Stored outside any web root, non-guessable key, served only via an authorising endpoint (C-30)

### An LLM call

- [ ] Untrusted text **never concatenated into the system role**; fenced and labelled in a user message (C-31)
- [ ] Output constrained to a schema and **validated before it reaches the database or UI** (C-31)
- [ ] Token ceiling, per-user quota, and the global spend breaker checked (C-32)
- [ ] The breaker **fails closed** — unable to read the meter means refuse (C-32)
- [ ] **C-41 redaction runs before egress.** Note it cannot redact an image: there the personal data is pixels (T-26)

### A dependency or model checkpoint

- [ ] `make security` passes; `api` and `dev` locks are strict (C-39)
- [ ] The API lockfile gained no ML package — `scripts/check_api_isolation.py` (C-45)
- [ ] Checkpoints are **safetensors only**; every pickle format is refused (C-34)
- [ ] Pinned by revision **and** SHA-256, verified before load (C-34)
- [ ] No `torch.load`, `pickle.load` or `pickle.loads` anywhere in source

## Adding a control

Land it complete, or it is scope creep:

1. Give it the next `C-NN` id in `docs/THREAT_MODEL.md` §8.
2. Cite the threat(s) it mitigates — and add the control to those threats' rows, both
   directions, or the coverage check fails.
3. Implement it on a live code path. A module nobody calls protects nothing; C-37 was
   briefly in exactly that state.
4. Write the failing-without-it test, and mutation-verify it.
5. Record it in `docs/SECURITY.md` with status, location and test name.
6. Run `python docs/research/verify_threat_coverage.py`.

Use the honest status vocabulary. **Partial** with the gap stated beats **Implemented**
with a caveat buried in a docstring. Four controls in this project are Partial and each
says exactly what is missing.

## Things that are already known

Do not re-litigate these; they are decided and documented.

| Question | Answer |
|---|---|
| Why 404 and not 403 for another user's record? | 403 confirms existence (enumeration oracle) |
| Why no hard account lockout? | It is a free DoS against any known email; R-02 accepts the tradeoff |
| Why synchroniser CSRF and not double-submit? | A sibling subdomain can write our cookies; §6.1 |
| Why can the app not read `audit_events`? | Deliberate: append-only via RLS, so it cannot tamper either |
| Why does the worker have BYPASSRLS? | It processes every user's documents and has no request path for an IDOR |
| Why is `is_complete` always False in redaction? | Person names are undetectable by regex in Amharic; claiming otherwise is dangerous |

## Further reading

- `references/checklists.md` — all 45 controls with threat, location and test.
- `docs/THREAT_MODEL.md` — assets, boundaries, actors, threats, residual risks.
- `docs/SECURITY.md` — per-control status and the mutation-testing results table.
