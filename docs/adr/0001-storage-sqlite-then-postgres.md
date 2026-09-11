# ADR 0001: SQLite now, Postgres before multi-team scale

## Status
Accepted

## Context
The system needs somewhere to persist ingested PRs, releases, deployments,
and issues so metrics can be recomputed without re-hitting the GitHub API.
At current scale (one demo repo, single-user local dashboard) the storage
layer is not the bottleneck — ingestion API calls and metric-computation
correctness are.

## Decision
Use SQLite (`dora/storage/db.py`, file-based, zero setup) for local
development, demos, and single-repo use. Move to PostgreSQL when any of the
following becomes true:

- more than one process needs to write concurrently (e.g. a scheduled
  ingestion job running alongside an interactive dashboard),
- the Metrics API (see [roadmap.md](../roadmap.md)) needs to serve multiple
  teams/repos with concurrent reads,
- data volume passes the point where SQLite's single-writer lock causes
  visible ingestion delays (rule of thumb: tens of repos, years of PR
  history).

## Consequences
- Zero-friction setup today: `pip install`, run, no database server to
  stand up. This matters for a portfolio project a reviewer might actually
  run.
- The `dora/storage/db.py` interface is written against a plain DB-API
  connection and pandas `read_sql`, not SQLite-specific syntax, so the
  migration is a connection-string and schema-migration-tool change, not a
  rewrite of ingestion or metrics code.
- We accept that concurrent-write correctness (e.g. two ingestion jobs
  racing) is untested until the Postgres migration — this is a known gap,
  not an oversight.

## Update (implemented)

The Postgres path is now implemented, not just planned: `dora/storage/db.py`
was rewritten against SQLAlchemy Core, and both dialects share one code
path, including the upserts — SQLite (3.24+) and Postgres both support the
same `INSERT ... ON CONFLICT (...) DO UPDATE SET col = excluded.col` syntax,
so no dialect branch was needed. SQLite via `dora.db` (a plain file) stays
the default; set `DATABASE_URL` (e.g.
`postgresql://user:pass@host:5432/dora`) to switch to Postgres — see
`docker-compose.yml` for a working example. Verified against both SQLite
and a real `postgres:16-alpine` container: the full test suite, the
seed script, and the Metrics API all pass unchanged against either backend
(CI runs both — see `.github/workflows/ci.yml`).
