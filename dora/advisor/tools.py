"""Claude tool definitions for the Advisor -- thin @beta_tool wrappers
around dora.advisor.context, which does the actual (LLM-free, unit-tested)
work. Kept thin deliberately: any logic worth testing belongs in context.py,
not here.
"""
from __future__ import annotations

import json

from anthropic import beta_tool

from dora.advisor import context


def _json(value) -> str:
    return json.dumps(value, default=str)


@beta_tool
def list_repos() -> str:
    """List repos that have ingested or seeded data available to query."""
    return _json({"repos": context.repos()})


@beta_tool
def get_pr_cycle_time(repo: str) -> str:
    """Get PR cycle time (open-to-merge hours): overall median, recent trend, and its caveat.

    Args:
        repo: Repository in "owner/name" form, e.g. "acme/widgets".
    """
    return _json(context.pr_cycle_time_snapshot(repo))


@beta_tool
def get_change_failure_rate(repo: str) -> str:
    """Get change failure rate (fraction of releases followed by a hotfix-like merge), with caveat.

    Args:
        repo: Repository in "owner/name" form.
    """
    return _json(context.change_failure_rate_snapshot(repo))


@beta_tool
def get_deployment_frequency(repo: str) -> str:
    """Get deployment/release frequency per period and its trend.

    Args:
        repo: Repository in "owner/name" form.
    """
    return _json(context.deployment_frequency_snapshot(repo))


@beta_tool
def get_lead_time_for_changes(repo: str) -> str:
    """Get lead time for changes (PR merge to next release), with caveat.

    Args:
        repo: Repository in "owner/name" form.
    """
    return _json(context.lead_time_snapshot(repo))


@beta_tool
def get_mttr(repo: str) -> str:
    """Get mean time to restore, computed from incident-type issues, with caveat.

    Args:
        repo: Repository in "owner/name" form.
    """
    return _json(context.mttr_snapshot(repo))


@beta_tool
def get_wip(repo: str) -> str:
    """Get work-in-progress (started-but-unresolved issue count) and its trend, with caveat.

    Args:
        repo: Repository in "owner/name" form.
    """
    return _json(context.wip_snapshot(repo))


@beta_tool
def get_throughput(repo: str) -> str:
    """Get throughput (issues resolved per period) and its trend, with caveat.

    Args:
        repo: Repository in "owner/name" form.
    """
    return _json(context.throughput_snapshot(repo))


@beta_tool
def get_space_indicators(repo: str) -> str:
    """Get SPACE-inspired indicators (activity, performance, efficiency; satisfaction and
    communication are always null -- no signal exists for them), with caveat.

    Args:
        repo: Repository in "owner/name" form.
    """
    return _json(context.space_snapshot(repo))


@beta_tool
def get_full_health_snapshot(repo: str) -> str:
    """Get every metric at once for a repo -- use this for broad "summarize engineering health"
    or VP-level questions instead of calling each metric tool separately.

    Args:
        repo: Repository in "owner/name" form.
    """
    return _json(context.full_health_snapshot(repo))


ALL_TOOLS = [
    list_repos,
    get_pr_cycle_time,
    get_change_failure_rate,
    get_deployment_frequency,
    get_lead_time_for_changes,
    get_mttr,
    get_wip,
    get_throughput,
    get_space_indicators,
    get_full_health_snapshot,
]
