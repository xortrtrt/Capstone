# MEATTRACK PostgreSQL database

`migrations/` is the authoritative, ordered PostgreSQL schema history. The
application records applied filenames and SHA-256 checksums in
`schema_migrations`.

Apply pending migrations with:

```powershell
.venv\Scripts\python.exe tools\migrate_database.py
```

For a disposable local database, `tools/seed_database.py` drops and recreates the
`public` schema, applies all migrations, and inserts classroom sample data.

The schema covers:

- accounts and activity logs;
- departments and reseller onboarding;
- inventory items, FEFO batches, recipes, and alerts;
- orders, order items, and sales reports;
- forecast runs and results.

PostgreSQL constraints protect basic values and relationships. The FastAPI
application performs workflow transactions, including row locking, stock checks,
FEFO batch deduction, order state changes, and audit-log insertion. Foreign-key
columns used for joins or cascading operations are indexed in the baseline.

To change the schema, add a new file such as `002_descriptive_name.sql`. Do not
edit a migration after it has been applied to a shared database.
