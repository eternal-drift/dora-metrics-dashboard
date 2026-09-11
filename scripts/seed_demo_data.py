"""Generate synthetic-but-realistic PR/release/issue data so the dashboard
can be demoed without hitting the live GitHub API (or a Jira instance --
there is no live Jira ingestion in this project; issues are Jira-shaped
synthetic events used to exercise WIP/throughput/MTTR).

Usage: python scripts/seed_demo_data.py [repo_name]
"""
from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")

from dora.storage import db

random.seed(7)

REPO = sys.argv[1] if len(sys.argv) > 1 else "acme/widgets"
WEEKS = 26
START = datetime(2024, 1, 1, tzinfo=timezone.utc)

HOTFIX_TITLES = ["hotfix: fix null pointer in checkout", "revert: bad migration", "rollback broken feature flag"]
NORMAL_TITLES = [
    "add pagination to search results", "refactor auth middleware", "fix flaky test in CI",
    "improve error messages", "add dark mode toggle", "update dependency versions",
    "optimize database query", "add rate limiting to API", "fix typo in docs",
    "implement caching layer",
]


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


ASSIGNEES = ["amir", "bea", "chidi", "dana", "eli"]


def main() -> None:
    prs, releases, issues = [], [], []
    pr_number = 1
    issue_seq = 1

    # Simulate improving cycle time over the 26 weeks (mirrors a real flow-metrics story).
    for week in range(WEEKS):
        week_start = START + timedelta(weeks=week)
        maturity = week / WEEKS  # 0 -> 1, used to trend metrics over time
        n_prs = random.randint(3, 6) + int(maturity * 4)  # throughput improves over time
        median_cycle_hours = 48 - 30 * maturity  # 48h -> 18h as the team improves

        for _ in range(n_prs):
            created = week_start + timedelta(days=random.uniform(0, 6), hours=random.uniform(0, 23))
            cycle_hours = max(1, random.gauss(median_cycle_hours, median_cycle_hours * 0.3))
            merged = created + timedelta(hours=cycle_hours)
            first_review = created + timedelta(hours=min(cycle_hours * 0.4, cycle_hours - 0.5))
            title = random.choice(NORMAL_TITLES)
            prs.append({
                "number": pr_number, "state": "closed", "created_at": _iso(created),
                "merged_at": _iso(merged), "closed_at": _iso(merged),
                "first_review_at": _iso(first_review),
                "additions": random.randint(5, 400), "deletions": random.randint(0, 150),
                "title": title,
            })
            pr_number += 1

            # Jira-style story/bug backing the PR: filed a bit before work
            # started, moved in_progress at PR-open time, resolved at merge.
            filed = created - timedelta(hours=random.uniform(2, 72))
            issues.append({
                "key": f"ENG-{issue_seq}", "issue_type": random.choice(["story", "story", "bug"]),
                "status": "done", "assignee": random.choice(ASSIGNEES),
                "priority": random.choice(["P2", "P3", "P3", "P4"]),
                "created_at": _iso(filed), "started_at": _iso(created), "resolved_at": _iso(merged),
            })
            issue_seq += 1

        # A trickle of backlog/in-progress work that never resolves in this
        # window, so WIP has something to show besides completed items.
        for _ in range(random.randint(0, 2)):
            filed = week_start + timedelta(days=random.uniform(0, 6))
            still_open = random.random() < 0.6
            issues.append({
                "key": f"ENG-{issue_seq}", "issue_type": "story",
                "status": "in_progress" if still_open else "backlog",
                "assignee": random.choice(ASSIGNEES), "priority": random.choice(["P3", "P4"]),
                "created_at": _iso(filed), "started_at": _iso(filed) if still_open else None,
                "resolved_at": None,
            })
            issue_seq += 1

        # Release roughly weekly; failure rate improves over time too.
        release_time = week_start + timedelta(days=6, hours=random.uniform(0, 12))
        releases.append({"id": week + 1, "tag_name": f"v0.{week + 1}.0", "published_at": _iso(release_time)})

        failure_chance = 0.35 - 0.3 * maturity  # 35% -> 5%
        if random.random() < failure_chance:
            hotfix_created = release_time + timedelta(hours=random.uniform(1, 20))
            hotfix_merged = hotfix_created + timedelta(hours=1)
            prs.append({
                "number": pr_number, "state": "closed", "created_at": _iso(hotfix_created),
                "merged_at": _iso(hotfix_merged), "closed_at": _iso(hotfix_merged),
                "first_review_at": _iso(hotfix_created + timedelta(minutes=20)),
                "additions": random.randint(2, 20), "deletions": random.randint(0, 10),
                "title": random.choice(HOTFIX_TITLES),
            })
            pr_number += 1

            # Incident issue backing the hotfix: MTTR improves as the team
            # matures, same story the PR cycle-time trend already tells.
            mttr_hours = max(0.5, random.gauss(6 - 4 * maturity, 1.5))
            detected = release_time + timedelta(minutes=random.uniform(5, 45))
            resolved = detected + timedelta(hours=mttr_hours)
            issues.append({
                "key": f"ENG-{issue_seq}", "issue_type": "incident", "status": "done",
                "assignee": random.choice(ASSIGNEES), "priority": "P1",
                "created_at": _iso(detected), "started_at": _iso(detected), "resolved_at": _iso(resolved),
            })
            issue_seq += 1

    with db.connect() as conn:
        db.upsert_pull_requests(conn, REPO, prs)
        db.upsert_releases(conn, REPO, releases)
        db.upsert_deployments(conn, REPO, [])
        db.upsert_issues(conn, REPO, issues)

    from dora.config import settings
    print(f"Seeded {len(prs)} PRs, {len(releases)} releases, and {len(issues)} issues for {REPO} into {settings.db_path}")


if __name__ == "__main__":
    main()
