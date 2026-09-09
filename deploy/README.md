# Hostinger VPS deployment

The production stack uses Docker Compose with three services:

- `caddy` terminates HTTPS and is the only public container;
- `app` runs FastAPI and applies pending PostgreSQL migrations before startup;
- `db` runs PostgreSQL on a private Docker network with persistent storage.

## First deployment

1. Point the domain's DNS records to the VPS.
2. Install Docker Engine and the Docker Compose plugin on the VPS.
3. Clone this repository to `/opt/meattrack`.
4. Copy `.env.example` to `.env`, replace every placeholder, and set `APP_DOMAIN`.
5. Ensure `APP_DB_PASSWORD` and the password embedded in `DATABASE_URL` match.
   The separate `POSTGRES_ADMIN_PASSWORD` is used only for database administration
   and backups; FastAPI connects as the non-superuser `APP_DB_USER`.
6. Start the stack with `docker compose up -d --build`.
7. Create initial classroom data only on a new database with
   `docker compose exec app python tools/seed_database.py`.
8. Confirm `https://YOUR_DOMAIN/health` returns `{"status":"ok"}`.

The PostgreSQL image reads `POSTGRES_*` and `APP_DB_*` initialization values only
when it creates an empty data volume. Changing those values later does not rotate
passwords in an existing database. For an established installation, change the
role password inside PostgreSQL first, update `.env` to the same value, and then
recreate the application container. Never delete the production volume as a
password-rotation shortcut.

Do not expose container port 5432 in production. The database initialization
script makes the application role the database owner without granting PostgreSQL
server administration. At the VPS firewall, allow only
SSH, HTTP, and HTTPS. Restrict SSH by source address when practical and disable
password-based root login after key-based access has been verified.

## Start at boot

Copy `deploy/meattrack.service` to `/etc/systemd/system/`, then run:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now meattrack.service
```

## Backups

`deploy/backup.sh` creates a compressed PostgreSQL custom-format dump and SHA-256
checksum. When `RESTIC_REPOSITORY` is configured it also sends the new dump to an
encrypted off-site Restic repository.

Create `/etc/meattrack/backup.env` with permissions `0600`:

```text
RESTIC_REPOSITORY=sftp:backup-user@backup-host:/srv/restic/meattrack
RESTIC_PASSWORD=replace_with_a_long_unique_password
RETENTION_DAYS=14
```

Install Restic, configure key-based access to the off-site host, copy the backup
service and timer to `/etc/systemd/system/`, and enable them:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now meattrack-backup.timer
sudo systemctl start meattrack-backup.service
sudo systemctl status meattrack-backup.service
```

The local dump directory is `/var/backups/meattrack`. VPS snapshots are useful,
but they are not a substitute for an independently stored database backup.

## Restore drill

Perform restore drills against a temporary database, never directly against the
production database. A typical check is:

```sh
docker compose exec db createdb -U "$POSTGRES_USER" meattrack_restore_test
docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d meattrack_restore_test --no-owner --no-privileges < /var/backups/meattrack/BACKUP.dump
docker compose exec db psql -U "$POSTGRES_USER" -d meattrack_restore_test -c "SELECT count(*) FROM accounts;"
docker compose exec db dropdb -U "$POSTGRES_USER" meattrack_restore_test
```

Record the date and result of each restore drill. Test again after schema changes
or backup tooling changes.

## Updating

Pull reviewed changes and rebuild:

```sh
git pull --ff-only
docker compose up -d --build
docker compose ps
```

The application startup command applies pending migrations under a PostgreSQL
advisory lock, so repeated starts are safe. Never edit a migration already listed
in `schema_migrations`; add a new numbered migration instead.
