from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import psycopg2
import pytest

from app import database
from app import repositories
from app.security import hash_password
from tools.migrate_database import apply_migrations
from tools.seed_database import reset_database


@pytest.fixture()
def order_database(test_database_url: str):
    database.close_pool()
    reset_database(test_database_url)
    apply_migrations(test_database_url)

    with psycopg2.connect(test_database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO resellers (
                    business_name, contact_person, email, contact_number, reseller_status
                )
                VALUES ('Lipa Fresh Mart', 'Test Reseller', 'reseller@lipafresh.test', '09170000000', 'active')
                RETURNING reseller_id;
                """
            )
            reseller_id = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO accounts (account_type, name, email, password_hash, is_active)
                VALUES ('team_leader', 'Maria Santos', 'leader@batangaspremium.test', %s, true)
                RETURNING account_id;
                """,
                (hash_password("test-password"),),
            )
            leader_id = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO accounts (account_type, reseller_id, name, email, password_hash, is_active)
                VALUES ('reseller', %s, 'Lipa Fresh Mart', 'reseller@lipafresh.test', %s, true);
                """,
                (reseller_id, hash_password("test-password")),
            )
            cursor.execute(
                """
                UPDATE resellers
                SET approved_by_account_id = %s, approved_at = now()
                WHERE reseller_id = %s;
                """,
                (leader_id, reseller_id),
            )
            cursor.execute(
                """
                INSERT INTO inventory_items (
                    item_type, category, name, unit, base_price, quantity_available, is_active
                )
                VALUES ('finished_product', 'Pork', 'Atomic Test Product', 'pack', 125, 0, true)
                RETURNING item_id;
                """
            )
            product_id = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO inventory_batches (
                    item_id, batch_code, source_type, quantity_received, quantity_available,
                    unit, received_date, expiry_date, quality_status
                )
                VALUES
                    (%s, 'EARLY', 'production', 2, 2, 'pack', CURRENT_DATE, CURRENT_DATE + 5, 'approved'),
                    (%s, 'LATER', 'production', 3, 3, 'pack', CURRENT_DATE, CURRENT_DATE + 10, 'approved');
                """,
                (product_id, product_id),
            )

    yield {"product_id": product_id}
    database.close_pool()


def fetch_values(test_database_url: str, query: str, params=()):
    with psycopg2.connect(test_database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()


def test_walk_in_sale_rolls_back_when_stock_is_insufficient(test_database_url, order_database):
    with pytest.raises(ValueError, match="Insufficient stock"):
        repositories.create_order("team-leader", order_database["product_id"], 6)

    assert fetch_values(test_database_url, "SELECT count(*) FROM orders;") == [(0,)]
    assert fetch_values(
        test_database_url,
        "SELECT batch_code, quantity_available FROM inventory_batches ORDER BY expiry_date;",
    ) == [("EARLY", Decimal("2.000")), ("LATER", Decimal("3.000"))]
    assert fetch_values(test_database_url, "SELECT count(*) FROM activity_logs;") == [(0,)]


def test_reseller_fulfillment_is_approved_atomic_and_idempotent(test_database_url, order_database):
    order = repositories.create_order("reseller", order_database["product_id"], 4)

    with pytest.raises(ValueError, match="Approve the order"):
        repositories.decide_order(order["order_id"], "fulfill")

    assert repositories.decide_order(order["order_id"], "approve") is True
    assert repositories.decide_order(order["order_id"], "fulfill") is True
    assert repositories.decide_order(order["order_id"], "fulfill") is False

    assert fetch_values(
        test_database_url,
        "SELECT status, fulfilled_at IS NOT NULL FROM orders WHERE order_id = %s;",
        (order["order_id"],),
    ) == [("fulfilled", True)]
    assert fetch_values(
        test_database_url,
        "SELECT batch_code, quantity_available FROM inventory_batches ORDER BY expiry_date;",
    ) == [("EARLY", Decimal("0.000")), ("LATER", Decimal("1.000"))]
    assert fetch_values(
        test_database_url,
        "SELECT action FROM activity_logs WHERE entity_type = 'order' ORDER BY activity_log_id;",
    ) == [
        ("created_reseller_order",),
        ("approved_reseller_order",),
        ("fulfilled_reseller_order",),
    ]


def test_migrations_are_idempotent(test_database_url, order_database):
    assert apply_migrations(test_database_url) == []


def test_database_rejects_fulfillment_without_workflow_metadata(test_database_url, order_database):
    with psycopg2.connect(test_database_url) as connection:
        with connection.cursor() as cursor:
            with pytest.raises(psycopg2.errors.CheckViolation):
                cursor.execute(
                    """
                    INSERT INTO orders (order_type, status, total_amount)
                    VALUES ('walk_in', 'fulfilled', 0);
                    """
                )


def test_concurrent_fulfillment_deducts_inventory_once(test_database_url, order_database):
    order = repositories.create_order("reseller", order_database["product_id"], 4)
    assert repositories.decide_order(order["order_id"], "approve") is True

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(
            lambda _: repositories.decide_order(order["order_id"], "fulfill"),
            range(2),
        ))

    assert sorted(results) == [False, True]
    assert fetch_values(
        test_database_url,
        "SELECT sum(quantity_available) FROM inventory_batches;",
    ) == [(Decimal("1.000"),)]
    assert fetch_values(
        test_database_url,
        "SELECT count(*) FROM activity_logs WHERE action = 'fulfilled_reseller_order';",
    ) == [(1,)]
