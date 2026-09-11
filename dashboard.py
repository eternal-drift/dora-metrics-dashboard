"""Streamlit dashboard for engineering flow metrics computed from GitHub data.

Run: streamlit run dashboard.py
Data must already be ingested via `python cli.py ingest owner/repo`.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from dora.metrics.dora import summary
from dora.storage import db

st.set_page_config(page_title="Engineering Flow Metrics", layout="wide")


@st.cache_data(ttl=60)
def _load(repo: str):
    with db.connect() as conn:
        prs = db.load_pull_requests(conn, repo)
        releases = db.load_releases(conn, repo)
        deployments = db.load_deployments(conn, repo)
    return prs, releases, deployments


@st.cache_data(ttl=60)
def _known_repos():
    with db.connect() as conn:
        return db.known_repos(conn)


st.title("Engineering Flow Metrics")
st.caption("Deployment frequency, lead time for changes, PR cycle time, and change failure rate — computed from GitHub PR/release/deployment data.")

repos = _known_repos()
if not repos:
    st.warning("No data ingested yet. Run `python cli.py ingest owner/repo` first.")
    st.stop()

col1, col2 = st.columns([2, 1])
with col1:
    repo = st.selectbox("Repository", repos)
with col2:
    freq_label = st.selectbox("Deploy frequency bucket", ["Daily", "Weekly", "Monthly"], index=1)
freq = {"Daily": "D", "Weekly": "W", "Monthly": "M"}[freq_label]

prs, releases, deployments = _load(repo)
if prs.empty:
    st.info("No pull requests stored for this repo.")
    st.stop()

metrics = summary(prs, releases, deployments, freq=freq)

# --- Headline tiles -------------------------------------------------------
cycle = metrics["pr_cycle_time"]
lead = metrics["lead_time_for_changes"]
freq_df = metrics["deployment_frequency"]
cfr = metrics["change_failure_rate"]

t1, t2, t3, t4 = st.columns(4)
t1.metric("Median PR cycle time", f"{cycle['cycle_time_hours'].median():.1f} h" if not cycle.empty else "—")
t2.metric("Median lead time for changes", f"{lead['lead_time_hours'].median():.1f} h" if not lead.empty else "—")
avg_deploys = freq_df["deployments"].mean() if not freq_df.empty else 0
t3.metric(f"Avg deploys / {freq_label.lower()[:-2] if freq_label != 'Daily' else 'day'}", f"{avg_deploys:.1f}")
t4.metric("Change failure rate (proxy)", f"{cfr * 100:.1f}%")

st.divider()

# --- Deployment frequency ---------------------------------------------------
st.subheader("Deployment Frequency")
if freq_df.empty:
    st.info("No releases or deployments recorded for this repo.")
else:
    fig = px.bar(freq_df, x="period", y="deployments")
    st.plotly_chart(fig, width="stretch")

# --- PR cycle time ----------------------------------------------------------
st.subheader("PR Cycle Time")
if cycle.empty:
    st.info("No merged PRs recorded for this repo.")
else:
    weekly = cycle.set_index("merged_at_dt").resample("W")["cycle_time_hours"].median().reset_index()
    fig = px.line(weekly, x="merged_at_dt", y="cycle_time_hours", markers=True,
                  labels={"merged_at_dt": "Week", "cycle_time_hours": "Median cycle time (h)"})
    st.plotly_chart(fig, width="stretch")
    st.caption("Time-to-first-review is also stored per PR; see the raw table below.")

# --- Lead time for changes ---------------------------------------------------
st.subheader("Lead Time for Changes")
if lead.empty:
    st.info("No releases to compute lead time against. Ingest releases, or adapt `lead_time_for_changes` to use deployments.")
else:
    fig = px.histogram(lead, x="lead_time_hours", nbins=30)
    st.plotly_chart(fig, width="stretch")

# --- Change failure rate ------------------------------------------------
st.subheader("Change Failure Rate (proxy)")
st.caption(
    "Heuristic: a release is counted as a failure if a PR merges within the configured "
    "hotfix window afterward whose title matches hotfix/revert/rollback/incident. "
    "Adjust `DORA_HOTFIX_WINDOW_HOURS` or wire in real incident data for a ground-truth signal."
)
cfr_detail = metrics["change_failure_rate_detail"]
if not cfr_detail.empty:
    st.dataframe(cfr_detail, width="stretch")

with st.expander("Raw PR data"):
    st.dataframe(prs, width="stretch")
