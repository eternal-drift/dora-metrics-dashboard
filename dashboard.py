"""Streamlit dashboard for engineering flow metrics computed from GitHub data.

Run: streamlit run dashboard.py
Data must already be ingested via `python cli.py ingest owner/repo`.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from dora.metrics.dora import summary
from dora.metrics.flow import mttr, space_indicators, throughput, wip
from dora.storage import db

st.set_page_config(page_title="Engineering Flow Metrics", layout="wide")


@st.cache_data(ttl=60)
def _load(repo: str):
    with db.connect() as conn:
        prs = db.load_pull_requests(conn, repo)
        releases = db.load_releases(conn, repo)
        deployments = db.load_deployments(conn, repo)
        issues = db.load_issues(conn, repo)
    return prs, releases, deployments, issues


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

prs, releases, deployments, issues = _load(repo)
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

st.divider()
st.header("Flow & SPACE-Inspired Metrics")
st.caption(
    "Computed from Jira-style issue events (dora/ingest/synthetic data — see "
    "`scripts/seed_demo_data.py`); there is no live Jira ingestion in this project."
)

if issues.empty:
    st.info("No issues stored for this repo. Seed demo data with `python scripts/seed_demo_data.py` to see WIP/throughput/MTTR.")
else:
    mttr_detail, mttr_hours = mttr(issues)
    throughput_df = throughput(issues, freq=freq)
    wip_df = wip(issues, freq=freq)

    m1, m2, m3 = st.columns(3)
    m1.metric("Mean time to restore (MTTR)", f"{mttr_hours:.1f} h" if mttr_hours == mttr_hours else "—")
    avg_throughput = throughput_df["resolved"].mean() if not throughput_df.empty else 0
    m2.metric(f"Avg throughput / {freq_label.lower()[:-2] if freq_label != 'Daily' else 'day'}", f"{avg_throughput:.1f} issues")
    current_wip = wip_df.iloc[-1]["wip"] if not wip_df.empty else 0
    m3.metric("Current WIP", f"{int(current_wip)}")

    st.subheader("Work in Progress (point-in-time)")
    if wip_df.empty:
        st.info("No started issues to compute WIP from.")
    else:
        fig = px.line(wip_df, x="period", y="wip", markers=True)
        st.plotly_chart(fig, width="stretch")
        st.caption("Snapshot of open (started, unresolved) issues at the end of each period, not a period average.")

    st.subheader("Throughput")
    if throughput_df.empty:
        st.info("No resolved issues recorded.")
    else:
        fig = px.bar(throughput_df, x="period", y="resolved")
        st.plotly_chart(fig, width="stretch")

    st.subheader("MTTR (proxy)")
    st.caption("Hours from an incident issue's creation to its resolution. No separate detection-time signal is available, so this overstates MTTR if incidents are filed after detection has already begun.")
    if not mttr_detail.empty:
        st.dataframe(mttr_detail, width="stretch")
    else:
        st.info("No resolved incident issues recorded.")

    st.subheader("SPACE-Inspired Indicators")
    st.caption(
        "SPACE is survey- and sentiment-driven in its original form. Only Activity, "
        "Efficiency, and Performance have a reasonable proxy here; Satisfaction and "
        "Communication have no signal in this data source and are intentionally omitted "
        "rather than approximated from unrelated numbers."
    )
    space = space_indicators(prs, issues, freq=freq)
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.markdown("**Activity** (PRs opened)")
        if space["activity"].empty:
            st.info("No data.")
        else:
            st.plotly_chart(px.bar(space["activity"], x="period", y="prs_opened"), width="stretch")
    with sc2:
        st.markdown("**Performance** (issues resolved)")
        if space["performance"].empty:
            st.info("No data.")
        else:
            st.plotly_chart(px.bar(space["performance"], x="period", y="resolved"), width="stretch")
    with sc3:
        st.markdown("**Efficiency** (median PR cycle time)")
        if space["efficiency"].empty:
            st.info("No data.")
        else:
            st.plotly_chart(px.line(space["efficiency"], x="period", y="median_cycle_time_hours", markers=True), width="stretch")
    st.caption("Satisfaction and Communication: not measurable from GitHub/Jira event data alone (would need survey or chat/comment ingestion) — omitted rather than faked.")

    with st.expander("Raw issue data"):
        st.dataframe(issues, width="stretch")

st.divider()
st.header("AI Engineering Advisor")
st.caption(
    "Ask questions like \"why did PR cycle time increase?\" or \"summarize engineering "
    "health for the VP\" — answers are grounded in the metrics above via tool calling, "
    "and always carry the same caveats shown on this dashboard. See docs/roadmap.md."
)

from dora.config import settings as _settings  # noqa: E402

if not _settings.anthropic_api_key:
    st.info("Set `ANTHROPIC_API_KEY` to enable the AI Advisor (see README.md).")
else:
    if "advisor_display" not in st.session_state:
        st.session_state.advisor_display = []
    if "advisor_history" not in st.session_state:
        st.session_state.advisor_history = []

    for role, text in st.session_state.advisor_display:
        with st.chat_message(role):
            st.markdown(text)

    question = st.chat_input(f"Ask about {repo}...")
    if question:
        st.session_state.advisor_display.append(("user", question))
        with st.chat_message("user"):
            st.markdown(question)

        from dora.advisor.advisor import Advisor

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                advisor = Advisor()
                scoped_question = f"[Current dashboard repo: {repo}] {question}"
                answer, st.session_state.advisor_history = advisor.ask(
                    scoped_question, st.session_state.advisor_history
                )
                st.markdown(answer)
        st.session_state.advisor_display.append(("assistant", answer))
