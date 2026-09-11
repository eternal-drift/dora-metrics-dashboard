# Metric Definitions & Caveats

This is the single source of truth for how every metric in this system is
computed, what data it needs, and where it lies to you. If a number from the
dashboard is going into a slide for a VP or a hiring manager, the caveat in
this doc is the thing you say out loud before they ask.

Every metric here is computed from real ingested data (`dora/ingest/github.py`)
or from Jira-shaped synthetic data (`scripts/seed_demo_data.py`) — nothing is
hand-typed into a spreadsheet.

## DORA metrics (`dora/metrics/dora.py`)

| Metric | Definition | Data needed | Caveat |
|---|---|---|---|
| **Deployment frequency** | Count of releases (or deployments) per day/week/month | GitHub Releases API, or `--environment` deployments | If a repo doesn't tag releases and has no deployment events, this is empty — it does not fall back to commit or merge counts, because that would silently misrepresent "shipped" as "written" |
| **Lead time for changes** | Hours from a PR's merge to the next release published afterward | Merged PRs + releases, same repo/timeline | Proxy, not ground truth: GitHub has no native "this change reached production at time T" event. A PR merged the day before a release is counted the same as one merged an hour before, even though the wait was materially different. Repos with irregular or batched releases will show high, noisy lead times that reflect release cadence more than engineering speed |
| **PR cycle time** | Hours from PR open to merge; also tracks time-to-first-review | Merged PRs only (closed-without-merge PRs are excluded — abandoned work isn't cycle time) | Doesn't distinguish "PR sat waiting for review" from "PR sat waiting for CI" from "author was on PTO." Time-to-first-review is a partial proxy for the first, nothing here measures the second or third |
| **Change failure rate** | Fraction of releases followed within `hotfix_window_hours` (default 24h) by a PR merge whose title/labels match a hotfix/revert/rollback/incident keyword | Releases + subsequent PR merges | Heuristic, not an incident measurement. False negatives: a real production failure fixed with a PR titled "fix checkout bug" (no keyword match) is missed. False positives: an unrelated hotfix merged coincidentally in the window after an unrelated release is counted. This is the weakest-signal metric in the system and should be sanity-checked against actual incident records before being presented as fact |

## Flow & SPACE-inspired metrics (`dora/metrics/flow.py`)

| Metric | Definition | Data needed | Caveat |
|---|---|---|---|
| **MTTR** | Mean hours from an incident issue's `created_at` to `resolved_at` | Issues with `issue_type == "incident"` and a `resolved_at` | Treats ticket filing as the start of the outage clock. There is no separate detection-time signal, so if incidents are filed after detection/triage has already begun (the common case), this **overstates** true MTTR |
| **WIP** | Count of issues started but not resolved, sampled at the end of each period | Issues with `started_at` set | Point-in-time snapshot, not a period average. An issue that spikes WIP mid-week and clears before the sample is invisible — this understates volatility, not just the level |
| **Throughput** | Count of issues resolved per period | Issues with `resolved_at` set | Counts completed work items, not deployments — deliberately distinct from deployment frequency. Says nothing about the size or value of what was completed; a period of ten one-line fixes and a period of ten major features look identical |
| **SPACE — Activity** | PRs opened per period | PRs | Proxy for activity only in the narrow "code was written" sense; says nothing about review, design, or incident work |
| **SPACE — Performance** | Same as throughput (issues resolved per period) | Issues | Reused rather than duplicated — "performance" here means "output," not quality or customer impact |
| **SPACE — Efficiency** | Median PR cycle time per period | PRs | Same caveats as PR cycle time above |
| **SPACE — Satisfaction, Communication** | **Not computed — returned as `None`** | N/A | No survey or chat/comment-volume signal exists in this data source. This is deliberate: the system returns `None` with a caveat rather than approximating these from unrelated numbers. Any presentation of SPACE from this system should say explicitly that 2 of 5 dimensions are out of scope, not silently omit them |

## Why proxies instead of "real" data

Lead time, change failure rate, and MTTR would ideally come from a real
incident-management system (PagerDuty, Opsgenie) and a real deploy pipeline
event (not a GitHub Release, which is sometimes cut well after code actually
reaches production). This system doesn't have those integrations yet — see
[roadmap.md](roadmap.md) — so it documents the substitution instead of
hiding it. Treat every "proxy" caveat above as a todo for a real
integration, not a permanent design choice.
