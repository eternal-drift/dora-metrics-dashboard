import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    github_token: str = field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))
    db_path: str = field(default_factory=lambda: os.getenv("DORA_DB_PATH", "dora.db"))
    api_base_url: str = "https://api.github.com"

    # Storage backend: SQLite by default (see docs/adr/0001-storage-sqlite-then-postgres.md).
    # Set DATABASE_URL (e.g. postgresql://user:pass@host:5432/dora) to use Postgres instead --
    # dora/storage/db.py is written against SQLAlchemy Core so both dialects share one code path.
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))

    # Change-failure-rate proxy: a merge to the default branch within this many
    # hours after a release/deploy is treated as a "hotfix" (i.e. that release failed).
    # There is no universal "incident" signal in the GitHub API, so this is a
    # documented heuristic, not a ground-truth measurement.
    hotfix_window_hours: int = int(os.getenv("DORA_HOTFIX_WINDOW_HOURS", "24"))
    hotfix_label_keywords: tuple = ("hotfix", "revert", "rollback", "incident")

    # AI Engineering Advisor (dora/advisor) -- see docs/roadmap.md.
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    advisor_model: str = field(default_factory=lambda: os.getenv("ADVISOR_MODEL", "claude-opus-5"))

    # Webhook-driven ingestion + event queue (dora/webhooks, dora/queue, dora/worker).
    # See docs/adr/0006-webhook-ingestion-and-event-queue.md.
    github_webhook_secret: str = field(default_factory=lambda: os.getenv("GITHUB_WEBHOOK_SECRET", ""))
    # Set QUEUE_URL to a redis:// URL to use Redis as the queue; unset falls back to an
    # in-process queue (dev/test only -- not durable, not shared across processes).
    queue_url: str = field(default_factory=lambda: os.getenv("QUEUE_URL", ""))

    # Observability (dora/observability) -- operational health of this platform itself,
    # not the engineering metrics it computes about other teams. See docs/adr/0007.
    otel_exporter_otlp_endpoint: str = field(default_factory=lambda: os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", ""))
    otel_service_name_api: str = field(default_factory=lambda: os.getenv("OTEL_SERVICE_NAME_API", "dora-api"))
    otel_service_name_worker: str = field(default_factory=lambda: os.getenv("OTEL_SERVICE_NAME_WORKER", "dora-worker"))
    worker_metrics_port: int = int(os.getenv("WORKER_METRICS_PORT", "9100"))


settings = Settings()
