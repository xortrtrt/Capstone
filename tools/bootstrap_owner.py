from __future__ import annotations

import argparse
import getpass
import re
import sys
from pathlib import Path

import psycopg2


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import DATABASE_URL, database_dsn
from app.security import hash_password


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
BOOTSTRAP_LOCK_KEY = "meattrack-bootstrap-owner"


def bootstrap_owner(dsn: str, name: str, email: str, password: str) -> bool:
    """Create the first owner account without resetting any application data.

    Returns True when an account is created and False when the same active owner
    already exists. A different existing owner must be handled explicitly in the
    owner portal instead of silently granting another privileged account.
    """
    clean_name = name.strip()
    clean_email = email.strip().lower()
    if len(clean_name) < 2:
        raise ValueError("Owner name must contain at least 2 characters.")
    if not EMAIL_RE.fullmatch(clean_email):
        raise ValueError("Enter a valid owner email address.")
    if len(password) < 12:
        raise ValueError("Owner password must contain at least 12 characters.")

    with psycopg2.connect(database_dsn(dsn)) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s));", (BOOTSTRAP_LOCK_KEY,))
            cursor.execute(
                """
                SELECT account_id, account_type, is_active
                FROM accounts
                WHERE lower(email) = lower(%s)
                FOR UPDATE;
                """,
                (clean_email,),
            )
            existing = cursor.fetchone()
            if existing is not None:
                _, account_type, is_active = existing
                if account_type != "owner":
                    raise ValueError("That email already belongs to a non-owner account.")
                if not is_active:
                    raise ValueError("That owner account exists but is inactive.")
                return False

            cursor.execute(
                "SELECT email FROM accounts WHERE account_type = 'owner' FOR UPDATE;"
            )
            owner = cursor.fetchone()
            if owner is not None:
                raise ValueError(
                    "An owner already exists. Create additional accounts from the owner portal."
                )

            cursor.execute(
                """
                INSERT INTO accounts (account_type, name, email, password_hash, is_active)
                VALUES ('owner', %s, %s, %s, true)
                RETURNING account_id;
                """,
                (clean_name, clean_email, hash_password(password)),
            )
            account_id = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO activity_logs (account_id, action, entity_type, entity_id)
                VALUES (%s, 'bootstrapped_owner', 'account', %s);
                """,
                (account_id, account_id),
            )
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create the first production owner without resetting the database."
    )
    parser.add_argument("--name", required=True, help="Owner display name")
    parser.add_argument("--email", required=True, help="Owner login email")
    args = parser.parse_args()

    password = getpass.getpass("Owner password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm owner password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match; no account was created.")

    try:
        created = bootstrap_owner(DATABASE_URL, args.name, args.email, password)
    except (ValueError, psycopg2.Error) as exc:
        raise SystemExit(f"Owner bootstrap failed: {exc}") from exc

    if created:
        print("Initial owner account created successfully.")
    else:
        print("The requested active owner account already exists; no changes made.")


if __name__ == "__main__":
    main()
