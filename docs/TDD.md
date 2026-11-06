**GitHub:** https://github.com/Manjunath-G-K/ShipmentIQ<br>
**Live application:** https://manjunath-g-k.github.io/ShipmentIQ/<br>
**Backend health endpoint:** https://shipmentiq.onrender.com/api/v1/health

# ShipmentIQ Technical Design Document

**Document status:** Implementation audit, November 2026<br>
**Repository:** ShipmentIQ

> Release note: the public Pages site and Render health endpoint are reachable. At audit time the deployed frontend bundle still contained the pre-bootstrap CSRF client and the deployed API returned 404 for /api/v1/auth/csrf. The corrected CSRF implementation is present locally and must be deployed before the live app is described as fixed.

## Executive summary

ShipmentIQ is a customs-broker documentation workbench for Documentation Executives and Documentation Managers. It turns private invoice, packing-list, and bill-of-lading uploads into structured, reviewable shipment data. The source document remains visible beside extracted fields, with confidence and page/locator evidence. Reviewers can compare values across documents, record human decisions, and request a backend-gated provisional CSV.

The problem is a manual, error-prone handoff: a broker reads several documents, re-keys shipment values, notices mismatches, resolves uncertain fields, and prepares a filing-software import. ShipmentIQ makes these steps explicit and auditable. It does not file customs entries, classify HSN codes, calculate duty, provide importer tracking, or certify regulatory compliance.

| Verification item | Result |
|---|---|
| Public repository | Verified remote points to the GitHub URL above |
| Frontend host | GitHub Pages returned HTTP 200 |
| Backend host | Render health returned HTTP 200 and {"status":"ok"} |
| CORS | Pages origin allowed; unrelated origin rejected |
| CSRF bootstrap release | Not live; live endpoint returned 404 |
| Database provider | Neon is documented, but not independently verifiable publicly |

## 1. Problem, users, and scope

### User roles

| Role | Implemented responsibilities |
|---|---|
| Documentation Executive | Sign in, create/update own shipments, upload documents, run extraction, correct fields, confirm/reject fields, run validation, and request eligible CSV export |
| Documentation Manager | View all shipments in scope, review documents and fields, confirm/reject fields, run validation, and view field/supplier Unchanged Extraction Rate |

The server reloads roles from PostgreSQL for every protected request. A hidden frontend button is not authorization.

### Core build

1. Shipment list, creation, and metadata update.
2. Private upload of one invoice, packing list, and bill of lading per shipment.
3. Synchronous OCR/text extraction and structured field materialization.
4. Side-by-side source viewer and extracted-field review.
5. Confidence, source-page/locator references, missing/unreadable flags, and revision history.
6. Deterministic invoice-total, package, gross-weight, and net-weight checks.
7. Human correction, confirmation, rejection, stale-validation handling, and export eligibility.
8. Provisional CSV export and manager reporting.

## 2. Architecture

### Modular monolith rationale

One FastAPI process owns authentication, authorization, transactions, document handling, extraction orchestration, review, validation, reporting, and export. This fits a small workflow product and a six-to-eight-screen take-home build. It keeps policy close to data and avoids a queue, broker, service discovery, or distributed deployment before measured latency or throughput requires one.

### Technology choices

| Layer | Actual implementation | Boundary or trade-off |
|---|---|---|
| Browser | React 18, TypeScript, Vite, plain CSS | Feature-local state; no router/state-management dependency |
| API | FastAPI, dependency injection, OpenAPI | Synchronous handlers and service transactions |
| Schemas | Pydantic v2 | Strict provider and request validation |
| Persistence | SQLAlchemy 2, PostgreSQL, Alembic | Relational constraints and JSONB evidence |
| Auth | Argon2id; short-lived JWT in HttpOnly cookie | No refresh-token rotation/password recovery |
| Storage | Private generated-name filesystem adapter | Render filesystem is ephemeral |
| OCR | Embedded PDF text; PyMuPDF/Pillow/Tesseract fallback | Tesseract executable is external |
| Extraction | Local labelled-text parser; optional OpenAI-compatible adapter | External provider setting not publicly verifiable |

### Architecture diagram

~~~text
User
  |
  v
React + TypeScript + Vite
  | HTTPS REST, credentials, Origin, CSRF header
  v
FastAPI modular monolith
  | auth/RBAC/CSRF
  | shipments
  | documents/private storage
  | extraction/provider adapters
  | review/revisions/validation
  | export eligibility/CSV
  + manager reporting
       |                         |
       v                         v
PostgreSQL + Alembic       private filesystem adapter
       ^                         ^
       +---- SQLAlchemy ---------+
~~~

All mutations enter through backend routes protected by authentication, role checks, input validation, exact Origin checks, and CSRF checks. The frontend cannot set shipment status or export eligibility.

