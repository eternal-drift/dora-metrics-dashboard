# ADR 0004: Streamlit before a React dashboard

## Status
Accepted

## Context
The target architecture (see [roadmap.md](../roadmap.md)) ends with a React
dashboard behind a Metrics API. Building that first means building an API
contract, an auth story, and a frontend before a single metric has been
validated against real data.

## Decision
Ship the dashboard in Streamlit (`dashboard.py`), reading directly from
storage via `dora/metrics`, with no API layer in between. Move to a
Metrics API (FastAPI) + React frontend once there is a second consumer of
the metrics — the AI Advisor's tool-calling layer, or a second team wanting
their own view — because a second consumer is what actually forces a
stable API contract into existence. Building the API contract for a
hypothetical second consumer before one exists tends to guess wrong about
what that contract needs to look like.

## Consequences
- Fast iteration on metric definitions early, when they were most likely
  to be wrong (see the proxy-metric caveats in [ADR 0002](0002-proxy-metrics-over-missing-signals.md))
  — no API/frontend churn on every definition change.
- The React dashboard is explicitly a v2 deliverable, not a missing piece
  of v1. Streamlit is not a placeholder to apologize for; it's the correct
  choice for a single-user local tool, and the migration trigger is
  concrete (a second consumer), not a vague "eventually."
- Streamlit's per-session state and lack of a stable JSON API means the AI
  Advisor cannot currently query "what the dashboard shows" directly — it
  queries `dora/metrics` the same way `dashboard.py` does. This becomes a
  real constraint once the Advisor needs request-scoped or role-scoped
  metric access, which is the trigger described above.
