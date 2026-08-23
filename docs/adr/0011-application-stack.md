# ADR-0011: FastAPI + Postgres + Redis/arq + Next.js, inference always async

**Status:** Accepted · **Date:** 2026-08-23 · **Driver:** Senior backend engineer

## Context
The brief fixes the broad stack (FastAPI, PostgreSQL, background queue, Next.js, Docker Compose) and one hard rule: **inference must never block an HTTP request.**

That rule plus ADR-0007's container split means the queue is not a convenience — it is the only channel between the API and the ML stacks. It is load-bearing and needs a deliberate choice.

**[V]** Verified co-installable on Python 3.11: `fastapi 0.141.1`, `sqlalchemy 2.0.52`, `alembic 1.19.1`, `psycopg 3.3.4`, `arq 0.28.0`, `redis 8.1.0`, `argon2-cffi 25.1.0`, `pydantic 2.13.4` — resolution A, 103 packages, `pillow==12.3.0`, clean.

## Decision
- **API:** FastAPI on Python 3.11, `psycopg` v3 with async SQLAlchemy 2.x.
- **DB:** PostgreSQL 16 (matches the local `psql 16.13`), Alembic migrations from the **first** commit.
- **Queue: `arq`** (Redis-backed, asyncio-native).
- **Frontend:** Next.js, static-hostable.
- **Local dev:** one `docker compose up` brings up api, worker(s), postgres, redis, frontend.
- **Request flow:** upload → validate + re-encode → persist → enqueue job → return `202` with a job id. The client polls or subscribes. **No inference call ever happens inside a request handler.**

**Why `arq` over Celery.** Celery is the default answer and it is a reasonable one, but: our API is asyncio end to end, and Celery's async story is still awkward — it wants a prefork worker model and a sync entrypoint. `arq` is asyncio-native, dramatically smaller, and uses Redis which we want anyway for rate limiting (Phase 5). The tradeoff is a smaller ecosystem and fewer operational batteries; for a job graph this simple (one job type, one queue, retries, timeouts) that ecosystem is not worth the impedance mismatch. If the job graph grows complex — chords, chains, multi-broker routing — Celery becomes the right call and the interface is narrow enough to swap.

## Alternatives rejected
| Alternative | Why rejected |
|---|---|
| Celery | Async impedance mismatch with an asyncio API; much heavier. Genuinely close — revisit if the job graph outgrows `arq`. |
| Postgres-backed queue (SKIP LOCKED) | One less service, and tempting. Rejected because we need Redis for rate limiting anyway, so it saves nothing and puts queue load on the same DB holding user documents. |
| Synchronous inference with a long timeout | Violates the explicit rule. Ties up workers, gives users no progress, and makes GPU cost a DoS vector (T-06). |
| RabbitMQ / SQS | Operationally heavier than this project needs; SQS also adds a cloud dependency to local dev. |

## Constraint discovered during implementation

**[V]** `arq 0.28.0` requires `redis[hiredis]>=4.2.0,<6`, so it caps us at redis-py
**5.3.1** while 8.1.0 is current. This was found by running the resolver, not by reading
the README.

It is recorded rather than waved through, but it is **not** the pillow situation:
`pip-audit` reports **no known vulnerabilities** in redis 5.3.1, so this is dependency
staleness, not an exposed defect. The asyncio argument still wins.

**Revisit trigger:** if a CVE lands in redis-py 5.x and arq has not moved its cap, that
converts staleness into exposure and we switch to Celery, which accepts redis 8.1.0
**[V]**.

## Consequences
- **Positive:** GPU work cannot stall the API; the API stays small and free of ML dependencies (ADR-0007).
- **Positive:** Redis serves double duty as queue broker and rate-limit store.
- **Negative:** async job status is a UX surface — the frontend needs real progress/failure states, not a spinner.
- **Negative:** at-least-once delivery means jobs must be **idempotent**. Non-negotiable, and it must be tested.
- **Negative:** a smaller ecosystem than Celery; we may write tooling Celery would have given us.
- **Negative:** pinned to redis-py 5.x by arq (see above).
- **Implementation note:** the arq pool is bound to the event loop that created it, so
  `adai.queue.get_pool` tracks the running loop and rebuilds when it changes. Under
  uvicorn there is only one loop; without this, anything creating a second loop hits a
  cross-loop RuntimeError. Found by the integration tests.

## Revisit when
The job graph needs chaining/fan-out beyond `arq`'s model, or operational gaps make Celery's ecosystem worth the mismatch.