## 3. Data model

The current migrations create nine tables: users, roles, user_roles, shipments, shipment_documents, document_extractions, review_fields, field_revisions, and shipment_validations. There is no separate supplier table; supplier is a string on shipments.

| Entity | Implemented facts |
|---|---|
| User | UUID, email, Argon2id password hash, active flag, timestamps |
| Role/user_roles | Two roles and many-to-many association |
| Shipment | Unique reference, importer, supplier, origin, description, creator, status, timestamps |
| ShipmentDocument | Shipment/uploader foreign keys, type, filename, opaque key, content type, size, SHA-256 |
| DocumentExtraction | One latest run, provider names, status, page count, JSON result, safe errors |
| ReviewField | Path, extracted/current values, value type, confidence, sources, status, version |
| FieldRevision | Append-only action, actor, old/new values, note, timestamp |
| ShipmentValidation | One result per shipment/rule, status, evidence, evaluator, timestamps |

### ER diagram

~~~text
USERS 1 ----< USER_ROLES >---- 1 ROLES
  |
  + created_by_id / uploaded_by_id / actor ids
  v
SHIPMENTS 1 ----< SHIPMENT_DOCUMENTS 1 ---- 0..1 DOCUMENT_EXTRACTIONS
    |                         |
    |                         +----< REVIEW_FIELDS 1 ----< FIELD_REVISIONS
    |
    +----< SHIPMENT_VALIDATIONS

Unique shipment reference; one document type per shipment;
one extraction per document; one field per document/path;
one validation per shipment/rule; constrained status/action values.
~~~

## 4. End-to-end workflows

### Sign-in and shipment creation

1. The client submits credentials to POST /api/v1/auth/login with the exact allowed Origin.
2. The backend authenticates against PostgreSQL and sets a short-lived JWT cookie plus a signed CSRF cookie.
3. The client calls /auth/me and loads the shipment list.
4. Before a state-changing request, the corrected client calls authenticated GET /api/v1/auth/csrf, receives the signed value with Cache-Control: no-store, and keeps it in memory only.
5. POST /api/v1/shipments sends credentials, Origin, and X-CSRF-Token. The backend verifies the header/cookie match and signature binding to the JWT.
6. The shipment is created in DRAFT status.

### Document intake, extraction, and review

1. An executive selects a type and uploads PDF/JPG/PNG content.
2. The backend validates filename, extension, size, declared type, file signature, and shallow document structure before storing an opaque key.
3. The client calls extraction synchronously. OCR returns ordered page records with text, readability, and source type.
4. The provider returns a strict structured shape; populated fields require confidence and page/locator evidence.
5. Missing or unreadable values remain NEEDS_REVIEW rather than being guessed.
6. Reviewers correct scalar values with optimistic version checking, confirm, reject, and inspect history.

### Validation and export

The reviewer explicitly runs invoice-total, package-count, gross-weight, and net-weight checks. Fewer than two comparison values produce UNRESOLVED; different normalized values produce FAILED; equality produces PASSED. Corrections and rejections make existing validations STALE.

The export service recomputes eligibility inside a shipment lock. It blocks failed, unresolved, stale, missing, rejected, unconfirmed, failed-extraction, and incomplete-document conditions. A successful export streams provisional CSV and marks the shipment EXPORTED; later corrections return it to action-required state.

~~~text
Sign in -> Shipment list -> Create DRAFT
                              |
                              v
                 Upload invoice / packing list / BOL
                              |
                              v
                 OCR/text -> structured extraction
                              |
                              v
                 Review fields + evidence + flags
                    |            |            |
                 confirm      correct       reject
                    +            |            +
                     +------- rerun validation
                              |
                   eligible and complete?
                      /                \
                    yes                 no
                     |                   |
              backend CSV export    show blockers/review
~~~

## 5. OCR and extraction design

The default configuration is EXTRACTION_AI_PROVIDER=local, selecting LocalRuleBasedProvider. This is deterministic labelled-text parsing, not an LLM. It extracts explicitly labelled values and simple labelled/table forms from OCR text; it does not claim semantic understanding or measured accuracy.

PDFs first use pypdf embedded text page by page. Pages with no usable text fall back to PyMuPDF rasterization, Pillow image handling, and the pytesseract wrapper. The Tesseract executable is not installed by requirements.txt; absence becomes a safe OCR failure for scanned files.

An OpenAICompatibleProvider adapter exists behind explicit provider, URL, key, model, and timeout settings. It requests JSON-only output with confidence and sources, then validates the response strictly. Public source and live HTTP do not expose Render environment values, so the deployed external-provider setting cannot be verified. No claim is made that an external LLM is configured in production.

