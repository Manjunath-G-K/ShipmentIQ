# ShipmentIQ deployment and review runbook

GitHub URL: Not provided in this workspace.

Live application URL: Not deployed.

This runbook describes the reproducible local/demo deployment. It does not claim a production deployment, India-region hosting, legal compliance, or compatibility with a filing-software template that was not supplied.

## Prerequisites

- Python 3.12 or newer.
- Node.js and npm compatible with the frontend toolchain.
- Docker Desktop with Docker Compose, or an available PostgreSQL 15+ instance.
- Tesseract installed locally if scanned-image OCR is to be demonstrated. Embedded text PDFs use the bundled `pypdf` path.

## Local setup

1. From the repository root, set local-only values for the Compose variable names `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and optionally `POSTGRES_PORT`. The values must not be committed.

2. Start PostgreSQL:

   ```powershell
   docker compose up -d postgres
   docker compose ps
   ```

3. Create the backend environment:

   ```powershell
   Set-Location backend
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   Copy-Item .env.example .env
   ```

   Fill the local `.env` values for the variable names documented in `backend/.env.example`. At minimum, configure `DATABASE_URL` and `JWT_SECRET_KEY`. For local browser access, keep `AUTH_ALLOWED_ORIGINS` aligned with the frontend origin.

4. Apply all database migrations:

   ```powershell
   alembic upgrade head
   alembic current
   ```

   The expected head is `0006_review_validation`.

5. Seed synthetic reviewer accounts. Set local values for `SEED_DEMO_USERS`, `DEMO_EXECUTIVE_EMAIL`, `DEMO_EXECUTIVE_PASSWORD`, `DEMO_MANAGER_EMAIL`, and `DEMO_MANAGER_PASSWORD`, then run:

   ```powershell
   python -m app.scripts.seed_demo_users
   ```

   Password values are intentionally not documented or committed. The reviewer credentials are the values supplied through those environment variables.

6. Seed the labelled synthetic demo shipments and documents:

   ```powershell
   python -m app.scripts.seed_demo_data
   ```

   This creates or verifies `SHP-24811` and `SHP-24812` using private local storage and the configured provider adapters. It is disabled in production. The data is synthetic and marked inside the generated documents.

7. Start the API:

   ```powershell
   uvicorn app.main:app --reload
   ```

8. In another terminal, start the frontend:

   ```powershell
   Set-Location frontend
   npm install
   npm run dev
   ```

   Set `VITE_API_BASE_URL`, `VITE_CSRF_COOKIE_NAME`, and `VITE_CSRF_HEADER_NAME` only when the defaults do not match the backend configuration.

## Demo workflow

1. Sign in as the Documentation Executive using the locally configured executive credentials.
2. Open `SHP-24811`, view the invoice and packing list, and run validation. The synthetic data shows invoice gross weight `3,120 kg` versus packing-list gross weight `3,165 kg`; the system reports a discrepancy and does not choose a correct value.
3. Confirm or correct fields only after human review. A correction marks existing validation results `STALE`; run validation again before export. A rejected, missing, low-confidence, unresolved, stale, or failed field/check keeps export blocked.
4. Open `SHP-24812` to see the invoice-only sample. Comparisons without a second document remain unresolved and are not treated as passes.
5. Sign in as the Documentation Manager to review shipment data, validation evidence, revision history, and the accuracy report. Server-side RBAC remains authoritative even if a frontend control is hidden.

## Production-like deployment guidance

No production deployment is included in this repository. A deployment must provide HTTPS, a secret manager, private document storage, PostgreSQL backups, restricted logs, and a verified AI provider/data-use policy before it is treated as production-ready.

Configure these variable names through the platform secret/environment system:

- Backend: `ENVIRONMENT`, `DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_EXPIRE_MINUTES`, `AUTH_COOKIE_SECURE`, `AUTH_COOKIE_SAMESITE`, `AUTH_ALLOWED_ORIGINS`, `AUTH_COOKIE_NAME`, `AUTH_CSRF_COOKIE_NAME`, `AUTH_CSRF_HEADER_NAME`.
- Storage/limits: `DOCUMENT_STORAGE_PATH`, `DOCUMENT_MAX_SIZE_BYTES`.
- Extraction: `OCR_PROVIDER`, `EXTRACTION_AI_PROVIDER`, `EXTRACTION_AI_API_URL`, `EXTRACTION_AI_API_KEY`, `EXTRACTION_AI_MODEL`, `EXTRACTION_AI_TIMEOUT_SECONDS`, `EXTRACTION_LOW_CONFIDENCE_THRESHOLD`.
- Frontend build: `VITE_API_BASE_URL`, `VITE_CSRF_COOKIE_NAME`, `VITE_CSRF_HEADER_NAME`.

Keep `SEED_DEMO_USERS` disabled in production. Do not expose the private document directory through a static web server. Build the frontend with `npm run build` and serve `frontend/dist` through the chosen HTTPS frontend/server; run the FastAPI application behind the chosen HTTPS reverse proxy.

## Verification commands

```powershell
# Backend unit/default suite
Set-Location backend
.\.venv\Scripts\pytest.exe -q

# PostgreSQL integration suite
$env:RUN_DB_INTEGRATION = "1"
.\.venv\Scripts\pytest.exe -q

# Frontend
Set-Location ..\frontend
npm run test
npm run build
```

The actual filing-software CSV layout remains provisional because the client template was not supplied. ShipmentIQ prepares a documented CSV response; it does not submit to a customs portal or certify legal compliance.
