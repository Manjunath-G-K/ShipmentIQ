# ShipmentIQ frontend

This is the finalized Part 3/4 React/TypeScript/Vite client. It uses the backend session cookie and CSRF cookie; there is no mock data or client-only authorization. Set `VITE_API_BASE_URL` when the API is not at `http://127.0.0.1:8000/api/v1`. `VITE_CSRF_COOKIE_NAME` and `VITE_CSRF_HEADER_NAME` are available when the backend uses non-default names.

```powershell
npm install
npm run dev
```

Executives can create shipments, upload documents, run extraction and validation, correct/confirm/reject fields, and request the provisional CSV after the backend gate passes. Managers can review documents, run validations, and inspect the accuracy report. The backend remains authoritative for role checks, object access, stale validation state, and export eligibility.

For a complete local demo, follow the root [deployment runbook](../deployment.md) and seed `SHP-24811`/`SHP-24812` with the backend demo script. The real filing-software CSV template was not supplied, so the layout is documented as provisional.
