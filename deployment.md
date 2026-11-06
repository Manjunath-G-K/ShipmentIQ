# ShipmentIQ deployment and reviewer runbook

Repository: https://github.com/Manjunath-G-K/ShipmentIQ<br>
Document status: implementation audit, November 2026

This guide uses environment variable names only. Never paste secrets, passwords, database URLs, or JWT keys into this file or the public repository.

## A. Live deployment first

### Public URLs

- Frontend: https://manjunath-g-k.github.io/ShipmentIQ/
- Backend health: https://shipmentiq.onrender.com/api/v1/health
- Backend API base: https://shipmentiq.onrender.com/api/v1

The frontend is hosted by GitHub Pages. The backend is running on Render; the live health endpoint returned HTTP 200 with {"status":"ok"} and Render/uvicorn infrastructure headers. The intended PostgreSQL deployment provider is Neon, as documented below, but the provider cannot be independently verified from public HTTP responses without deployment-console access.

### Current release status

Both public hosts were reachable during this audit. The Pages bundle still contains the pre-bootstrap document.cookie CSRF client, and the live backend returned 404 Not Found for /api/v1/auth/csrf. The corrected local CSRF implementation is not live until the backend is redeployed and the Pages workflow publishes a new bundle.

The separate GitHub Pages and Render sites rely on cross-site cookies. Production requires secure cookies and SameSite=None; browser privacy modes may still block third-party cookies. Render's free tier may sleep between requests, causing cold-start latency.

## B. Local setup - exact end-to-end steps

### Prerequisites

- Windows with PowerShell.
- Docker Desktop with Docker Compose v2.
- Python 3.12 or newer.
- Node.js 20 and npm, matching the GitHub Pages workflow.
- Git.
- Optional for scanned-document OCR: Tesseract executable on PATH. The Python wrapper is installed by backend/requirements.txt; the executable is not.

### Clone and create private environment files

~~~powershell
git clone https://github.com/Manjunath-G-K/ShipmentIQ.git
Set-Location .\ShipmentIQ
Copy-Item .env.example .env
Copy-Item .\backend\.env.example .\backend\.env
~~~

Configure local values privately. The root .env supplies POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, and optional POSTGRES_PORT for Compose. The backend .env supplies DATABASE_URL, JWT_SECRET_KEY, and application settings. For local HTTP, use the localhost/loopback cookie and Origin settings from the examples. Do not put real customer information in the database or sample documents.

### Create the backend environment and install dependencies

~~~powershell
py -3.12 -m venv .\backend\.venv
& .\backend\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
~~~

The launcher expects backend\.venv\Scripts\python.exe to exist. Use one supported Python version consistently for the virtual environment.

### Start PostgreSQL and apply migrations

~~~powershell
docker compose up -d postgres
Set-Location .\backend
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m alembic current
~~~

The Compose service is postgres and binds only to local loopback. The migration head is 0006_review_validation.

### Provision synthetic demo users and optional demo shipments

The supported seeder is environment-driven and idempotent. Set SEED_DEMO_USERS, DEMO_EXECUTIVE_EMAIL, DEMO_EXECUTIVE_PASSWORD, DEMO_MANAGER_EMAIL, and DEMO_MANAGER_PASSWORD privately, then run:

~~~powershell
& .\.venv\Scripts\python.exe -m app.scripts.seed_demo_users
~~~

For labelled synthetic documents and two demo shipments, run the optional local-only seeder while ENVIRONMENT is not production:

~~~powershell
& .\.venv\Scripts\python.exe -m app.scripts.seed_demo_data
~~~

The seeders refuse production mode. Remove temporary seeding values or set SEED_DEMO_USERS false before serving publicly. Demo passwords are intentionally not documented here.

### Start the backend

From backend in one PowerShell terminal:

~~~powershell
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
~~~

Verify:

- API liveness: http://localhost:8000/api/v1/health
- API readiness: http://localhost:8000/api/v1/health/ready
- OpenAPI UI: http://localhost:8000/docs

### Start the frontend

In a second PowerShell terminal:

~~~powershell
Set-Location .\frontend
npm ci
npm run dev -- --host localhost
~~~

Open http://localhost:5173. The default API base follows the browser's localhost/loopback hostname. Keep frontend and API hostnames consistent because cookies are host-only.

The repository launcher performs the same local startup after prerequisites exist:

~~~powershell
Set-Location .\ShipmentIQ
.\start-shipmentiq.bat
~~~

### Stop local services safely

~~~powershell
Set-Location .\ShipmentIQ
.\stop-shipmentiq.bat
~~~

The stop script terminates only recorded ShipmentIQ launcher process trees and runs docker compose stop postgres. It preserves the named PostgreSQL volume. Do not use destructive volume-removal commands.

## C. Deployment architecture and procedure

### GitHub Pages frontend

The workflow .github/workflows/deploy-pages.yml runs on pushes to main and manual dispatch. It uses Ubuntu and Node.js 20, builds from frontend with npm ci and npm run build, sets Vite base /ShipmentIQ/, reads repository variable VITE_API_BASE_URL, uploads frontend/dist, and deploys with official Pages actions.

Required repository variable name:

- VITE_API_BASE_URL

The value must be the public backend API base with /api/v1 appended. Do not put credentials or secrets in it. Deployment is triggered by pushing to main or manually running the workflow.

### Render backend

Documented Render Web Service configuration:

