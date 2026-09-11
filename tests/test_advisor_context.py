"""Tests for dora.advisor.context -- the deterministic (LLM-free) snapshot
layer the Advisor's tools call into. No API key or network access needed;
this is exactly why context.py is kept separate from tools.py/advisor.py.
"""
import sys

sys.path.insert(0, ".")

from dora.advisor import context
from dora.storage import db


def _seed(tmp_path):
    db_path = str(tmp_path / "advisor_test.db")

    import dora.config as config_module
    config_module.settings.db_path = db_path

    from scripts import seed_demo_data
    seed_demo_data.REPO = "acme/widgets"
    seed_demo_data.main()
    return db_path


def test_repos_lists_seeded_repo(tmp_path):
    _seed(tmp_path)
    assert "acme/widgets" in context.repos()


def test_pr_cycle_time_snapshot_has_trend_and_caveat(tmp_path):
    _seed(tmp_path)
    snap = context.pr_cycle_time_snapshot("acme/widgets")
    assert "error" not in snap
    assert snap["overall_median_hours"] > 0
    assert snap["n_prs"] > 0
    assert "caveat" in snap and snap["caveat"]


def test_pr_cycle_time_improves_over_the_seeded_window(tmp_path):
    _seed(tmp_path)
    snap = context.pr_cycle_time_snapshot("acme/widgets")
    # The seed generator trends cycle time 48h -> 18h; overall median should
    # land well below the starting point, not just be "a positive number".
    assert snap["overall_median_hours"] < 40


def test_unknown_repo_returns_error_not_exception(tmp_path):
    _seed(tmp_path)
    snap = context.pr_cycle_time_snapshot("nope/nonexistent")
    assert "error" in snap


def test_change_failure_rate_snapshot(tmp_path):
    _seed(tmp_path)
    snap = context.change_failure_rate_snapshot("acme/widgets")
    assert "error" not in snap
    assert 0 <= snap["overall_rate_pct"] <= 100
    assert "caveat" in snap


def test_full_health_snapshot_covers_every_metric(tmp_path):
    _seed(tmp_path)
    snap = context.full_health_snapshot("acme/widgets")
    for key in (
        "pr_cycle_time", "change_failure_rate", "deployment_frequency",
        "lead_time_for_changes", "mttr", "wip", "throughput", "space_indicators",
    ):
        assert key in snap
