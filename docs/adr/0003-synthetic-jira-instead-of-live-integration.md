# ADR 0003: Synthetic Jira-shaped data instead of a live Jira integration

## Status
Accepted

## Context
WIP, throughput, MTTR, and half of the SPACE indicators need issue-tracker
data (created/started/resolved timestamps, issue type, status). Building a
live Jira integration (OAuth, REST/webhooks, field-mapping across
customer-specific Jira workflows) is a multi-week effort that doesn't
change what the metrics *mean* once the data is flowing — it only changes
where the rows come from.

## Decision
Ship `scripts/seed_demo_data.py`, which generates Jira-shaped synthetic
issues (stories, bugs, incidents) on the same timeline as synthetic PRs and
releases, stored in the same `issues` table a real Jira ingest would write
to. The synthetic generator deliberately encodes a plausible improvement
trend (cycle time 48h → 18h, change-failure rate 35% → 5% over 26 weeks)
rather than random noise, so the dashboard demos a coherent story instead
of a scatterplot — see [before-after-intervention.md](../before-after-intervention.md).

A live Jira ingest is deferred to when a real customer/team needs it (see
[roadmap.md](../roadmap.md)); the `issues` table schema is designed so that
a real Jira ingest module is a drop-in alongside `dora/ingest/github.py`,
not a schema change.

## Consequences
- The dashboard and Advisor are fully demoable with zero external
  dependencies beyond a GitHub token (and not even that, for the synthetic
  path) — important for a project a reviewer runs cold.
- Every "issue-tracker" metric in this system is honest about being
  demoed on synthetic data until a live ingest lands; this is stated in
  the README and must stay stated there — silently swapping synthetic data
  for "real-looking" data in a demo without disclosure would misrepresent
  the system's actual capability.
- Real Jira field mapping (custom statuses, custom issue types, multiple
  workflows per project) is unvalidated until a live integration is built —
  the synthetic data cannot surface those edge cases.
