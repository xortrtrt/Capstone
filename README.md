# MEATTRACK Website

MEATTRACK is Batangas Premium's standalone, server-rendered web application for
public product information and role-based owner, team-leader, and reseller
workflows.

## Technology

- FastAPI and Uvicorn
- Jinja2 templates, HTML, CSS, and vanilla JavaScript
- PostgreSQL accessed server-side with psycopg2
- Docker Compose for local and Hostinger VPS operation
- Caddy for production HTTPS and reverse proxying

The application does not require a mobile runtime, JavaScript framework, managed
database platform, or database API exposed to browsers.

## Local development

Create a private environment file:

```powershell
Copy-Item .env.example .env
```

Replace every placeholder. For local access from Windows, change the hostname in
`DATABASE_URL` from `db` to `127.0.0.1` and use port `5433`.

Start PostgreSQL with its host-only development port:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml up -d db
```

Create the schema and sample classroom data. This command resets the selected
database, so use it only with a disposable development database:

```powershell
.venv\Scripts\python.exe tools\seed_database.py
```

Start FastAPI:

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. Bundled product images are served directly from
`app/static/img`; they are not duplicated inside PostgreSQL.

## Database migrations

The authoritative schema history is `database/migrations/`. Apply pending
migrations without deleting data:

```powershell
.venv\Scripts\python.exe tools\migrate_database.py
```

Applied migration checksums are stored in `schema_migrations`. Never modify an
applied migration; add the next numbered SQL file.

## Tests

Install development dependencies and point the tests at a disposable PostgreSQL
database whose name contains `test`:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:TEST_DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:5433/meattrack_test"
.venv\Scripts\python.exe -m pytest -q
```

The test suite resets `TEST_DATABASE_URL`. It refuses to run database integration
tests against a database without `test` in its name.

## Demo accounts

`tools/seed_database.py` creates owner, team-leader, and reseller accounts using
the development passwords from `.env`. It refuses to run when `APP_ENV` is
`production`. A new production database must use `tools/bootstrap_owner.py`,
which creates only the first owner and does not reset any data.

## Production deployment

The Compose stack keeps PostgreSQL private, gives FastAPI a dedicated non-superuser
database role, publishes only Caddy on ports 80 and 443, checks service health,
applies migrations before FastAPI starts, and persists PostgreSQL data in a named
volume.

See [deploy/README.md](deploy/README.md) for Hostinger VPS setup, firewall rules,
service startup, daily database backups, off-site replication, restore drills,
and updates.

## Current functions

- Public product, company, and reseller-partnership pages
- Database-backed login with PBKDF2 password hashing
- Reseller ordering, order history, reports, and messages
- Team-leader sales, inventory, production, inquiries, fulfillment, and reports
- Owner metrics, pricing, reports, forecasts, account administration, and logs
- Transactional FEFO inventory deduction for sales and fulfillment
- Optional OpenRouter-backed support chatbot with a local FAQ fallback
