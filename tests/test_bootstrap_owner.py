from __future__ import annotations

import psycopg2
import pytest

from app.security import verify_password
from tools import seed_database
from tools.bootstrap_owner import bootstrap_owner
from tools.migrate_database import apply_migrations
from tools.seed_database import reset_database


@pytest.fixture()
def empty_application_database(test_database_url: str):
    reset_database(test_database_url)
    apply_migrations(test_database_url)
    return test_database_url


def fetch_one(dsn: str, query: str, params=()):
    with psycopg2.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()


def test_bootstrap_creates_exactly_one_owner(empty_application_database):
    dsn = empty_application_database

    assert bootstrap_owner(dsn, "Initial Owner", "OWNER@example.com", "strong-password-123") is True
    assert bootstrap_owner(dsn, "Initial Owner", "owner@example.com", "strong-password-123") is False

    account = fetch_one(
        dsn,
        "SELECT account_type, name, email, password_hash, is_active FROM accounts;",
    )
    assert account[:3] == ("owner", "Initial Owner", "owner@example.com")
    assert verify_password("strong-password-123", account[3])
    assert account[4] is True
    assert fetch_one(
        dsn,
        "SELECT action, entity_type FROM activity_logs;",
    ) == ("bootstrapped_owner", "account")

    with pytest.raises(ValueError, match="An owner already exists"):
        bootstrap_owner(dsn, "Second Owner", "second@example.com", "another-password-456")

    assert fetch_one(dsn, "SELECT count(*) FROM accounts;") == (1,)


def test_bootstrap_validates_before_writing(empty_application_database):
    dsn = empty_application_database

    with pytest.raises(ValueError, match="valid owner email"):
        bootstrap_owner(dsn, "Owner", "not-an-email", "strong-password-123")
    with pytest.raises(ValueError, match="at least 12"):
        bootstrap_owner(dsn, "Owner", "owner@example.com", "short")

    assert fetch_one(dsn, "SELECT count(*) FROM accounts;") == (0,)


def test_classroom_seed_refuses_production(monkeypatch, empty_application_database):
    monkeypatch.setattr(seed_database, "APP_ENV", "production")

    with pytest.raises(SystemExit, match="Refusing to reset and seed"):
        seed_database.main()

    assert fetch_one(
        empty_application_database,
        "SELECT count(*) FROM schema_migrations;",
    ) == (2,)
