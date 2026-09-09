from __future__ import annotations

import os
from urllib.parse import urlsplit

import pytest


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "").strip()
if TEST_DATABASE_URL:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("APP_ENV", "development")


@pytest.fixture(scope="session")
def test_database_url() -> str:
    if not TEST_DATABASE_URL:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests")
    database_name = urlsplit(TEST_DATABASE_URL).path.lstrip("/").lower()
    if "test" not in database_name:
        pytest.fail("TEST_DATABASE_URL must name a dedicated database containing 'test'")
    return TEST_DATABASE_URL
