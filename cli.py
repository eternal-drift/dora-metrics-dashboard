"""CLI entrypoint: ingest GitHub data into the local SQLite store.

Usage:
    python cli.py ingest owner/repo
    python cli.py ingest owner/repo --limit 500
"""
from __future__ import annotations

import typer

from dora.ingest.github import GitHubClient
from dora.storage import db

app = typer.Typer(add_completion=False)


@app.command()
def ingest(repo: str, limit: int = 500, environment: str = None):
    """Fetch pull requests, releases, and deployments for OWNER/REPO."""
    owner, name = repo.split("/", 1)
    client = GitHubClient()

    typer.echo(f"Fetching pull requests for {repo}...")
    prs = client.pull_requests(owner, name, limit=limit)
    typer.echo(f"  {len(prs)} PRs")

    typer.echo("Fetching reviews for merged PRs...")
    reviews_by_number = {}
    merged_prs = [pr for pr in prs if pr.get("merged_at")]
    for i, pr in enumerate(merged_prs):
        reviews_by_number[pr["number"]] = client.pull_request_reviews(owner, name, pr["number"])
        if (i + 1) % 25 == 0:
            typer.echo(f"  {i + 1}/{len(merged_prs)} reviewed PRs fetched")

    typer.echo("Fetching releases...")
    releases = client.releases(owner, name, limit=limit)
    typer.echo(f"  {len(releases)} releases")

    typer.echo("Fetching deployments...")
    deployments = client.deployments(owner, name, environment=environment, limit=limit)
    typer.echo(f"  {len(deployments)} deployments")

    with db.connect() as conn:
        db.upsert_pull_requests(conn, repo, prs, reviews_by_number)
        db.upsert_releases(conn, repo, releases)
        db.upsert_deployments(conn, repo, deployments)

    from dora.config import settings
    typer.echo(f"Done. Stored to {settings.db_path}.")


@app.command()
def worker(max_events: int = None):
    """Run the event-queue consumer (dora/worker.py) that applies webhook-sourced
    events to storage. Runs forever unless --max-events is given (useful for testing)."""
    from dora.worker import run_worker

    n = run_worker(max_events=max_events)
    typer.echo(f"Processed {n} event(s).")


@app.command()
def advise(question: str):
    """Ask the AI Engineering Advisor a question (needs ANTHROPIC_API_KEY)."""
    from dora.advisor.advisor import Advisor

    try:
        advisor = Advisor()
    except RuntimeError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)
    answer, _ = advisor.ask(question)
    typer.echo(answer)


if __name__ == "__main__":
    app()
