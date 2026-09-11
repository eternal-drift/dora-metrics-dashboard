"""Thin client for pulling the raw signals DORA/flow metrics are built from:
pull requests (+ their commits and reviews), releases, and deployments.

Only read-only REST endpoints are used. Pagination and basic rate-limit
backoff are handled here so callers just get back plain lists of dicts.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Iterator

import requests

from dora.config import settings


class GitHubAPIError(RuntimeError):
    pass


@dataclass
class GitHubClient:
    token: str = ""
    base_url: str = settings.api_base_url
    per_page: int = 100

    def __post_init__(self) -> None:
        self.token = self.token or settings.github_token
        self.session = requests.Session()
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self.session.headers.update(headers)

    def _paginate(self, path: str, params: dict[str, Any] | None = None) -> Iterator[dict]:
        url = f"{self.base_url}{path}"
        params = dict(params or {})
        params["per_page"] = self.per_page
        while url:
            resp = self.session.get(url, params=params)
            if resp.status_code == 403 and "rate limit" in resp.text.lower():
                reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
                time.sleep(max(1, reset - int(time.time())))
                continue
            if resp.status_code >= 400:
                raise GitHubAPIError(f"GET {url} -> {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
            yield from data
            url = resp.links.get("next", {}).get("url")
            params = None  # `next` URL already carries params

    def pull_requests(self, owner: str, repo: str, state: str = "all", limit: int | None = None) -> list[dict]:
        out = []
        for pr in self._paginate(f"/repos/{owner}/{repo}/pulls", {"state": state, "sort": "updated", "direction": "desc"}):
            out.append(pr)
            if limit and len(out) >= limit:
                break
        return out

    def pull_request_reviews(self, owner: str, repo: str, pr_number: int) -> list[dict]:
        return list(self._paginate(f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews"))

    def releases(self, owner: str, repo: str, limit: int | None = None) -> list[dict]:
        out = []
        for rel in self._paginate(f"/repos/{owner}/{repo}/releases"):
            out.append(rel)
            if limit and len(out) >= limit:
                break
        return out

    def deployments(self, owner: str, repo: str, environment: str | None = None, limit: int | None = None) -> list[dict]:
        params = {"environment": environment} if environment else {}
        out = []
        for dep in self._paginate(f"/repos/{owner}/{repo}/deployments", params):
            out.append(dep)
            if limit and len(out) >= limit:
                break
        return out

    def default_branch(self, owner: str, repo: str) -> str:
        resp = self.session.get(f"{self.base_url}/repos/{owner}/{repo}")
        if resp.status_code >= 400:
            raise GitHubAPIError(f"GET repo {owner}/{repo} -> {resp.status_code}: {resp.text[:300]}")
        return resp.json()["default_branch"]