The extraction schema requires confidence in 0..1 and at least one source reference for every populated field. Unreadable pages, missing values, malformed provider JSON, OCR failures, and provider failures become explicit statuses or safe error codes. The low-confidence threshold defaults to 0.80, an implementation assumption rather than a measured quality threshold. No accuracy percentage is claimed because there is no labelled evaluation dataset.

Deterministic cross-document validation consumes persisted current review values and never asks an AI provider to choose a winning document.

## 6. UI and UX decisions

The frontend implements sign-in, shipment list, shipment creation, shipment detail/review, and manager report views. The detail view is the primary work surface: a private document viewer sits beside structured fields, while upload, rerun, validation, eligibility, and export controls stay near the shipment heading.

Each field exposes current and extracted values, confidence, source page/locator, status, flags, correction note, actions, and history. Low confidence, rejected/missing values, extraction errors, and validation blockers use restrained status colour and readable text. Export is disabled in the client when ineligible, but the backend independently recomputes eligibility.

Loading, empty, and error states are explicit. The CSS uses a sand/off-white surface, deep green navigation, red/amber status accents, responsive grids, and a desktop-first detail layout that collapses at smaller widths.

## 7. Security and reliability

- Passwords use Argon2id.
- JWT access tokens are short-lived and stored in an HttpOnly cookie.
- The CSRF cookie is signed with a nonce and the current JWT value.
- Protected writes require exact Origin allowlist membership and a matching signed cookie/header pair.
- The corrected client uses authenticated GET /auth/csrf, Cache-Control: no-store, and an in-memory token only. It does not use localStorage or sessionStorage.
- CORS permits credentials only for configured exact origins and lists the CSRF header explicitly.
- Input schemas validate login, shipment, review, upload, extraction, and configuration values.
- Shipment/document/field access is scoped server-side.
- Private files use opaque names, restrictive modes, content checks, size limits, checksums, and path/symlink validation.
- Row locks protect validation/export decisions; optimistic versions protect field corrections.

For separate HTTPS Pages and Render sites, production requires AUTH_COOKIE_SECURE=true and AUTH_COOKIE_SAMESITE=none. Browser privacy modes can still block cross-site cookies. The initial deployment uses ephemeral local filesystem storage. Login rate limiting, refresh-token rotation, password recovery, full malware scanning, durable object storage, browser E2E tests, and operational backup/retention are not implemented.

## 8. Testing and verification

| Check | Result | Notes |
|---|---:|---|
| Backend pytest -q tests | 39 passed, 26 skipped | PostgreSQL integration tests skipped because RUN_DB_INTEGRATION was not set and no isolated database was provided |
| Frontend npm run test | 9 passed | Vitest API-client and CSRF bootstrap coverage |
| Frontend npm run build | Passed | TypeScript compilation and Vite production bundle |
| git diff --check | Passed | No whitespace errors |
| Live frontend | HTTP 200 | Pages host reachable; public bundle is pre-fix |
| Live backend health | HTTP 200 | Render health returned {"status":"ok"} |
| Live CSRF bootstrap | Not passed | Endpoint returned 404 because the local fix is not deployed |

Integration tests cover PostgreSQL migrations, authentication/RBAC, shipment scoping, upload/extraction flows, review/revisions, validation state, and export eligibility. They must run only against an isolated test database.

## 9. Assumptions, limitations, and prioritized future work

### Explicit assumptions

1. 0.80 is the default low-confidence threshold because the brief supplies no threshold.
2. Exact normalized numeric equality is used because no rounding/tolerance policy was supplied.
3. Managers may review, decide, validate, and report; executive-only corrections, uploads, and CSV generation remain server-enforced.
4. The CSV field order is provisional because the filing template was not supplied.
5. The documented Neon target is not independently verifiable from public runtime evidence.

### Client targets, not measured results

The client brief gives targets of reducing data entry from 45 minutes to under 15 minutes, achieving 95% field accuracy on 200 historical shipments, and halving amended Bills of Entry within three months. These are client-provided estimates/targets. ShipmentIQ has no evaluation dataset and makes no measured claim about them.

### Out of scope

No customs-portal filing, HSN classification, duty calculation, importer tracking portal, regulatory certification, autonomous approval, or India data-residency guarantee is implemented.

### Prioritized follow-on work

1. Deploy the CSRF bootstrap fix with a coordinated Pages rebuild and authenticated browser smoke test.
2. Replace ephemeral Render storage with approved private object storage and define retention/backup.
3. Install and verify Tesseract in the chosen runtime and evaluate OCR on labelled documents.
4. Obtain and implement the actual filing-software CSV template and field mapping.
5. Add browser tests, rate limiting, malware scanning, token revocation policy, and monitoring.
