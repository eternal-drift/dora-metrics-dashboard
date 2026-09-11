import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    github_token: str = field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))
    db_path: str = field(default_factory=lambda: os.getenv("DORA_DB_PATH", "dora.db"))
    api_base_url: str = "https://api.github.com"

    # Change-failure-rate proxy: a merge to the default branch within this many
    # hours after a release/deploy is treated as a "hotfix" (i.e. that release failed).
    # There is no universal "incident" signal in the GitHub API, so this is a
    # documented heuristic, not a ground-truth measurement.
    hotfix_window_hours: int = int(os.getenv("DORA_HOTFIX_WINDOW_HOURS", "24"))
    hotfix_label_keywords: tuple = ("hotfix", "revert", "rollback", "incident")


settings = Settings()
