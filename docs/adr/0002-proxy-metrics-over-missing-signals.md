# ADR 0002: Documented proxy metrics instead of blocking on missing signals

## Status
Accepted

## Context
Three metrics — lead time for changes, change failure rate, and MTTR — have
no first-class, unambiguous signal in the GitHub REST API or in Jira-shaped
issue data. A "real" implementation would need a deploy pipeline event (not
a GitHub Release, which can be cut well after code reaches production), an
incident-management system (PagerDuty/Opsgenie), and a detection-time
timestamp separate from ticket-creation time.

The options were: (a) don't compute these metrics until real integrations
exist, (b) compute them from the best available proxy and document the gap,
or (c) compute them from a proxy and present them as ground truth.

## Decision
Option (b). Every proxy metric — lead time (PR merge → next release),
change failure rate (hotfix-labeled merge within N hours of a release), and
MTTR (incident issue created → resolved) — is computed and shown, but each
one carries an explicit, code-adjacent caveat (docstring in
`dora/metrics/{dora,flow}.py`, table in [metrics.md](../metrics.md)) stating
what it actually measures and how it can mislead.

Option (c) was rejected outright: presenting a heuristic as a measurement
is the kind of thing that gets a metrics program actively distrusted once
someone finds the gap themselves. Option (a) was rejected because a
platform that refuses to show anything until every integration is perfect
never ships a usable v1.

## Consequences
- Every dashboard view and every AI Advisor answer that touches one of
  these metrics must surface (or be able to surface, on request) its
  caveat — this is a standing requirement on the Advisor's system prompt
  and RAG context (see [roadmap.md](../roadmap.md)), not just a README
  footnote.
- Real integrations (deploy-pipeline events, an incident-management ingest)
  are the path to retiring each caveat one at a time — this ADR is
  superseded per-metric as each integration lands, not all at once.
