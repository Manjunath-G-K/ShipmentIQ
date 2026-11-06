# ShipmentIQ deployment and review runbook

Repository: https://github.com/Manjunath-G-K/ShipmentIQ

Live application URL: not verified; update this placeholder only after a real GitHub Pages and Render smoke test.

Demo credentials are provided separately. They are not stored in this repository or this document.

## Local Windows demonstration

Prerequisites: Python 3.12+, Node.js/npm, Docker Desktop with Compose v2, and the dependencies installed in `backend/.venv` and `frontend/node_modules`.

1. Copy `backend/.env.example` to the ignored `backend/.env`.
2. Set local-only values for the variable names in that file, including `DATABASE_URL` and `JWT_SECRET_KEY`. Do not commit `.env`.
3. Set the Compose variable names `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and optionally `POSTGRES_PORT` in the local environment.
4. Run `start-shipmentiq.bat` from the repository root. It starts only the PostgreSQL Compose service and opens separate backend/frontend terminals.
5. Apply migrations from `backend` with `alembic upgrade head`, then check `alembic current`.
6. Seed the two synthetic demo accounts by setting `SEED_DEMO_USERS`, `DEMO_EXECUTIVE_EMAIL`, `DEMO_EXECUTIVE_PASSWORD`, `DEMO_MANAGER_EMAIL`, and `DEMO_MANAGER_PASSWORD` locally, then run `python -m app.scripts.seed_demo_users`.
7. Optionally seed the labelled synthetic shipment workflow with `python -m app.scripts.seed_demo_data`.
8. Use `stop-shipmentiq.bat` to stop only the launcher process trees and the PostgreSQL service. It never removes the named volume.

The launcher URLs are:

- Frontend: `http://127.0.0.1:5173`
- Health: `http://127.0.0.1:8000/api/v1/health`
- Swagger: `http://127.0.0.1:8000/docs`

The synthetic review case `SHP-24811` contains invoice gross weight 3,120 kg and packing-list gross weight 3,165 kg. The expected 45 kg discrepancy is surfaced for human review; the system does not choose a correct value.

## Required environment variable names

Backend settings are defined in `backend/app/core/config.py` and listed in `backend/.env.example`. Configure only through the local environment or the deployment platform:

`APP_NAME`, `ENVIRONMENT`, `API_V1_PREFIX`, `LOG_LEVEL`, `DATABASE_URL`, `DB_CONNECT_TIMEOUT`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_EXPIRE_MINUTES`, `AUTH_COOKIE_NAME`, `AUTH_COOKIE_SECURE`, `AUTH_COOKIE_SAMESITE`, `AUTH_CSRF_COOKIE_NAME`, `AUTH_CSRF_HEADER_NAME`, `AUTH_ALLOWED_ORIGINS`, `SEED_DEMO_USERS`, `DEMO_EXECUTIVE_EMAIL`, `DEMO_EXECUTIVE_PASSWORD`, `DEMO_MANAGER_EMAIL`, `DEMO_MANAGER_PASSWORD`, `DOCUMENT_STORAGE_PATH`, `DOCUMENT_MAX_SIZE_BYTES`, `OCR_PROVIDER`, `EXTRACTION_AI_PROVIDER`, `EXTRACTION_AI_API_URL`, `EXTRACTION_AI_API_KEY`, `EXTRACTION_AI_MODEL`, `EXTRACTION_AI_TIMEOUT_SECONDS`, and `EXTRACTION_LOW_CONFIDENCE_THRESHOLD`.

Frontend build variables are `VITE_API_BASE_URL`, `VITE_BASE_PATH`, `VITE_CSRF_COOKIE_NAME`, and `VITE_CSRF_HEADER_NAME`. The frontend must never receive a secret; `VITE_API_BASE_URL` is only a public backend origin.

## Neon PostgreSQL

1. Create a Neon PostgreSQL project and database.
2. Copy the Neon-provided connection string into the deployment platform's `DATABASE_URL` setting only. Require SSL using the connection-string option supplied by Neon; never commit or paste the value into documentation.
3. Run `alembic upgrade head` from the `backend` directory with the deployment environment loaded, then verify `alembic current` reports `0006_review_validation`.
4. Provision the two synthetic demo accounts through a controlled, non-public administrative operation using the variable names above. Public registration is not implemented.

## Render backend

Create a Web Service connected to this repository with:

- Root directory: `backend`
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/api/v1/health`

Set the backend environment variable names listed above. For a cross-site GitHub Pages frontend, use `ENVIRONMENT=production`, `AUTH_COOKIE_SECURE=true`, `AUTH_COOKIE_SAMESITE=none`, and set `AUTH_ALLOWED_ORIGINS` to the exact Pages origin without a path. Keep `allow_credentials` enabled; do not weaken CSRF or CORS. Set the frontend's `VITE_API_BASE_URL` to the Render backend URL with `/api/v1` appended; the client appends route paths after that base.

Verify browser cookie behavior manually after both hosts are live. Some browsers or privacy modes may block third-party cookies even with correct `Secure`/`SameSite=None` settings; that is a deployment compatibility constraint, not a reason to disable CSRF.

Render's free tier may sleep between requests. Its local filesystem is ephemeral, so uploaded documents stored under `DOCUMENT_STORAGE_PATH` can disappear after restart or redeployment. Cloud file storage is intentionally not integrated in this initial deployment; do not claim permanent document retention or production readiness.

## GitHub Pages frontend

The workflow `.github/workflows/deploy-pages.yml` builds only `frontend` with Node 20, uses `/ShipmentIQ/` as the Vite base path, uploads `frontend/dist`, and deploys with the official Pages actions. Before running it, create the repository variable `VITE_API_BASE_URL` with the deployed backend origin. No backend files, private storage, `.env` files, or test fixtures are included in the artifact.

The expected Pages URL is `https://manjunath-g-k.github.io/ShipmentIQ/`, but it remains unverified until a successful GitHub Actions run and browser smoke test.

## Verification commands

```powershell
Set-Location backend
.\.venv\Scripts\pytest.exe -q
$env:DATABASE_URL = '<isolated-test-database-url>'
$env:RUN_DB_INTEGRATION = '1'
.\.venv\Scripts\pytest.exe -q
alembic upgrade head
alembic current

Set-Location ..\frontend
npm run test
npm run build
```

Never run integration tests against an unknown or production database. The current CSV layout is explicitly provisional because the client's filing-software template was not supplied. ShipmentIQ does not submit customs filings or certify regulatory compliance.
