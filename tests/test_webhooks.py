import hashlib
import hmac
import json

from dora.webhooks import normalize_event, verify_signature


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_verify_signature_accepts_correct_hmac():
    body = b'{"hello": "world"}'
    secret = "s3cr3t"
    assert verify_signature(body, _sign(body, secret), secret) is True


def test_verify_signature_rejects_wrong_secret():
    body = b'{"hello": "world"}'
    assert verify_signature(body, _sign(body, "right"), "wrong") is False


def test_verify_signature_rejects_missing_header():
    assert verify_signature(b"{}", None, "s3cr3t") is False


def test_verify_signature_rejects_malformed_header():
    assert verify_signature(b"{}", "not-sha256-prefixed", "s3cr3t") is False


def test_normalize_pull_request_event():
    payload = {
        "repository": {"full_name": "acme/widgets"},
        "pull_request": {"number": 42, "state": "closed", "merged_at": "2024-01-01T00:00:00Z"},
    }
    event = normalize_event("pull_request", payload)
    assert event == {
        "repo": "acme/widgets",
        "kind": "pull_request",
        "data": payload["pull_request"],
    }


def test_normalize_release_published_event():
    payload = {
        "repository": {"full_name": "acme/widgets"},
        "action": "published",
        "release": {"id": 1, "tag_name": "v1.0.0", "published_at": "2024-01-01T00:00:00Z"},
    }
    event = normalize_event("release", payload)
    assert event["kind"] == "release"
    assert event["data"]["tag_name"] == "v1.0.0"


def test_normalize_release_ignores_non_published_actions():
    payload = {
        "repository": {"full_name": "acme/widgets"},
        "action": "created",
        "release": {"id": 1, "tag_name": "v1.0.0-draft"},
    }
    assert normalize_event("release", payload) is None


def test_normalize_pull_request_review_submitted():
    payload = {
        "repository": {"full_name": "acme/widgets"},
        "action": "submitted",
        "pull_request": {"number": 7},
        "review": {"submitted_at": "2024-01-02T00:00:00Z"},
    }
    event = normalize_event("pull_request_review", payload)
    assert event == {
        "repo": "acme/widgets",
        "kind": "pull_request_review",
        "data": {"number": 7, "submitted_at": "2024-01-02T00:00:00Z"},
    }


def test_normalize_deployment_status_event():
    payload = {
        "repository": {"full_name": "acme/widgets"},
        "deployment": {"id": 99, "environment": "production", "created_at": "2024-01-03T00:00:00Z"},
    }
    event = normalize_event("deployment_status", payload)
    assert event["kind"] == "deployment"
    assert event["data"]["id"] == 99


def test_normalize_unknown_event_type_returns_none():
    payload = {"repository": {"full_name": "acme/widgets"}}
    assert normalize_event("issues", payload) is None


def test_normalize_missing_repository_returns_none():
    assert normalize_event("pull_request", {"pull_request": {}}) is None
