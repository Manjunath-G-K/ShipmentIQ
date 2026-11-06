# ShipmentIQ Backend

FastAPI backend for the ShipmentIQ engineering take-home project.

This milestone includes:

- FastAPI application setup;
- environment-based settings with PostgreSQL URL validation;
- SQLAlchemy 2.x engine and request-scoped session dependency;
- Alembic migration configuration;
- liveness endpoint: `GET /api/v1/health`;
- PostgreSQL readiness endpoint: `GET /api/v1/health/ready`;
- cookie-based JWT authentication and server-side role checks;
- shipment create, list, detail, and metadata-update endpoints with object-level authorization;
- private shipment document upload, list, and authorized download endpoints for invoices, packing lists, and bills of lading;
- provider-neutral OCR and structured extraction endpoints with multi-page provenance, field confidence, and PostgreSQL-backed processing status;
- deterministic cross-document validation, human review actions, field revision history, and manager accuracy reports;
- consistent JSON error responses with request IDs; and
- Pytest coverage for authentication, shipments, health, configuration, and PostgreSQL integration.

The React review UI is in `frontend/`. Customs filing is not included. Extraction is proposed data only and never approves or verifies a shipment.

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

From the repository root, set local-only values in the current PowerShell session and start PostgreSQL. Never copy those values into Git or public documentation:

```powershell
$env:POSTGRES_DB = "shipmentiq"
$env:POSTGRES_USER = "shipmentiq_dev"
$env:POSTGRES_PASSWORD = "<local-only-value>"
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

Set the `DATABASE_URL` variable using the local connection details. If `POSTGRES_PORT` is set, use that host port. The database can be stopped while preserving its data with:

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
$env:DEMO_EXECUTIVE_EMAIL = "<separately-provided-demo-email>"
$env:DEMO_EXECUTIVE_PASSWORD = "<separately-provided-demo-password>"
$env:DEMO_MANAGER_EMAIL = "<separately-provided-demo-email>"
$env:DEMO_MANAGER_PASSWORD = "<separately-provided-demo-password>"
python -m app.scripts.seed_demo_users
```

The command is explicit and idempotent: it creates or reconciles the two synthetic users and required roles without printing passwords. Use separately provided synthetic credentials of at least eight characters; keep their values out of Git and public documentation.

To seed the labelled synthetic reviewer workflow after migrations and demo users are ready, run `python -m app.scripts.seed_demo_data`. This creates or verifies `SHP-24811` with the required 45 kg invoice/packing-list discrepancy and `SHP-24812` as an invoice-only sample. It is disabled in production and does not contain real credentials or personal data.

The foundation includes `/api/v1/auth/rbac/executive` and `/api/v1/auth/rbac/manager` as small protected RBAC boundary checks. They are disabled in production and are not shipment functionality.

## Shipment management

The current shipment API provides:

- `POST /api/v1/shipments` — Documentation Executive only; creates a `DRAFT` shipment;
- `GET /api/v1/shipments` — Executive sees owned shipments, Manager sees all authorized shipments; supports `limit`, `offset`, and `status`;
- `GET /api/v1/shipments/{shipment_id}` — object-scoped detail access; and
- `PATCH /api/v1/shipments/{shipment_id}` — Executive-only update of shipment metadata they own.

Shipment status is server-managed and cannot be supplied through create or update payloads. All cookie-authenticated state-changing requests require the configured Origin and CSRF header protections. Shipment references are normalized and unique.

## Shipment documents

The document API provides:

- `POST /api/v1/shipments/{shipment_id}/documents` — Documentation Executive only; accepts one `INVOICE`, `PACKING_LIST`, or `BILL_OF_LADING` upload;
- `GET /api/v1/shipments/{shipment_id}/documents` — authorized shipment-scoped metadata list; and
- `GET /api/v1/shipments/{shipment_id}/documents/{document_id}/download` — authorized private-file download.
- `POST /api/v1/shipments/{shipment_id}/documents/{document_id}/extract` — authorized OCR and structured extraction; returns `NEEDS_REVIEW` for missing/unreadable values.
- `GET /api/v1/shipments/{shipment_id}/documents/{document_id}/extraction` — authorized persisted extraction result/status.

