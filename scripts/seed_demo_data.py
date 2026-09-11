"""Generate synthetic-but-realistic PR/release data so the dashboard can be
demoed without hitting the live GitHub API or needing a token.

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


def main() -> None:
    prs, releases = [], []
    pr_number = 1

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

        # Release roughly weekly; failure rate improves over time too.
        release_time = week_start + timedelta(days=6, hours=random.uniform(0, 12))
        releases.append({"id": week + 1, "tag_name": f"v0.{week + 1}.0", "published_at": _iso(release_time)})

        failure_chance = 0.35 - 0.3 * maturity  # 35% -> 5%
        if random.random() < failure_chance:
            hotfix_created = release_time + timedelta(hours=random.uniform(1, 20))
            prs.append({
                "number": pr_number, "state": "closed", "created_at": _iso(hotfix_created),
                "merged_at": _iso(hotfix_created + timedelta(hours=1)),
                "closed_at": _iso(hotfix_created + timedelta(hours=1)),
                "first_review_at": _iso(hotfix_created + timedelta(minutes=20)),
                "additions": random.randint(2, 20), "deletions": random.randint(0, 10),
                "title": random.choice(HOTFIX_TITLES),
            })
            pr_number += 1

    with db.connect() as conn:
        db.upsert_pull_requests(conn, REPO, prs)
        db.upsert_releases(conn, REPO, releases)
        db.upsert_deployments(conn, REPO, [])

    from dora.config import settings
    print(f"Seeded {len(prs)} PRs and {len(releases)} releases for {REPO} into {settings.db_path}")


if __name__ == "__main__":
    main()
