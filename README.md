# ShipmentIQ

AI-assisted customs shipment document extraction and cross-check workspace.

Repository: https://github.com/Manjunath-G-K/ShipmentIQ

ShipmentIQ helps customs brokerage teams turn shipping documents into structured, reviewable shipment data. It supports PDF/JPG/PNG uploads, OCR and configurable extraction, source-page/confidence evidence, deterministic cross-document validation, human review history, role-based access, and backend-gated provisional CSV export.

## Workflow

Create a shipment, upload shipping documents, extract proposed fields, compare documents, review discrepancies, confirm or correct values, and export only when backend eligibility checks pass.

Extraction never approves or verifies values. The synthetic case `SHP-24811` demonstrates invoice gross weight 3,120 kg versus packing-list gross weight 3,165 kg; the system reports the 45 kg discrepancy for human review instead of choosing a correct value.

## Architecture

ShipmentIQ is a modular monolith:

- React, TypeScript, and Vite frontend;
- FastAPI, SQLAlchemy, Pydantic, and Alembic backend;
- PostgreSQL for relational shipment, document, extraction, and review data;
- private generated-name local document storage;
- provider-neutral OCR/extraction interfaces; and
- backend-enforced authentication, CSRF, RBAC, object ownership, validation, and export eligibility.

## Security and limitations

The application uses Argon2id password hashing, JWT HttpOnly cookies, signed CSRF cookie/header validation, server-side role reloads, file validation, path traversal protections, revision history, and database migrations. There is no public registration endpoint.

The CSV layout is provisional because the client filing template was not supplied. Render local storage is ephemeral in the initial deployment, so uploaded documents are not claimed to be permanently retained. Rate limiting, malware scanning, refresh-token rotation, password recovery, production object storage, and browser-level end-to-end tests remain future work.

## Documentation

- Backend setup and API behavior: [backend/README.md](backend/README.md)
- Frontend setup and workflow: [frontend/README.md](frontend/README.md)
- Deployment runbook: [deployment.md](deployment.md)
- Technical Design Document: [docs/TDD.md](docs/TDD.md)
- Client brief: [docs/client-brief.md](docs/client-brief.md)
- Architecture and requirements: [docs/](docs/)
