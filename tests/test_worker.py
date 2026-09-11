"""End-to-end: webhook receipt -> queue -> worker -> storage. Uses the
in-memory queue backend (QUEUE_URL unset) so no Redis is required.

Isolation is by unique repo name, not by db file path -- see
tests/test_advisor_context.py for why (Postgres/DATABASE_URL shares one
database across tests regardless of tmp_path).
"""
import sys
import uuid

sys.path.insert(0, ".")

from fastapi.testclient import TestClient

import dora.config as config_module
from dora.api.main import app
from dora.queue import reset_queue
from dora.storage import db
from dora.worker import run_worker

client = TestClient(app)


def _use_tmp_db(tmp_path, name="worker_test.db"):
    config_module.settings.db_path = str(tmp_path / name)
    config_module.settings.queue_url = ""  # in-memory queue backend
    config_module.settings.github_webhook_secret = ""
    reset_queue()
    return f"acme/widgets-{uuid.uuid4().hex[:8]}"


def test_pull_request_webhook_flows_through_to_storage(tmp_path):
    repo = _use_tmp_db(tmp_path)
    payload = {
        "repository": {"full_name": repo},
        "action": "closed",
        "pull_request": {
            "number": 101, "state": "closed", "merged_at": "2024-01-01T12:00:00Z",
            "created_at": "2024-01-01T00:00:00Z", "closed_at": "2024-01-01T12:00:00Z",
            "additions": 10, "deletions": 2,
        },
    }
    r = client.post("/webhooks/github", json=payload, headers={"X-GitHub-Event": "pull_request"})
    assert r.status_code == 200
    assert r.json()["status"] == "queued"

    processed = run_worker(max_events=1)
    assert processed == 1

    with db.connect() as conn:
        prs = db.load_pull_requests(conn, repo)
    assert len(prs) == 1
    assert prs.iloc[0]["number"] == 101
    assert prs.iloc[0]["merged_at"] == "2024-01-01T12:00:00Z"


def test_release_webhook_flows_through_to_storage(tmp_path):
    repo = _use_tmp_db(tmp_path)
    payload = {
        "repository": {"full_name": repo},
        "action": "published",
        "release": {"id": 5, "tag_name": "v1.2.3", "published_at": "2024-02-01T00:00:00Z"},
    }
    client.post("/webhooks/github", json=payload, headers={"X-GitHub-Event": "release"})
    run_worker(max_events=1)

    with db.connect() as conn:
        releases = db.load_releases(conn, repo)
    assert len(releases) == 1
    assert releases.iloc[0]["tag_name"] == "v1.2.3"


def test_pull_request_review_updates_first_review_at_after_pr_exists(tmp_path):
    repo = _use_tmp_db(tmp_path)
    pr_payload = {
        "repository": {"full_name": repo},
        "pull_request": {
            "number": 202, "state": "open", "merged_at": None,
            "created_at": "2024-01-01T00:00:00Z", "closed_at": None,
            "additions": 1, "deletions": 1,
        },
    }
    client.post("/webhooks/github", json=pr_payload, headers={"X-GitHub-Event": "pull_request"})
    run_worker(max_events=1)

    review_payload = {
        "repository": {"full_name": repo},
        "action": "submitted",
        "pull_request": {"number": 202},
        "review": {"submitted_at": "2024-01-01T04:00:00Z"},
    }
    client.post("/webhooks/github", json=review_payload, headers={"X-GitHub-Event": "pull_request_review"})
    run_worker(max_events=1)

    with db.connect() as conn:
        prs = db.load_pull_requests(conn, repo)
    assert prs.iloc[0]["first_review_at"] == "2024-01-01T04:00:00Z"


def test_unsigned_webhook_rejected_when_secret_configured(tmp_path):
    repo = _use_tmp_db(tmp_path)
    config_module.settings.github_webhook_secret = "test-secret"
    try:
        payload = {"repository": {"full_name": repo}, "pull_request": {"number": 1}}
        r = client.post("/webhooks/github", json=payload, headers={"X-GitHub-Event": "pull_request"})
        assert r.status_code == 401
    finally:
        config_module.settings.github_webhook_secret = ""


def test_unknown_event_type_is_ignored_not_errored(tmp_path):
    repo = _use_tmp_db(tmp_path)
    payload = {"repository": {"full_name": repo}, "action": "opened"}
    r = client.post("/webhooks/github", json=payload, headers={"X-GitHub-Event": "issues"})
    assert r.status_code == 200
    assert r.json()["status"] == "ignored"
