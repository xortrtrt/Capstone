from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

APP_ENV = os.getenv("APP_ENV", "development")
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "change-this-local-dev-secret")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://meattrack:meattrack@127.0.0.1:5433/meattrack",
)
DATABASE_POOL_MIN = int(os.getenv("DATABASE_POOL_MIN", "1"))
DATABASE_POOL_MAX = int(os.getenv("DATABASE_POOL_MAX", "5"))


def database_dsn(value: str = DATABASE_URL) -> str:
    """Return a psycopg2-compatible PostgreSQL DSN."""
    if value.startswith("postgres://"):
        value = "postgresql://" + value.removeprefix("postgres://")
    parts = urlsplit(value)
    if parts.scheme not in {"postgresql", "postgres"}:
        raise ValueError("DATABASE_URL must be a PostgreSQL connection URL")
    return urlunsplit(parts)

OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

OWNER_PASSWORD = os.getenv("OWNER_PASSWORD", "demo123")
TEAM_LEADER_PASSWORD = os.getenv("TEAM_LEADER_PASSWORD", "demo1234")
RESELLER_PASSWORD = os.getenv("RESELLER_PASSWORD", "demo1234")
DEFAULT_ACCOUNT_PASSWORD = os.getenv("DEFAULT_ACCOUNT_PASSWORD", "demo1234")

if APP_ENV == "production":
    def is_placeholder(value: str) -> bool:
        return not value or value.startswith("replace_with_")

    insecure_defaults = {
        "DATABASE_URL": "replace_with_" in DATABASE_URL,
        "SESSION_SECRET_KEY": (
            SESSION_SECRET_KEY == "change-this-local-dev-secret"
            or is_placeholder(SESSION_SECRET_KEY)
            or len(SESSION_SECRET_KEY) < 32
        ),
        "OWNER_PASSWORD": OWNER_PASSWORD == "demo123" or is_placeholder(OWNER_PASSWORD),
        "TEAM_LEADER_PASSWORD": TEAM_LEADER_PASSWORD == "demo1234" or is_placeholder(TEAM_LEADER_PASSWORD),
        "RESELLER_PASSWORD": RESELLER_PASSWORD == "demo1234" or is_placeholder(RESELLER_PASSWORD),
        "DEFAULT_ACCOUNT_PASSWORD": DEFAULT_ACCOUNT_PASSWORD == "demo1234" or is_placeholder(DEFAULT_ACCOUNT_PASSWORD),
    }
    unsafe_names = [name for name, is_unsafe in insecure_defaults.items() if is_unsafe]
    if unsafe_names:
        raise RuntimeError(
            "Production secrets must be set explicitly: " + ", ".join(unsafe_names)
        )
