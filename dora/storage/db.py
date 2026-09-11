"""Minimal SQLite storage for ingested GitHub data.

Raw JSON payloads are kept alongside a handful of flattened columns used for
filtering/joins, so metric code can either use the columns or reparse the
JSON for anything not promoted to a column.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from dora.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS pull_requests (
    repo TEXT NOT NULL,
    number INTEGER NOT NULL,
    state TEXT,
    merged_at TEXT,
    created_at TEXT,
    closed_at TEXT,
    first_review_at TEXT,
    additions INTEGER,
    deletions INTEGER,
    raw JSON,
    PRIMARY KEY (repo, number)
);

CREATE TABLE IF NOT EXISTS releases (
    repo TEXT NOT NULL,
    id INTEGER NOT NULL,
    tag_name TEXT,
    published_at TEXT,
    raw JSON,
    PRIMARY KEY (repo, id)
);

CREATE TABLE IF NOT EXISTS deployments (
    repo TEXT NOT NULL,
    id INTEGER NOT NULL,
    environment TEXT,
    created_at TEXT,
    raw JSON,
    PRIMARY KEY (repo, id)
);
"""


@contextmanager
def connect(db_path: str | None = None):
    path = db_path or settings.db_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_pull_requests(conn: sqlite3.Connection, repo: str, prs: list[dict], reviews_by_number: dict[int, list[dict]] | None = None) -> None:
    reviews_by_number = reviews_by_number or {}
    rows = []
    for pr in prs:
        reviews = sorted(reviews_by_number.get(pr["number"], []), key=lambda r: r.get("submitted_at") or "")
        first_review_at = reviews[0]["submitted_at"] if reviews else pr.get("first_review_at")
        rows.append((
            repo, pr["number"], pr.get("state"), pr.get("merged_at"), pr.get("created_at"),
            pr.get("closed_at"), first_review_at, pr.get("additions"), pr.get("deletions"),
            json.dumps(pr),
        ))
    conn.executemany(
        """INSERT INTO pull_requests
           (repo, number, state, merged_at, created_at, closed_at, first_review_at, additions, deletions, raw)
           VALUES (?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(repo, number) DO UPDATE SET
             state=excluded.state, merged_at=excluded.merged_at, created_at=excluded.created_at,
             closed_at=excluded.closed_at, first_review_at=excluded.first_review_at,
             additions=excluded.additions, deletions=excluded.deletions, raw=excluded.raw""",
        rows,
    )


def upsert_releases(conn: sqlite3.Connection, repo: str, releases: list[dict]) -> None:
    rows = [(repo, r["id"], r.get("tag_name"), r.get("published_at"), json.dumps(r)) for r in releases]
    conn.executemany(
        """INSERT INTO releases (repo, id, tag_name, published_at, raw) VALUES (?,?,?,?,?)
           ON CONFLICT(repo, id) DO UPDATE SET tag_name=excluded.tag_name,
             published_at=excluded.published_at, raw=excluded.raw""",
        rows,
    )


def upsert_deployments(conn: sqlite3.Connection, repo: str, deployments: list[dict]) -> None:
    rows = [(repo, d["id"], d.get("environment"), d.get("created_at"), json.dumps(d)) for d in deployments]
    conn.executemany(
        """INSERT INTO deployments (repo, id, environment, created_at, raw) VALUES (?,?,?,?,?)
           ON CONFLICT(repo, id) DO UPDATE SET environment=excluded.environment,
             created_at=excluded.created_at, raw=excluded.raw""",
        rows,
    )


def load_pull_requests(conn: sqlite3.Connection, repo: str):
    import pandas as pd
    return pd.read_sql_query("SELECT * FROM pull_requests WHERE repo = ?", conn, params=(repo,))


def load_releases(conn: sqlite3.Connection, repo: str):
    import pandas as pd
    return pd.read_sql_query("SELECT * FROM releases WHERE repo = ?", conn, params=(repo,))


def load_deployments(conn: sqlite3.Connection, repo: str):
    import pandas as pd
    return pd.read_sql_query("SELECT * FROM deployments WHERE repo = ?", conn, params=(repo,))


def known_repos(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute(
        "SELECT DISTINCT repo FROM pull_requests UNION SELECT DISTINCT repo FROM releases UNION SELECT DISTINCT repo FROM deployments"
    )
    return [row[0] for row in cur.fetchall()]
