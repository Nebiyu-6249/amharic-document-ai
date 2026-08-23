# ADR-0007: The upload API and the ML stacks never share a Python environment

**Status:** Accepted · **Date:** 2026-08-23 · **Driver:** Application security engineer

## Context
This ADR exists because of a measurement, not a principle.

**[V]** `surya-ocr` hard-constrains `pillow>=10.2.0,<11.0.0`. Proven by resolver error:
```
× Because all versions of surya-ocr depend on pillow>=10.2.0,<11.0.0
  and you require pillow>=12, we can conclude that your requirements are unsatisfiable.
```
Adding surya to the API environment therefore **silently downgrades pillow from 12.3.0 to 10.4.0** (resolution B, 228 packages **[V]**).

**[V]** `pip-audit` on that pin:
```
Found 24 known vulnerabilities in 1 package
pillow 10.4.0  PYSEC-2026-165, -2249, -2250, -2252 … -3496   Fix: 12.1.1 / 12.2.0 / 12.3.0
```

**Pillow is the image decoder.** In this system it is the component that parses attacker-supplied phone photos — the single most hostile input we accept. A 24-CVE decoder on that path is the worst possible placement of a vulnerable dependency. It is not a theoretical concern: image-decoder CVEs are routinely memory-safety bugs reachable from a crafted file.

By contrast **kraken and paddleocr both accept `pillow>=12`** and resolve to 12.3.0 **[V]**. surya is the sole cause.

## Decision
**Hard architectural boundary.** Separate containers, separate Python environments, separate lockfiles:

| Container | Contents | pillow |
|---|---|---|
| `api` | FastAPI, SQLAlchemy, psycopg, upload validation, re-encoding | **12.3.0, current** |
| `worker-ocr` | torch, kraken, our recogniser | ≥12 |
| `worker-layout` | paddlepaddle, paddleocr (ADR-0003) | pinned exactly |
| `baseline-vlm` | surya (ADR-0010), **evaluation only, never on the request path** | 10.4.0, quarantined |

Rules that follow:
1. The `api` image **must not** contain surya, torch, or paddle. Enforced by a CI check that fails the build if the API lockfile contains them.
2. The first thing the API does with an upload is **verify magic bytes and re-encode through a current decoder** before anything else touches it (Phase 5).
3. The `baseline-vlm` container is **offline-only** — it runs against the evaluation corpus, never against user uploads, and has no network path from the request handler.
4. Every container gets its own `pip-audit` run in CI with a build-failing threshold.

## Alternatives rejected
| Alternative | Why rejected |
|---|---|
| One environment, accept pillow 10.4.0 | Puts 24 CVEs on the hostile-input path. Not acceptable at any convenience gain. |
| One environment, force pillow 12 and drop surya | Loses the VLM baseline, which is the control that tells us whether the project is worth building (ADR-0010). |
| Patch/vendor surya to relax the pin | Unsupported fork of a dependency whose *weights* we cannot relicense anyway. Maintenance burden with no upside. |
| Isolate by virtualenv within one container | A venv is not a security boundary — same kernel, same filesystem, same process namespace. Containers at least give us a real one. |

## Consequences
- **Positive:** the hostile-input path runs a current, patched decoder. The vulnerable one exists only in an offline evaluation container that never sees user data.
- **Positive:** each stage's dependencies evolve independently; a surya upgrade cannot break the API.
- **Negative:** four images to build, cache, and keep audited. Larger CI surface and longer builds.
- **Negative:** inter-container communication (job queue + shared object storage) instead of function calls — more moving parts, and the interfaces must be typed and validated.
- Directly satisfies the async-inference requirement: the API cannot block on a GPU job because the GPU job is not in the API process.

## Threat-model mapping
Recorded as **C-45** in `docs/THREAT_MODEL.md` §8.6. Mitigates **T-03** (malicious image file),
**T-05** (poisoned checkpoint / typosquat), **T-21** (worker compromise and lateral movement)
and **T-27** (vulnerable dependency reaching production).

C-45 did not exist in Phase 5's original control list — the isolation requirement lived only in
this ADR, with no control ID and therefore no test. The bidirectional coverage check in
`docs/research/verify_threat_coverage.py` surfaced the gap, and the control was added.

## Revisit when
surya relaxes its pillow cap (then it may share the worker environment — still never the API), or we drop the surya baseline entirely.
