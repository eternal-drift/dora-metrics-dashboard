"""Storage for ingested GitHub/Jira-shaped data.

Backed by SQLite by default; set DATABASE_URL (e.g. postgresql://user:pass@host/dora)
to use Postgres instead -- see docs/adr/0001-storage-sqlite-then-postgres.md. Both
dialects go through the same SQLAlchemy Core code path below: the SQL here (including
the ON CONFLICT ... DO UPDATE upserts) is written to be valid on both SQLite (3.24+)
and Postgres without a dialect branch.

Raw JSON payloads are kept alongside a handful of flattened columns used for
filtering/joins, so metric code can either use the columns or reparse the
JSON for anything not promoted to a column.
"""
from __future__ import annotations

import json
from contextlib import contextmanager

import sqlalchemy as sa
from sqlalchemy.engine import Engine

from dora.config import settings

SCHEMA_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS pull_requests (
        repo TEXT NOT NULL,
        number INTEGER NOT NULL,
        state TEXT,
        merged_at TEXT,
        created_at TEXT,
        closed_at TEXT,
        first_review_at TEXT,
        additions INTEGER,
        deletions INTEGER,
        raw TEXT,
        PRIMARY KEY (repo, number)
    )""",
    """CREATE TABLE IF NOT EXISTS releases (
        repo TEXT NOT NULL,
        id INTEGER NOT NULL,
        tag_name TEXT,
        published_at TEXT,
        raw TEXT,
        PRIMARY KEY (repo, id)
    )""",
    """CREATE TABLE IF NOT EXISTS deployments (
        repo TEXT NOT NULL,
        id INTEGER NOT NULL,
        environment TEXT,
        created_at TEXT,
        raw TEXT,
        PRIMARY KEY (repo, id)
    )""",
    # Jira-style issue tracking events. There is no live Jira ingestion here
    # (see scripts/seed_demo_data.py) -- rows come from synthetic data generated
    # to exercise WIP/throughput/MTTR, which need work-item state transitions
    # that the GitHub PR/release data doesn't carry.
    """CREATE TABLE IF NOT EXISTS issues (
        repo TEXT NOT NULL,
        key TEXT NOT NULL,
        issue_type TEXT,
        status TEXT,
        assignee TEXT,
        priority TEXT,
        created_at TEXT,
        started_at TEXT,
        resolved_at TEXT,
        raw TEXT,
        PRIMARY KEY (repo, key)
    )""",
]

_engines: dict[str, Engine] = {}


def _engine_url(db_path: str | None) -> str:
    if settings.database_url:
        return settings.database_url
    return f"sqlite:///{db_path or settings.db_path}"


def _get_engine(db_path: str | None = None) -> Engine:
    url = _engine_url(db_path)
    if url not in _engines:
        _engines[url] = sa.create_engine(url, future=True)
    return _engines[url]


@contextmanager
def connect(db_path: str | None = None):
    conn = _get_engine(db_path).connect()
    trans = conn.begin()
    try:
        for stmt in SCHEMA_STATEMENTS:
            conn.execute(sa.text(stmt))
        yield conn
        trans.commit()
    except Exception:
        trans.rollback()
        raise
    finally:
        conn.close()


def upsert_pull_requests(conn, repo: str, prs: list[dict], reviews_by_number: dict[int, list[dict]] | None = None) -> None:
    reviews_by_number = reviews_by_number or {}
    rows = []
    for pr in prs:
        reviews = sorted(reviews_by_number.get(pr["number"], []), key=lambda r: r.get("submitted_at") or "")
        first_review_at = reviews[0]["submitted_at"] if reviews else pr.get("first_review_at")
        rows.append({
            "repo": repo, "number": pr["number"], "state": pr.get("state"),
            "merged_at": pr.get("merged_at"), "created_at": pr.get("created_at"),
            "closed_at": pr.get("closed_at"), "first_review_at": first_review_at,
            "additions": pr.get("additions"), "deletions": pr.get("deletions"),
            "raw": json.dumps(pr),
        })
    if not rows:
        return
    conn.execute(sa.text("""
        INSERT INTO pull_requests
          (repo, number, state, merged_at, created_at, closed_at, first_review_at, additions, deletions, raw)
        VALUES (:repo, :number, :state, :merged_at, :created_at, :closed_at, :first_review_at, :additions, :deletions, :raw)
        ON CONFLICT (repo, number) DO UPDATE SET
          state=excluded.state, merged_at=excluded.merged_at, created_at=excluded.created_at,
          closed_at=excluded.closed_at, first_review_at=excluded.first_review_at,
          additions=excluded.additions, deletions=excluded.deletions, raw=excluded.raw
    """), rows)


def upsert_releases(conn, repo: str, releases: list[dict]) -> None:
    rows = [
        {"repo": repo, "id": r["id"], "tag_name": r.get("tag_name"),
         "published_at": r.get("published_at"), "raw": json.dumps(r)}
        for r in releases
    ]
    if not rows:
        return
    conn.execute(sa.text("""
        INSERT INTO releases (repo, id, tag_name, published_at, raw)
        VALUES (:repo, :id, :tag_name, :published_at, :raw)
        ON CONFLICT (repo, id) DO UPDATE SET
          tag_name=excluded.tag_name, published_at=excluded.published_at, raw=excluded.raw
    """), rows)


def upsert_deployments(conn, repo: str, deployments: list[dict]) -> None:
    rows = [
        {"repo": repo, "id": d["id"], "environment": d.get("environment"),
         "created_at": d.get("created_at"), "raw": json.dumps(d)}
        for d in deployments
    ]
    if not rows:
        return
    conn.execute(sa.text("""
        INSERT INTO deployments (repo, id, environment, created_at, raw)
        VALUES (:repo, :id, :environment, :created_at, :raw)
        ON CONFLICT (repo, id) DO UPDATE SET
          environment=excluded.environment, created_at=excluded.created_at, raw=excluded.raw
    """), rows)


def upsert_issues(conn, repo: str, issues: list[dict]) -> None:
    rows = [
        {
            "repo": repo, "key": i["key"], "issue_type": i.get("issue_type"),
            "status": i.get("status"), "assignee": i.get("assignee"), "priority": i.get("priority"),
            "created_at": i.get("created_at"), "started_at": i.get("started_at"),
            "resolved_at": i.get("resolved_at"), "raw": json.dumps(i),
        }
        for i in issues
    ]
    if not rows:
        return
    conn.execute(sa.text("""
        INSERT INTO issues
          (repo, key, issue_type, status, assignee, priority, created_at, started_at, resolved_at, raw)
        VALUES (:repo, :key, :issue_type, :status, :assignee, :priority, :created_at, :started_at, :resolved_at, :raw)
        ON CONFLICT (repo, key) DO UPDATE SET
          issue_type=excluded.issue_type, status=excluded.status, assignee=excluded.assignee,
          priority=excluded.priority, created_at=excluded.created_at, started_at=excluded.started_at,
          resolved_at=excluded.resolved_at, raw=excluded.raw
    """), rows)


def load_pull_requests(conn, repo: str):
    import pandas as pd
    return pd.read_sql_query(sa.text("SELECT * FROM pull_requests WHERE repo = :repo"), conn, params={"repo": repo})


def load_releases(conn, repo: str):
    import pandas as pd
    return pd.read_sql_query(sa.text("SELECT * FROM releases WHERE repo = :repo"), conn, params={"repo": repo})


def load_deployments(conn, repo: str):
    import pandas as pd
    return pd.read_sql_query(sa.text("SELECT * FROM deployments WHERE repo = :repo"), conn, params={"repo": repo})


def load_issues(conn, repo: str):
    import pandas as pd
    return pd.read_sql_query(sa.text("SELECT * FROM issues WHERE repo = :repo"), conn, params={"repo": repo})


def known_repos(conn) -> list[str]:
    result = conn.execute(sa.text(
        "SELECT DISTINCT repo FROM pull_requests UNION SELECT DISTINCT repo FROM releases "
        "UNION SELECT DISTINCT repo FROM deployments UNION SELECT DISTINCT repo FROM issues"
    ))
    return [row[0] for row in result.fetchall()]
