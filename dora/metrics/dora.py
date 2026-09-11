"""DORA + PR flow metrics computed from ingested GitHub data.

All functions take pandas DataFrames (as produced by dora.storage.db) and
return either a per-item DataFrame (for drill-down) or a period-aggregated
DataFrame (for charting). Two metrics — lead time for changes and change
failure rate — have no first-class "this shipped to prod and it broke"
signal in the plain GitHub REST API, so they use documented proxies:

  * Lead time for changes: time from a PR's merge to the next release
    published afterwards (i.e. how long a merged change waited to ship).
    If a repo doesn't cut releases, this metric will be empty — deployments
    can be substituted via `--deployment-based` in the CLI.
  * Change failure rate: the fraction of releases followed within
    `hotfix_window_hours` by another PR merge whose title/labels match a
    hotfix/revert/rollback/incident keyword. This is a heuristic, not a
    measurement of production incidents.
"""
from __future__ import annotations

import pandas as pd

from dora.config import settings

_HOURS = pd.Timedelta(hours=1)


def _to_utc(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce")


def pr_cycle_time(prs: pd.DataFrame) -> pd.DataFrame:
    """Per-PR cycle time: open -> merge, and open -> first review, in hours.

    Only merged PRs are included (closed-without-merge PRs aren't "cycle
    time", they're abandoned work).
    """
    df = prs[prs["merged_at"].notna()].copy()
    created = _to_utc(df["created_at"])
    merged = _to_utc(df["merged_at"])
    first_review = _to_utc(df["first_review_at"])
    df["cycle_time_hours"] = (merged - created) / _HOURS
    df["time_to_first_review_hours"] = (first_review - created) / _HOURS
    df["merged_at_dt"] = merged
    return df[["repo", "number", "created_at", "merged_at", "cycle_time_hours", "time_to_first_review_hours", "merged_at_dt"]]


def deployment_frequency(events: pd.DataFrame, timestamp_col: str, freq: str = "W") -> pd.DataFrame:
    """Count of deploy-like events (releases or deployments) per period.

    `freq` is a pandas offset alias: "D" daily, "W" weekly, "M" monthly.
    """
    if events.empty:
        return pd.DataFrame(columns=["period", "deployments"])
    ts = _to_utc(events[timestamp_col]).dropna().dt.tz_localize(None)
    counts = ts.dt.to_period(freq).value_counts().sort_index()
    out = counts.rename_axis("period").reset_index(name="deployments")
    out["period"] = out["period"].dt.to_timestamp()
    return out


def lead_time_for_changes(prs: pd.DataFrame, releases: pd.DataFrame) -> pd.DataFrame:
    """Hours from each merged PR to the next release published after it.

    A PR merged after the last known release has no lead time yet (still
    "in flight") and is excluded.
    """
    if releases.empty:
        return pd.DataFrame(columns=["repo", "number", "merged_at", "shipped_in", "lead_time_hours"])
    merged = prs[prs["merged_at"].notna()].copy()
    merged["merged_at_dt"] = _to_utc(merged["merged_at"])
    rel = releases.copy()
    rel["published_at_dt"] = _to_utc(rel["published_at"])
    rel = rel.dropna(subset=["published_at_dt"]).sort_values("published_at_dt")

    rel_times = rel["published_at_dt"].to_numpy()
    rows = []
    for _, pr in merged.dropna(subset=["merged_at_dt"]).iterrows():
        idx = rel["published_at_dt"].searchsorted(pr["merged_at_dt"], side="left")
        if idx >= len(rel):
            continue  # not shipped yet
        ship = rel.iloc[idx]
        rows.append({
            "repo": pr["repo"],
            "number": pr["number"],
            "merged_at": pr["merged_at"],
            "shipped_in": ship["tag_name"],
            "lead_time_hours": (ship["published_at_dt"] - pr["merged_at_dt"]) / _HOURS,
        })
    return pd.DataFrame(rows)


def change_failure_rate(
    releases: pd.DataFrame,
    prs: pd.DataFrame,
    hotfix_window_hours: int | None = None,
    keywords: tuple[str, ...] | None = None,
) -> tuple[pd.DataFrame, float]:
    """Fraction of releases followed by a same-window "hotfix" PR merge.

    Returns (per-release detail, overall failure rate in [0, 1]).
    """
    hotfix_window_hours = hotfix_window_hours or settings.hotfix_window_hours
    keywords = keywords or settings.hotfix_label_keywords
    if releases.empty:
        return pd.DataFrame(columns=["tag_name", "published_at", "is_failure"]), 0.0

    rel = releases.copy()
    rel["published_at_dt"] = _to_utc(rel["published_at"])
    rel = rel.dropna(subset=["published_at_dt"]).sort_values("published_at_dt")

    merged = prs[prs["merged_at"].notna()].copy()
    merged["merged_at_dt"] = _to_utc(merged["merged_at"])
    titles = merged["raw"].apply(lambda r: _pr_title(r))
    is_hotfix_pr = titles.str.lower().str.contains("|".join(keywords), na=False)
    hotfix_times = merged.loc[is_hotfix_pr, "merged_at_dt"].dropna().sort_values()

    window = pd.Timedelta(hours=hotfix_window_hours)
    rows = []
    for _, r in rel.iterrows():
        in_window = ((hotfix_times >= r["published_at_dt"]) & (hotfix_times <= r["published_at_dt"] + window)).any()
        rows.append({"tag_name": r["tag_name"], "published_at": r["published_at"], "is_failure": bool(in_window)})
    detail = pd.DataFrame(rows)
    rate = float(detail["is_failure"].mean()) if not detail.empty else 0.0
    return detail, rate


def _pr_title(raw_json: str) -> str:
    import json
    try:
        return json.loads(raw_json).get("title", "") or ""
    except (TypeError, ValueError):
        return ""


def summary(prs: pd.DataFrame, releases: pd.DataFrame, deployments: pd.DataFrame, freq: str = "W") -> dict:
    """Bundle all four metrics for a single repo into one dict for the dashboard."""
    cycle = pr_cycle_time(prs)
    deploy_events = releases if not releases.empty else deployments
    ts_col = "published_at" if not releases.empty else "created_at"
    freq_df = deployment_frequency(deploy_events, ts_col, freq=freq)
    lead_time = lead_time_for_changes(prs, releases)
    cfr_detail, cfr_rate = change_failure_rate(releases, prs)
    return {
        "pr_cycle_time": cycle,
        "deployment_frequency": freq_df,
        "lead_time_for_changes": lead_time,
        "change_failure_rate_detail": cfr_detail,
        "change_failure_rate": cfr_rate,
    }