Uploads are limited by `DOCUMENT_MAX_SIZE_BYTES` (10 MiB by default), validated by file content as well as extension, and stored under `DOCUMENT_STORAGE_PATH` using generated names. The path is application-private and is not mounted as a public web directory. One document of each type is allowed per shipment. Executive users can only upload to their own shipments; managers can list and download documents for all shipments but cannot upload.

## OCR and extraction providers

The default `OCR_PROVIDER=local` uses `pypdf` for embedded text and local Tesseract OCR through PyMuPDF/Pillow for scanned PDF pages and JPG/PNG files. Install the Tesseract executable separately and keep its language data local; an unreadable page remains visible as `NEEDS_REVIEW` rather than receiving invented values. The default `EXTRACTION_AI_PROVIDER=local` is a free, conservative labelled-text parser that only accepts explicitly labelled values. An OpenAI-compatible provider can be selected only with `EXTRACTION_AI_PROVIDER=openai_compatible`, `EXTRACTION_AI_API_URL`, and `EXTRACTION_AI_API_KEY` configured. No API key or paid provider is required for the default path.

Every accepted value carries a confidence score and page/locator source references. Provider responses are rejected if they fail the strict Pydantic extraction schema; failures are persisted as `FAILED` with a safe error code. A successful extraction with missing values or unreadable pages is `NEEDS_REVIEW` and never changes a shipment to an approval/export state.

## Validation and human review

Part 2 provides:

- `GET /api/v1/shipments/{shipment_id}/review` for document fields, confidence/source data, and missing, unreadable, low-confidence, rejected, or unconfirmed flags;
- `POST /api/v1/shipments/{shipment_id}/validations/run` and `GET /api/v1/shipments/{shipment_id}/validations` for invoice total versus line items, package counts, and gross/net-weight comparisons;
- `PATCH /api/v1/fields/{field_id}` for executive corrections/manual entry;
- `POST /api/v1/fields/{field_id}/confirm`, `POST /api/v1/fields/{field_id}/reject`, and `GET /api/v1/fields/{field_id}/revisions` for human decisions and append-only actor/timestamp history; and
- `GET /api/v1/reports/accuracy` for manager-only field and shipment-supplier metrics.

Comparisons with fewer than two available document values remain `UNRESOLVED`. Numeric comparisons use exact normalized values because the brief does not supply tolerances. Any correction or rejection marks prior validation results `STALE`; validation must be explicitly rerun. Accuracy is transparent and conservative: confirmed fields without a correction count as correct, corrected fields count as incorrect initial extraction, and rejected fields count as incorrect; unresolved/unreviewed fields are excluded.

## Provisional CSV export

Part 3 exposes `GET /api/v1/shipments/{shipment_id}/export-eligibility` for executive/manager review and `POST /api/v1/shipments/{shipment_id}/exports` for Documentation Executive export. Eligibility is enforced in the backend and requires an invoice, completed/readable extraction, present required fields, no rejected or low-confidence populated fields, human confirmation of populated fields, and every deterministic validation rule in `PASSED` state. Missing, failed, unresolved, stale, rejected, or low-confidence data blocks the export; the frontend cannot bypass this gate.

The client's actual filing-software template was not supplied, so the current CSV is explicitly provisional. It has one row per invoice line item and these columns: `shipment_reference`, `importer`, `supplier`, `origin_country`, `invoice_number`, `invoice_date`, `currency`, `incoterm`, `invoice_total`, `item_description`, `quantity`, `unit_price`, `hsn_code`, `packages`, `gross_weight_kg`, `net_weight_kg`, and `containers`. No customs filing or automatic approval is performed. The CSV response marks the shipment `EXPORTED`; it does not add a separate export-attempt table or migration.

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

The migrations create the Alembic version table, authentication tables (`users`, `roles`, and `user_roles`), the `shipments` table, the `shipment_documents` metadata table, document extraction results, and review/validation/revision tables through migration `0006_review_validation`. Files remain outside PostgreSQL and are replaceable through the private storage adapter. Confirm the migration state with:

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

The integration tests check the migrated schema, shipment authorization and validation behavior, and a rollback-safe insert/retrieve transaction. The readiness behavior tests also verify HTTP 503 with a safe error payload when the database boundary reports that PostgreSQL is unavailable; the real database readiness check returns HTTP 200 when PostgreSQL is reachable.
