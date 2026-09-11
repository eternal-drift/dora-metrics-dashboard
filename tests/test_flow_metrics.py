import pandas as pd
import pytest

from dora.metrics.flow import mttr, space_indicators, throughput, wip


def _issue(key, issue_type, created_at, started_at=None, resolved_at=None):
    return {
        "repo": "acme/widgets", "key": key, "issue_type": issue_type, "status": "done",
        "assignee": "amir", "priority": "P2",
        "created_at": created_at, "started_at": started_at, "resolved_at": resolved_at,
    }


def test_mttr_computes_hours_for_resolved_incidents_only():
    issues = pd.DataFrame([
        _issue("ENG-1", "incident", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", "2024-01-01T04:00:00Z"),
        _issue("ENG-2", "incident", "2024-01-02T00:00:00Z", "2024-01-02T00:00:00Z", None),  # unresolved, excluded
        _issue("ENG-3", "story", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", "2024-01-01T02:00:00Z"),  # not incident
    ])
    detail, overall = mttr(issues)
    assert list(detail["key"]) == ["ENG-1"]
    assert overall == pytest.approx(4.0)


def test_mttr_empty_input_returns_nan():
    detail, overall = mttr(pd.DataFrame())
    assert detail.empty
    assert overall != overall  # NaN


def test_wip_counts_open_issues_at_period_end():
    issues = pd.DataFrame([
        _issue("ENG-1", "story", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", "2024-01-20T00:00:00Z"),
        _issue("ENG-2", "story", "2024-01-08T00:00:00Z", "2024-01-08T00:00:00Z", None),
    ])
    result = wip(issues, freq="W")
    first_week_end = result.iloc[0]["wip"]
    assert first_week_end == 1  # only ENG-1 started


def test_wip_empty_input():
    result = wip(pd.DataFrame())
    assert result.empty


def test_throughput_counts_resolved_per_period():
    issues = pd.DataFrame([
        _issue("ENG-1", "story", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"),
        _issue("ENG-2", "story", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", "2024-01-03T00:00:00Z"),
        _issue("ENG-3", "story", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", None),  # unresolved, excluded
    ])
    result = throughput(issues, freq="W")
    assert result["resolved"].sum() == 2


def test_space_indicators_omits_satisfaction_and_communication():
    space = space_indicators(pd.DataFrame(), pd.DataFrame())
    assert space["satisfaction"] is None
    assert space["communication"] is None
    assert space["activity"].empty
    assert space["performance"].empty
    assert space["efficiency"].empty
