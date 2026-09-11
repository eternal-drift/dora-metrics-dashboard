"""Tests for the Metrics API (dora/api/main.py). Uses FastAPI's TestClient
directly against seeded data -- no server process, no network.
"""
import sys

sys.path.insert(0, ".")

from fastapi.testclient import TestClient

from dora.api.main import app

client = TestClient(app)


def _seed(tmp_path):
    db_path = str(tmp_path / "api_test.db")

    import dora.config as config_module
    config_module.settings.db_path = db_path

    from scripts import seed_demo_data
    seed_demo_data.REPO = "acme/widgets"
    seed_demo_data.main()
    return db_path


def test_list_repos(tmp_path):
    _seed(tmp_path)
    r = client.get("/repos")
    assert r.status_code == 200
    assert "acme/widgets" in r.json()["repos"]


def test_pr_cycle_time_endpoint(tmp_path):
    _seed(tmp_path)
    r = client.get("/repos/acme/widgets/metrics/pr-cycle-time")
    assert r.status_code == 200
    body = r.json()
    assert body["overall_median_hours"] > 0
    assert "caveat" in body


def test_unknown_repo_returns_404(tmp_path):
    _seed(tmp_path)
    r = client.get("/repos/nope/nonexistent/metrics/pr-cycle-time")
    assert r.status_code == 404


def test_health_snapshot_covers_every_metric(tmp_path):
    _seed(tmp_path)
    r = client.get("/repos/acme/widgets/health")
    assert r.status_code == 200
    body = r.json()
    for key in (
        "pr_cycle_time", "change_failure_rate", "deployment_frequency",
        "lead_time_for_changes", "mttr", "wip", "throughput", "space_indicators",
    ):
        assert key in body
