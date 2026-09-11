import json

import pandas as pd
import pytest

from dora.metrics.dora import (
    change_failure_rate,
    deployment_frequency,
    lead_time_for_changes,
    pr_cycle_time,
)


def _pr(number, created_at, merged_at, first_review_at=None, title="add feature"):
    return {
        "repo": "acme/widgets",
        "number": number,
        "state": "closed",
        "created_at": created_at,
        "merged_at": merged_at,
        "closed_at": merged_at,
        "first_review_at": first_review_at,
        "additions": 10,
        "deletions": 2,
        "raw": json.dumps({"title": title}),
    }


def _release(id_, tag, published_at):
    return {"repo": "acme/widgets", "id": id_, "tag_name": tag, "published_at": published_at}


def test_pr_cycle_time_excludes_unmerged_and_computes_hours():
    prs = pd.DataFrame([
        _pr(1, "2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"),
        _pr(2, "2024-01-01T00:00:00Z", None),  # unmerged, must be excluded
    ])
    result = pr_cycle_time(prs)
    assert list(result["number"]) == [1]
    assert result.iloc[0]["cycle_time_hours"] == pytest.approx(24.0)


def test_pr_cycle_time_includes_time_to_first_review():
    prs = pd.DataFrame([_pr(1, "2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z", "2024-01-01T06:00:00Z")])
    result = pr_cycle_time(prs)
    assert result.iloc[0]["time_to_first_review_hours"] == pytest.approx(6.0)


def test_deployment_frequency_counts_per_week():
    releases = pd.DataFrame([
        _release(1, "v1", "2024-01-01T00:00:00Z"),
        _release(2, "v2", "2024-01-02T00:00:00Z"),
        _release(3, "v3", "2024-01-15T00:00:00Z"),
    ])
    result = deployment_frequency(releases, "published_at", freq="W")
    assert result["deployments"].sum() == 3
    assert len(result) == 2  # two distinct weeks


def test_deployment_frequency_empty_input():
    result = deployment_frequency(pd.DataFrame(), "published_at")
    assert result.empty


def test_lead_time_for_changes_maps_pr_to_next_release():
    prs = pd.DataFrame([_pr(1, "2024-01-01T00:00:00Z", "2024-01-01T12:00:00Z")])
    releases = pd.DataFrame([_release(1, "v1", "2024-01-02T00:00:00Z")])
    result = lead_time_for_changes(prs, releases)
    assert result.iloc[0]["lead_time_hours"] == pytest.approx(12.0)
    assert result.iloc[0]["shipped_in"] == "v1"


def test_lead_time_for_changes_excludes_prs_not_yet_shipped():
    prs = pd.DataFrame([_pr(1, "2024-01-05T00:00:00Z", "2024-01-05T12:00:00Z")])
    releases = pd.DataFrame([_release(1, "v1", "2024-01-01T00:00:00Z")])
    result = lead_time_for_changes(prs, releases)
    assert result.empty


def test_change_failure_rate_flags_release_followed_by_hotfix():
    releases = pd.DataFrame([_release(1, "v1", "2024-01-01T00:00:00Z")])
    prs = pd.DataFrame([_pr(1, "2024-01-01T01:00:00Z", "2024-01-01T02:00:00Z", title="hotfix: fix crash")])
    detail, rate = change_failure_rate(releases, prs, hotfix_window_hours=24)
    assert rate == 1.0
    assert bool(detail.iloc[0]["is_failure"]) is True


def test_change_failure_rate_ignores_hotfix_outside_window():
    releases = pd.DataFrame([_release(1, "v1", "2024-01-01T00:00:00Z")])
    prs = pd.DataFrame([_pr(1, "2024-01-05T00:00:00Z", "2024-01-05T01:00:00Z", title="hotfix: fix crash")])
    detail, rate = change_failure_rate(releases, prs, hotfix_window_hours=24)
    assert rate == 0.0


def test_change_failure_rate_no_releases_returns_zero():
    detail, rate = change_failure_rate(pd.DataFrame(), pd.DataFrame())
    assert rate == 0.0
    assert detail.empty
