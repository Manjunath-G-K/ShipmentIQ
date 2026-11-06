# ShipmentIQ

AI-assisted customs shipment document extraction and cross-check workspace.

Repository: https://github.com/Manjunath-G-K/ShipmentIQ

## Status

The current implemented milestone is ShipmentIQ Part 4 finalization: a React/Vite review client plus backend-enforced provisional CSV export, on top of shipment management, private document upload/storage, provider-neutral OCR, structured extraction, deterministic validation, and human review.

It includes PostgreSQL development through Docker Compose, JWT cookie authentication with Argon2id password hashing, database-backed RBAC, shipment creation/list/detail/update APIs, secure PDF/JPG/PNG shipment document upload/list/download APIs, private generated-name storage, object-level authorization, multi-page OCR, strict structured extraction schemas with field confidence and page references, persisted processing status, deterministic cross-document validation, human review corrections/confirmation/rejection, revision history, accuracy reporting, migrations, and PostgreSQL integration tests.

Shipment statuses are backend-controlled. Extraction never approves or verifies values, and no customs filing connector is included.

## Documentation

- Backend setup and API behavior: [backend/README.md](backend/README.md)
- Frontend setup and workflow: [frontend/README.md](frontend/README.md)
- Deployment runbook: [deployment.md](deployment.md)
- Technical Design Document: [docs/TDD.md](docs/TDD.md)
- Architecture and requirements: [docs/](docs/)
