# ShipmentIQ Backend

Initial FastAPI foundation for the ShipmentIQ engineering take-home project.

This milestone includes:

- FastAPI application setup;
- environment-based settings with PostgreSQL URL validation;
- SQLAlchemy 2.x engine and request-scoped session dependency;
- Alembic migration configuration;
- liveness endpoint: `GET /api/v1/health`;
- PostgreSQL readiness endpoint: `GET /api/v1/health/ready`;
- cookie-based JWT authentication and server-side role checks;
- consistent JSON error responses with request IDs; and
- Pytest coverage for health, configuration, and database-readiness behavior.

No shipment, document, or AI business logic is included yet.

## Prerequisites

- Python 3.12 or newer;
- Docker Desktop with Docker Compose, or another running PostgreSQL 15+ instance; and
- access to install the pinned dependencies from `requirements.txt`.

SQLite is intentionally unsupported.

## Local setup

From the repository root:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`backend/.env` is ignored by Git. Update `DATABASE_URL` in it with the PostgreSQL connection string for the local instance. Do not commit `.env`.

Authentication also requires `JWT_SECRET_KEY` to be set to a long, local-only random value. In production, set `ENVIRONMENT=production` and `AUTH_COOKIE_SECURE=true`. Keep the JWT secret and demo passwords out of Git.

## Local PostgreSQL with Docker Compose

The root `docker-compose.yml` contains only PostgreSQL. It requires the database credentials to be supplied through environment variables and stores data in the named `shipmentiq-postgres-data` volume.

From the repository root, set safe development-only values in the current PowerShell session and start PostgreSQL:

```powershell
$env:POSTGRES_DB = "shipmentiq"
$env:POSTGRES_USER = "shipmentiq_dev"
$env:POSTGRES_PASSWORD = "change-me-locally"
# If port 5432 is already in use, set this to an available host port, e.g. 55432.
# $env:POSTGRES_PORT = "55432"
docker compose up -d postgres
docker compose ps
```

Configure `backend/.env` to match the values used for the Compose session:

```powershell
Set-Location backend
Copy-Item .env.example .env
```

Then set `DATABASE_URL` in `backend/.env` to:

```text
postgresql+psycopg://shipmentiq_dev:change-me-locally@localhost:5432/shipmentiq
```

The password above is only a local placeholder. Replace it with another local-only value if desired; keep it out of Git. If `POSTGRES_PORT` is set, use that host port in `DATABASE_URL` (for example, `55432` in place of `5432`). The database can be stopped while preserving its data with:

```powershell
docker compose stop postgres
```

Start it again with `docker compose start postgres`. To stop and remove the container while preserving the named volume, use `docker compose down`. Do not use `docker compose down -v` unless the local database should be reset.

## Run the API

```powershell
uvicorn app.main:app --reload
```

The interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

## Authentication and demo users

Login uses a short-lived JWT in an HttpOnly cookie and a separate non-HttpOnly CSRF cookie. State-changing authentication requests must include both an allowed `Origin` header and the CSRF value in the configured `X-CSRF-Token` header. Roles are loaded from PostgreSQL for every protected request; JWT role claims are not trusted.

There is no public registration endpoint. To seed synthetic development users, set the following environment variables in the current PowerShell session after copying `.env.example` to `.env`:

```powershell
$env:SEED_DEMO_USERS = "true"
$env:DEMO_EXECUTIVE_EMAIL = "executive@example.test"
$env:DEMO_EXECUTIVE_PASSWORD = "replace-with-a-local-demo-password"
$env:DEMO_MANAGER_EMAIL = "manager@example.test"
$env:DEMO_MANAGER_PASSWORD = "replace-with-a-local-demo-password"
python -m app.scripts.seed_demo_users
```

The command is explicit and idempotent: it creates or reconciles the two synthetic users and required roles without printing passwords. Replace the example passwords with local-only values of at least eight characters.

The foundation includes `/api/v1/auth/rbac/executive` and `/api/v1/auth/rbac/manager` as small protected RBAC boundary checks. They are verification endpoints for this milestone, not shipment functionality.

## Health checks

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready
```

The liveness endpoint does not require PostgreSQL. The readiness endpoint executes `SELECT 1` using the configured PostgreSQL engine and returns HTTP 503 with a safe error payload when the database is unavailable.

## Migrations

After PostgreSQL is configured:

```powershell
alembic upgrade head
```

The migrations create the Alembic version table plus the authentication tables (`users`, `roles`, and `user_roles`). Future milestones should add revisions for their own persistence models. Confirm the migration state with:

```powershell
alembic current
```

## Tests

```powershell
pytest -q
```

The default suite does not substitute SQLite for PostgreSQL. After PostgreSQL is running, set `RUN_DB_INTEGRATION=1` and run the opt-in integration test against the configured `DATABASE_URL`:

```powershell
$env:RUN_DB_INTEGRATION = "1"
pytest -q
```

The integration test checks the migrated schema, performs an insert/retrieve in a transaction, and rolls the transaction back. The readiness behavior tests also verify HTTP 503 with a safe error payload when the database boundary reports that PostgreSQL is unavailable; the real database readiness check returns HTTP 200 when PostgreSQL is reachable.
