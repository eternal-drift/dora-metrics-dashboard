"""Deterministic metric snapshots for a repo, shared by the Advisor's tools
and directly unit-testable without touching the LLM.

Each function here loads data via dora.storage.db and returns a small
JSON-serializable dict -- not a raw DataFrame -- because these are the
shapes handed to Claude as tool results.
"""
from __future__ import annotations

import pandas as pd

from dora.metrics.dora import change_failure_rate, deployment_frequency, lead_time_for_changes, pr_cycle_time
from dora.metrics.flow import mttr, space_indicators, throughput, wip
from dora.storage import db


def _load(repo: str):
    with db.connect() as conn:
        prs = db.load_pull_requests(conn, repo)
        releases = db.load_releases(conn, repo)
        deployments = db.load_deployments(conn, repo)
        issues = db.load_issues(conn, repo)
    return prs, releases, deployments, issues


def _trend(df: pd.DataFrame, value_col: str, freq_label: str = "period") -> dict:
    """Compare the trailing period to the one before it. Returns {} if
    there isn't enough history to compare."""
    if df is None or df.empty or len(df) < 2:
        return {}
    sorted_df = df.sort_values(freq_label)
    latest = float(sorted_df.iloc[-1][value_col])
    prior = float(sorted_df.iloc[-2][value_col])
    delta_pct = None if prior == 0 else round((latest - prior) / prior * 100, 1)
    return {"latest": round(latest, 2), "prior": round(prior, 2), "change_pct": delta_pct}


def repos() -> list[str]:
    with db.connect() as conn:
        return db.known_repos(conn)


def pr_cycle_time_snapshot(repo: str, freq: str = "W") -> dict:
    prs, *_ = _load(repo)
    if prs.empty:
        return {"error": f"No PR data ingested for {repo}."}
    detail = pr_cycle_time(prs)
    if detail.empty:
        return {"error": f"No merged PRs for {repo}."}
    weekly = (
        detail.set_index("merged_at_dt")["cycle_time_hours"]
        .resample(freq)
        .median()
        .reset_index()
        .rename(columns={"merged_at_dt": "period", "cycle_time_hours": "median_hours"})
    )
    return {
        "metric": "pr_cycle_time_hours",
        "overall_median_hours": round(float(detail["cycle_time_hours"].median()), 1),
        "trend": _trend(weekly, "median_hours"),
        "n_prs": int(len(detail)),
        "caveat": (
            "Median hours from PR open to merge. Doesn't distinguish waiting-on-review "
            "from waiting-on-CI from author being unavailable."
        ),
    }


def change_failure_rate_snapshot(repo: str) -> dict:
    prs, releases, _, _ = _load(repo)
    if releases.empty:
        return {"error": f"No releases for {repo}; change failure rate needs release data."}
    detail, rate = change_failure_rate(releases, prs)
    recent = detail.sort_values("published_at").tail(8)
    recent_rate = float(recent["is_failure"].mean()) if not recent.empty else None
    return {
        "metric": "change_failure_rate",
        "overall_rate_pct": round(rate * 100, 1),
        "recent_8_releases_rate_pct": None if recent_rate is None else round(recent_rate * 100, 1),
        "n_releases": int(len(detail)),
        "caveat": (
            "Heuristic: fraction of releases followed within a configurable window by a PR "
            "merge whose title matches a hotfix/revert/rollback/incident keyword. Not a "
            "ground-truth incident count -- can miss real failures fixed under an unrelated "
            "title, and can flag unrelated coincidental hotfixes."
        ),
    }


def deployment_frequency_snapshot(repo: str, freq: str = "W") -> dict:
    prs, releases, deployments, _ = _load(repo)
    events = releases if not releases.empty else deployments
    ts_col = "published_at" if not releases.empty else "created_at"
    if events.empty:
        return {"error": f"No releases or deployments for {repo}."}
    df = deployment_frequency(events, ts_col, freq=freq)
    return {
        "metric": "deployment_frequency",
        "per_period": df.tail(8).assign(period=lambda d: d["period"].astype(str)).to_dict(orient="records"),
        "trend": _trend(df, "deployments"),
        "caveat": "Count of releases (or deployments, as a fallback) per period.",
    }


def lead_time_snapshot(repo: str) -> dict:
    prs, releases, _, _ = _load(repo)
    if releases.empty:
        return {"error": f"No releases for {repo}; lead time needs release data."}
    detail = lead_time_for_changes(prs, releases)
    if detail.empty:
        return {"error": f"No merged PRs have shipped in a release yet for {repo}."}
    return {
        "metric": "lead_time_for_changes_hours",
        "median_hours": round(float(detail["lead_time_hours"].median()), 1),
        "n_prs": int(len(detail)),
        "caveat": (
            "Proxy: hours from a PR's merge to the next release published afterward. Reflects "
            "release cadence/batching as much as engineering speed."
        ),
    }


def mttr_snapshot(repo: str) -> dict:
    _, _, _, issues = _load(repo)
    detail, mean_hours = mttr(issues)
    if detail.empty:
        return {"error": f"No resolved incident issues for {repo}."}
    return {
        "metric": "mttr_hours",
        "mean_hours": round(mean_hours, 1),
        "n_incidents": int(len(detail)),
        "caveat": (
            "Mean hours from incident creation to resolution. Overstates true MTTR if "
            "incidents are filed after detection/triage already began."
        ),
    }


def wip_snapshot(repo: str, freq: str = "W") -> dict:
    _, _, _, issues = _load(repo)
    df = wip(issues, freq=freq)
    if df.empty:
        return {"error": f"No in-progress issue data for {repo}."}
    return {
        "metric": "wip",
        "latest": int(df.iloc[-1]["wip"]),
        "trend": _trend(df, "wip"),
        "caveat": "Point-in-time snapshot of started-but-unresolved issues, sampled at period end -- not a period average.",
    }


def throughput_snapshot(repo: str, freq: str = "M") -> dict:
    _, _, _, issues = _load(repo)
    df = throughput(issues, freq=freq)
    if df.empty:
        return {"error": f"No resolved issue data for {repo}."}
    return {
        "metric": "throughput",
        "latest_period_resolved": int(df.iloc[-1]["resolved"]),
        "trend": _trend(df, "resolved"),
        "caveat": "Count of issues resolved per period. Says nothing about size/value of the work.",
    }


def space_snapshot(repo: str, freq: str = "W") -> dict:
    prs, _, _, issues = _load(repo)
    result = space_indicators(prs, issues, freq=freq)
    out = {"metric": "space_indicators"}
    for dim in ("activity", "performance", "efficiency"):
        df = result[dim]
        out[dim] = None if df.empty else df.tail(4).to_dict(orient="records")
    out["satisfaction"] = None
    out["communication"] = None
    out["caveat"] = (
        "Satisfaction and Communication have no signal in this data source (no surveys, no "
        "chat/comment volume) and are intentionally None, not approximated."
    )
    return out


def full_health_snapshot(repo: str) -> dict:
    """Everything at once -- used for VP-summary-style questions."""
    return {
        "repo": repo,
        "pr_cycle_time": pr_cycle_time_snapshot(repo),
        "change_failure_rate": change_failure_rate_snapshot(repo),
        "deployment_frequency": deployment_frequency_snapshot(repo),
        "lead_time_for_changes": lead_time_snapshot(repo),
        "mttr": mttr_snapshot(repo),
        "wip": wip_snapshot(repo),
        "throughput": throughput_snapshot(repo),
        "space_indicators": space_snapshot(repo),
    }
