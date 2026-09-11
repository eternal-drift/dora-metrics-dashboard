"""WIP, throughput, MTTR, and SPACE-inspired indicators computed from
Jira-style issue events (dora.storage.db "issues" table) plus GitHub PR data.

These sit alongside the four DORA metrics in dora/metrics/dora.py. As with
lead time and change failure rate there, some of these have no ground-truth
signal available and use documented proxies instead:

  * MTTR: mean hours from an incident issue's creation to its resolution.
    Requires issues of issue_type "incident" with created_at/resolved_at set.
    There's no separate "detection time" signal, so creation is treated as
    the start of the outage clock -- this overstates MTTR if incidents are
    filed after detection/triage has already begun.
  * WIP: point-in-time count of issues that have started but not resolved,
    sampled at the end of each period. This is a snapshot, not an average
    over the period, so short-lived spikes between samples are invisible.
  * Throughput: count of issues resolved per period. Unlike deployment
    frequency this counts completed work items, not ships.
  * SPACE indicators: SPACE (Satisfaction, Performance, Activity,
    Communication, Efficiency) is survey- and sentiment-driven in its
    original form. Only Activity, Efficiency, and Performance have a
    reasonable proxy in PR/issue metadata; Satisfaction and Communication
    have no signal in this data source and are returned as None rather than
    faked from unrelated numbers.
"""
from __future__ import annotations

import pandas as pd

_HOURS = pd.Timedelta(hours=1)


def _to_utc(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce")


def mttr(issues: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """Mean time to restore: created_at -> resolved_at for incident issues.

    Returns (per-incident detail, overall mean MTTR in hours). Issues without
    issue_type == "incident" or without a resolved_at are excluded.
    """
    cols = ["repo", "key", "created_at", "resolved_at", "mttr_hours"]
    if issues.empty:
        return pd.DataFrame(columns=cols), float("nan")
    incidents = issues[(issues["issue_type"] == "incident") & issues["resolved_at"].notna()].copy()
    if incidents.empty:
        return pd.DataFrame(columns=cols), float("nan")
    created = _to_utc(incidents["created_at"])
    resolved = _to_utc(incidents["resolved_at"])
    incidents["mttr_hours"] = (resolved - created) / _HOURS
    detail = incidents[["repo", "key", "created_at", "resolved_at", "mttr_hours"]]
    return detail, float(detail["mttr_hours"].mean())


def wip(issues: pd.DataFrame, freq: str = "W") -> pd.DataFrame:
    """Point-in-time WIP: issues started but not yet resolved, sampled at
    the end of each period between the earliest start and latest activity.
    """
    if issues.empty:
        return pd.DataFrame(columns=["period", "wip"])
    df = issues.copy()
    df["started_at_dt"] = _to_utc(df["started_at"])
    df["resolved_at_dt"] = _to_utc(df["resolved_at"])
    started = df.dropna(subset=["started_at_dt"])
    if started.empty:
        return pd.DataFrame(columns=["period", "wip"])

    horizon_end = pd.concat([started["resolved_at_dt"], started["started_at_dt"]]).max()
    periods = pd.period_range(
        start=started["started_at_dt"].min().tz_localize(None),
        end=horizon_end.tz_localize(None),
        freq=freq,
    )
    rows = []
    for period in periods:
        as_of = period.to_timestamp(how="end").tz_localize("UTC")
        open_count = (
            (started["started_at_dt"] <= as_of)
            & (started["resolved_at_dt"].isna() | (started["resolved_at_dt"] > as_of))
        ).sum()
        rows.append({"period": period.to_timestamp(), "wip": int(open_count)})
    return pd.DataFrame(rows)


def throughput(issues: pd.DataFrame, freq: str = "W") -> pd.DataFrame:
    """Count of issues resolved per period."""
    if issues.empty:
        return pd.DataFrame(columns=["period", "resolved"])
    resolved = _to_utc(issues["resolved_at"]).dropna().dt.tz_localize(None)
    if resolved.empty:
        return pd.DataFrame(columns=["period", "resolved"])
    counts = resolved.dt.to_period(freq).value_counts().sort_index()
    out = counts.rename_axis("period").reset_index(name="resolved")
    out["period"] = out["period"].dt.to_timestamp()
    return out


def space_indicators(prs: pd.DataFrame, issues: pd.DataFrame, freq: str = "W") -> dict:
    """SPACE-inspired indicators, per period, from PR and issue data.

    Satisfaction and Communication have no signal in this data source (no
    surveys, no chat/comment volume ingested) and are returned as None with
    a caveat rather than approximated from unrelated numbers.
    """
    activity = pd.DataFrame(columns=["period", "prs_opened"])
    if not prs.empty:
        created = _to_utc(prs["created_at"]).dropna().dt.tz_localize(None)
        if not created.empty:
            counts = created.dt.to_period(freq).value_counts().sort_index()
            activity = counts.rename_axis("period").reset_index(name="prs_opened")
            activity["period"] = activity["period"].dt.to_timestamp()

    performance = throughput(issues, freq=freq)

    efficiency = pd.DataFrame(columns=["period", "median_cycle_time_hours"])
    if not prs.empty:
        merged = prs[prs["merged_at"].notna()].copy()
        if not merged.empty:
            created = _to_utc(merged["created_at"])
            merged_dt = _to_utc(merged["merged_at"])
            merged["cycle_time_hours"] = (merged_dt - created) / _HOURS
            merged["period_dt"] = merged_dt.dt.tz_localize(None)
            efficiency = (
                merged.set_index("period_dt")["cycle_time_hours"]
                .resample(freq)
                .median()
                .reset_index()
                .rename(columns={"period_dt": "period", "cycle_time_hours": "median_cycle_time_hours"})
            )

    return {
        "activity": activity,
        "performance": performance,
        "efficiency": efficiency,
        "satisfaction": None,
        "communication": None,
    }