- Root directory: backend
- Build command: pip install -r requirements.txt
- Start command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
- Health check: /api/v1/health/ready
- Liveness: /api/v1/health

The service receives backend environment names through Render protected settings. DATABASE_URL must use the postgresql+psycopg:// SQLAlchemy scheme and the PostgreSQL provider must require TLS as appropriate. This runbook documents Neon as the intended managed PostgreSQL provider; verify the actual Render/Neon dashboard settings before release.

### Backend environment variable names

~~~text
APP_NAME
ENVIRONMENT
API_V1_PREFIX
LOG_LEVEL
DATABASE_URL
DB_CONNECT_TIMEOUT
JWT_SECRET_KEY
JWT_ALGORITHM
JWT_ISSUER
JWT_AUDIENCE
JWT_EXPIRE_MINUTES
AUTH_COOKIE_NAME
AUTH_COOKIE_SECURE
AUTH_COOKIE_SAMESITE
AUTH_CSRF_COOKIE_NAME
AUTH_CSRF_HEADER_NAME
AUTH_ALLOWED_ORIGINS
SEED_DEMO_USERS
DEMO_EXECUTIVE_EMAIL
DEMO_EXECUTIVE_PASSWORD
DEMO_MANAGER_EMAIL
DEMO_MANAGER_PASSWORD
DOCUMENT_STORAGE_PATH
DOCUMENT_MAX_SIZE_BYTES
OCR_PROVIDER
EXTRACTION_AI_PROVIDER
EXTRACTION_AI_API_URL
EXTRACTION_AI_API_KEY
EXTRACTION_AI_MODEL
EXTRACTION_AI_TIMEOUT_SECONDS
EXTRACTION_LOW_CONFIDENCE_THRESHOLD
~~~

For separate HTTPS Pages and Render origins, production must use production mode, secure cookies, SameSite=None, and an exact AUTH_ALLOWED_ORIGINS value containing the Pages origin without a path or trailing slash. Keep allow_credentials enabled. Do not use wildcard origins, disable CSRF, or expose the JWT cookie to JavaScript.

### Frontend build variable names

~~~text
VITE_API_BASE_URL
VITE_BASE_PATH
VITE_CSRF_COOKIE_NAME
VITE_CSRF_HEADER_NAME
~~~

The corrected client bootstraps CSRF through the authenticated API and keeps the returned token in memory. It does not read the cross-origin CSRF cookie directly. VITE_CSRF_HEADER_NAME must match the backend header name. VITE_CSRF_COOKIE_NAME remains in the example for compatibility but is not used by the corrected client to read cookies.

### Database and migrations

Run Alembic against an isolated target database before serving traffic. The current migration head is 0006_review_validation. Do not run migration or seeding commands against an unknown or production database without an approved release procedure. Demo-user seeding is disabled in production by application validation; provision reviewer accounts through a controlled administrative process and keep passwords out of Git.

The initial Render configuration stores documents on the local filesystem under DOCUMENT_STORAGE_PATH. Render's ephemeral filesystem can lose uploads after restart or redeployment. Durable private object storage, retention, backup, and restore procedures are required before production use.

## D. Reviewer access

### Roles

- Documentation Executive: shipment intake, own-shipment operations, uploads, corrections, extraction, validation, and export when eligible.
- Documentation Manager: cross-shipment review, confirmation/rejection, validation, and accuracy reporting.

### Reviewer credentials - pending explicit confirmation

The local environment files were not read, and no safe public reviewer credential source was available during this audit. Do not invent credentials or commit passwords.

Before producing a reviewer-ready private copy, fill these placeholders only after explicit confirmation:

- Documentation Executive email: [FILL AFTER OWNER CONFIRMS]
- Documentation Manager email: [FILL AFTER OWNER CONFIRMS]
- Password delivery: private channel only; never commit passwords to the public repository

The ZIP prepared from this workspace intentionally contains no passwords.

## E. Troubleshooting

### PostgreSQL, migrations, or readiness

- Confirm Docker Desktop and Compose v2 are running.
- Check docker compose ps for postgres health.
- Confirm DATABASE_URL uses postgresql+psycopg:// and matches Compose names/port.
- Run Alembic from backend with the virtual environment active.
- Use /api/v1/health for liveness and /api/v1/health/ready for database readiness.

### Backend or frontend startup

- Confirm backend\.venv\Scripts\python.exe exists and requirements are installed.
- Confirm node_modules exists before using the batch launcher.
- Check ports 8000 and 5173.
- Inspect the terminal that owns the process.

### CORS, CSRF, and cross-site cookies

- The API must allow the exact Pages origin and credentials; wildcard origins cannot be used with credentialed cookies.
- Production cookies require Secure and SameSite=None for separate Pages/Render sites.
- The corrected client calls authenticated GET /api/v1/auth/csrf; a 404 means the backend predates the local fix.
- If authentication works but writes fail, inspect X-CSRF-Token, the backend CSRF cookie, and exact Origin.
- Privacy modes may block third-party cookies entirely and can prevent the workspace from loading.

### OCR and extraction

- Embedded PDF text extraction does not require Tesseract.
- Scanned PDFs/images require PyMuPDF, Pillow, and Tesseract executable.
- Missing executable or unreadable pages become safe failure/needs-review states.
- The default provider is labelled-text parsing; the optional OpenAI-compatible provider requires explicit settings.

### Render cold starts and storage

- The free tier may sleep; allow time for the first request.
- Do not treat local Render storage as durable. Move to approved private object storage before relying on document retention.
