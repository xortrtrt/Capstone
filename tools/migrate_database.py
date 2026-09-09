from __future__ import annotations

import hashlib
from pathlib import Path
import sys

import psycopg2


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = PROJECT_ROOT / "database" / "migrations"
MIGRATION_LOCK_ID = 4_628_731_991
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import DATABASE_URL, database_dsn


def migration_files() -> list[Path]:
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        raise RuntimeError(f"No SQL migrations found in {MIGRATIONS_DIR}")
    return files


def checksum(path: Path) -> str:
    normalized = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def apply_migrations(dsn: str = DATABASE_URL) -> list[str]:
    """Apply pending migrations exactly once and reject edited history."""
    connection = psycopg2.connect(database_dsn(dsn), connect_timeout=15)
    applied_now: list[str] = []
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s);", (MIGRATION_LOCK_ID,))
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version text PRIMARY KEY,
                        checksum_sha256 text NOT NULL CHECK (length(checksum_sha256) = 64),
                        applied_at timestamptz NOT NULL DEFAULT now()
                    );
                    """
                )
                cursor.execute("SELECT version, checksum_sha256 FROM schema_migrations;")
                applied = dict(cursor.fetchall())

                for path in migration_files():
                    version = path.stem
                    file_checksum = checksum(path)
                    if version in applied:
                        if applied[version] != file_checksum:
                            raise RuntimeError(
                                f"Applied migration {version} was edited; add a new migration instead."
                            )
                        continue

                    cursor.execute(path.read_text(encoding="utf-8"))
                    cursor.execute(
                        "INSERT INTO schema_migrations (version, checksum_sha256) VALUES (%s, %s);",
                        (version, file_checksum),
                    )
                    applied_now.append(version)
    finally:
        connection.close()
    return applied_now


def main() -> None:
    applied = apply_migrations()
    if applied:
        print("Applied migrations: " + ", ".join(applied))
    else:
        print("Database schema is already current.")


if __name__ == "__main__":
    main()
