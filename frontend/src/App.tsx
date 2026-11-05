import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import { apiBlob, apiFetch, Blocker } from "./api";

type Role = "DOCUMENTATION_EXECUTIVE" | "DOCUMENTATION_MANAGER";
type User = { id: string; email: string; roles: Role[] };
type Shipment = {
  id: string;
  shipment_reference: string;
  importer: string;
  supplier: string;
  origin_country: string;
  description?: string;
  status: string;
  created_at: string;
  updated_at: string;
};
type Document = {
  id: string;
  document_type: "INVOICE" | "PACKING_LIST" | "BILL_OF_LADING" | string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
};
type SourceRef = { page_number: number; locator?: string; excerpt?: string };
type Field = {
  id: string;
  document_id: string;
  field_path: string;
  value_type: string;
  value: unknown;
  extracted_value: unknown;
  confidence?: number;
  source_references: SourceRef[];
  status: string;
  version: number;
  flags: string[];
  last_reviewed_at?: string;
};
type ReviewDocument = {
  id: string;
  document_type: string;
  extraction_status?: string;
  extraction_error_code?: string;
  page_count: number;
  fields: Field[];
};
type Validation = {
  id: string;
  rule_key: string;
  status: string;
  details: Record<string, unknown>;
  evaluated_at: string;
};
type Review = {
  shipment_id: string;
  documents: ReviewDocument[];
  validations: Validation[];
};
type Eligibility = { eligible: boolean; blockers: Blocker[] };
type Revision = {
  id: string;
  action: string;
  previous_value: unknown;
  new_value: unknown;
  note?: string;
  actor_id: string;
  created_at: string;
};
type AccuracyMetric = {
  key: string;
  reviewed_count: number;
  confirmed_count: number;
  corrected_count: number;
  rejected_count: number;
  accuracy_percent?: number;
};

const roleLabel = (roles: Role[]) =>
  roles.includes("DOCUMENTATION_MANAGER")
    ? "Documentation manager"
    : "Documentation executive";
const textValue = (value: unknown) =>
  value === null || value === undefined
    ? ""
    : typeof value === "object"
      ? JSON.stringify(value)
      : String(value);
const prettyPath = (path: string) =>
  path
    .replace(/\[(\d+)\]/g, " $1")
    .replace(/[._]/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
const formatDate = (value?: string) =>
  value ? new Date(value).toLocaleString() : "—";

function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      onLogin(
        await apiFetch<User>("/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        }),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to sign in");
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login-shell">
      <section className="login-card">
        <div className="brand-mark">SI</div>
        <p className="eyebrow">Trade documentation control</p>
        <h1>ShipmentIQ</h1>
        <p className="muted">
          Review the source, understand the confidence, and release only
          verified shipment data.
        </p>
        <form onSubmit={submit} className="stack">
          <label>
            Email
            <input
              required
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label>
            Password
            <input
              required
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {error && <div className="error-banner">{error}</div>}
          <button className="primary" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}

function ShipmentList({
  user,
  onOpen,
  onCreate,
  onAccuracy,
}: {
  user: User;
  onOpen: (id: string) => void;
  onCreate: () => void;
  onAccuracy: () => void;
}) {
  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    apiFetch<{ items: Shipment[] }>("/shipments?limit=50")
      .then((data) => setShipments(data.items))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Operations overview</p>
          <h1>Shipments</h1>
          <p className="muted">
            Document intake, structured extraction and controlled review.
          </p>
        </div>
        <div className="actions">
          {user.roles.includes("DOCUMENTATION_MANAGER") && (
            <button className="secondary" onClick={onAccuracy}>
              Accuracy report
            </button>
          )}
          {user.roles.includes("DOCUMENTATION_EXECUTIVE") && (
            <button className="primary" onClick={onCreate}>
              New shipment
            </button>
          )}
        </div>
      </div>
      {error && <div className="error-banner">{error}</div>}
      {loading ? (
        <div className="state-card">Loading shipments…</div>
      ) : shipments.length === 0 ? (
        <div className="state-card">
          <h3>No shipments yet</h3>
          <p className="muted">Create a shipment to begin document review.</p>
        </div>
      ) : (
        <div className="shipment-grid">
          {shipments.map((shipment) => (
            <button
              className="shipment-card"
              key={shipment.id}
              onClick={() => onOpen(shipment.id)}
            >
              <div className="card-top">
                <span className="status-pill">{shipment.status}</span>
                <span className="mono">{shipment.shipment_reference}</span>
              </div>
              <h3>{shipment.importer}</h3>
              <p>
                {shipment.supplier} · {shipment.origin_country}
              </p>
              <small>Updated {formatDate(shipment.updated_at)}</small>
            </button>
          ))}
        </div>
      )}
    </>
  );
}

function CreateShipment({
  onCreated,
  onCancel,
}: {
  onCreated: (shipment: Shipment) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState({
    shipment_reference: "",
    importer: "",
    supplier: "",
    origin_country: "",
    description: "",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const update =
    (key: keyof typeof form) =>
    (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm({ ...form, [key]: event.target.value });
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      onCreated(
        await apiFetch<Shipment>("/shipments", {
          method: "POST",
          body: JSON.stringify(form),
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to create shipment");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel narrow">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Intake</p>
          <h2>Create shipment</h2>
        </div>
        <button className="text-button" onClick={onCancel}>
          Cancel
        </button>
      </div>
      <form className="form-grid" onSubmit={submit}>
        <label>
          Shipment reference
          <input
            required
            value={form.shipment_reference}
            onChange={update("shipment_reference")}
          />
        </label>
        <label>
          Origin country
          <input
            required
            value={form.origin_country}
            onChange={update("origin_country")}
          />
        </label>
        <label>
          Importer
          <input required value={form.importer} onChange={update("importer")} />
        </label>
        <label>
          Supplier
          <input required value={form.supplier} onChange={update("supplier")} />
        </label>
        <label className="full">
          Description
          <textarea
            value={form.description}
            onChange={update("description")}
            rows={3}
          />
        </label>
        {error && <div className="error-banner full">{error}</div>}
        <div className="actions full">
          <button type="button" className="secondary" onClick={onCancel}>
            Cancel
          </button>
          <button className="primary" disabled={busy}>
            {busy ? "Creating…" : "Create shipment"}
          </button>
        </div>
      </form>
    </section>
  );
}

function DocumentViewer({
  shipmentId,
  document,
}: {
  shipmentId: string;
  document?: Document;
}) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    let objectUrl = "";
    setUrl("");
    setError("");
    if (!document)
      return () => {
        active = false;
      };
    apiBlob(`/shipments/${shipmentId}/documents/${document.id}/download`)
      .then((blob) => {
        if (active) {
          objectUrl = URL.createObjectURL(blob);
          setUrl(objectUrl);
        }
      })
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [shipmentId, document?.id]);
  if (!document)
    return (
      <div className="viewer empty">Select a document to view the source.</div>
    );
  return (
    <div className="viewer">
      {error ? (
        <div className="error-banner">{error}</div>
      ) : !url ? (
        <div className="muted">Loading source document…</div>
      ) : document.content_type === "application/pdf" ? (
        <iframe title={document.original_filename} src={url} />
      ) : (
        <img alt={document.original_filename} src={url} />
      )}
    </div>
  );
}

function FieldRow({
  field,
  canEdit,
  onChanged,
}: {
  field: Field;
  canEdit: boolean;
  onChanged: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(textValue(field.value));
  const [note, setNote] = useState("");
  const [revisions, setRevisions] = useState<Revision[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => setValue(textValue(field.value)), [field.value]);
  const confidence =
    field.confidence === undefined || field.confidence === null
      ? "—"
      : `${Math.round(field.confidence * 100)}%`;
  async function action(path: string, body: object) {
    setBusy(true);
    setError("");
    try {
      await apiFetch(`/fields/${field.id}${path}`, {
        method: path === "" ? "PATCH" : "POST",
        body: JSON.stringify(body),
      });
      setEditing(false);
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Review action failed");
    } finally {
      setBusy(false);
    }
  }
  async function save() {
    let parsed: unknown = value;
    if (field.value_type === "number" || field.value_type === "integer")
      parsed = Number(value);
    await action("", {
      value: parsed,
      note: note || undefined,
      expected_version: field.version,
    });
  }
  async function showRevisions() {
    if (revisions) {
      setRevisions(null);
      return;
    }
    try {
      setRevisions(await apiFetch<Revision[]>(`/fields/${field.id}/revisions`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load revisions");
    }
  }
  return (
    <div className="field-row">
      <div className="field-main">
        <div className="field-label">
          {prettyPath(field.field_path)}{" "}
          <span
            className={`confidence ${field.confidence !== undefined && field.confidence !== null && field.confidence < 0.8 ? "low" : ""}`}
          >
            {confidence}
          </span>
        </div>
        {editing ? (
          <div className="edit-stack">
            <input value={value} onChange={(e) => setValue(e.target.value)} />
            <input
              placeholder="Correction note (optional)"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
        ) : (
          <div className="field-value">
            {textValue(field.value) || <span className="missing">Missing</span>}
          </div>
        )}
        <div className="source-line">
          {field.source_references.length
            ? field.source_references
                .map(
                  (ref) =>
                    `p.${ref.page_number}${ref.locator ? ` · ${ref.locator}` : ""}`,
                )
                .join("  ")
            : "No source reference"}
          {field.extracted_value !== field.value &&
          field.extracted_value !== undefined
            ? ` · extracted: ${textValue(field.extracted_value)}`
            : ""}
        </div>
        {field.flags.length > 0 && (
          <div className="flag-line">
            {field.flags.map((flag) => (
              <span key={flag}>{flag.replaceAll("_", " ")}</span>
            ))}
          </div>
        )}
        {error && <div className="inline-error">{error}</div>}
      </div>
      <div className="field-actions">
        <span className={`review-status ${field.status.toLowerCase()}`}>
          {field.status}
        </span>
        {canEdit && editing ? (
          <>
            <button className="mini primary" disabled={busy} onClick={save}>
              Save
            </button>
            <button className="mini" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </>
        ) : (
          canEdit && (
            <button className="mini" onClick={() => setEditing(true)}>
              Correct
            </button>
          )
        )}
        {field.status !== "CONFIRMED" && (
          <button
            className="mini"
            disabled={busy}
            onClick={() =>
              action("/confirm", { expected_version: field.version })
            }
          >
            Confirm
          </button>
        )}
        {field.status !== "REJECTED" && (
          <button
            className="mini danger"
            disabled={busy}
            onClick={() =>
              action("/reject", { expected_version: field.version })
            }
          >
            Reject
          </button>
        )}
        <button className="mini" onClick={showRevisions}>
          History
        </button>
      </div>
      {revisions && (
        <div className="revision-list">
          {revisions.length ? (
            revisions.map((revision) => (
              <div key={revision.id}>
                <strong>{revision.action}</strong> ·{" "}
                {formatDate(revision.created_at)} ·{" "}
                {textValue(revision.new_value) || "blank"}
                {revision.note ? ` · ${revision.note}` : ""}
              </div>
            ))
          ) : (
            <span className="muted">No revisions recorded.</span>
          )}
        </div>
      )}
    </div>
  );
}

function ShipmentDetail({
  user,
  shipmentId,
  onBack,
}: {
  user: User;
  shipmentId: string;
  onBack: () => void;
}) {
  const [shipment, setShipment] = useState<Shipment | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [review, setReview] = useState<Review | null>(null);
  const [eligibility, setEligibility] = useState<Eligibility | null>(null);
  const [selected, setSelected] = useState<Document>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploadFile, setUploadFile] = useState<File>();
  const [uploadType, setUploadType] = useState("INVOICE");
  const canEdit = user.roles.includes("DOCUMENTATION_EXECUTIVE");
  async function load() {
    setError("");
    try {
      const [s, d, r, e] = await Promise.all([
        apiFetch<Shipment>(`/shipments/${shipmentId}`),
        apiFetch<{ items: Document[] }>(`/shipments/${shipmentId}/documents`),
        apiFetch<Review>(`/shipments/${shipmentId}/review`),
        apiFetch<Eligibility>(`/shipments/${shipmentId}/export-eligibility`),
      ]);
      setShipment(s);
      setDocuments(d.items);
      setReview(r);
      setEligibility(e);
      setSelected(
        (current) =>
          d.items.find((item) => item.id === current?.id) || d.items[0],
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load shipment");
    }
  }
  useEffect(() => {
    load();
  }, [shipmentId]);
  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!uploadFile) return;
    setBusy(true);
    setError("");
    const body = new FormData();
    body.append("document_type", uploadType);
    body.append("file", uploadFile);
    try {
      const doc = await apiFetch<Document>(
        `/shipments/${shipmentId}/documents`,
        { method: "POST", body },
      );
      await apiFetch(`/shipments/${shipmentId}/documents/${doc.id}/extract`, {
        method: "POST",
      });
      setUploadFile(undefined);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload or extraction failed");
    } finally {
      setBusy(false);
    }
  }
  async function runExtraction(documentId: string) {
    setBusy(true);
    try {
      await apiFetch(
        `/shipments/${shipmentId}/documents/${documentId}/extract`,
        { method: "POST" },
      );
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Extraction failed");
    } finally {
      setBusy(false);
    }
  }
  async function runValidation() {
    setBusy(true);
    try {
      await apiFetch(`/shipments/${shipmentId}/validations/run`, {
        method: "POST",
      });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Validation failed");
    } finally {
      setBusy(false);
    }
  }
  async function exportCsv() {
    setBusy(true);
    try {
      const csv = await apiFetch<string>(`/shipments/${shipmentId}/exports`, {
        method: "POST",
      });
      const blob = new Blob([csv], { type: "text/csv" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `${shipment?.shipment_reference || "shipment"}.csv`;
      link.click();
      URL.revokeObjectURL(link.href);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export blocked");
    } finally {
      setBusy(false);
    }
  }
  if (!shipment || !review)
    return <div className="state-card">{error || "Loading shipment…"}</div>;
  const reviewDocs = review.documents.filter(
    (doc) => doc.fields.length || documents.some((item) => item.id === doc.id),
  );
  return (
    <>
      <div className="detail-heading">
        <button className="text-button" onClick={onBack}>
          ← All shipments
        </button>
        <div className="detail-title">
          <div>
            <p className="eyebrow">Shipment {shipment.shipment_reference}</p>
            <h1>{shipment.importer}</h1>
            <p className="muted">
              {shipment.supplier} · {shipment.origin_country} ·{" "}
              {shipment.status}
            </p>
          </div>
          <div className="actions">
            {canEdit && (
              <form className="upload-form" onSubmit={upload}>
                <select
                  value={uploadType}
                  onChange={(e) => setUploadType(e.target.value)}
                >
                  <option value="INVOICE">Invoice</option>
                  <option value="PACKING_LIST">Packing list</option>
                  <option value="BILL_OF_LADING">Bill of lading</option>
                </select>
                <input
                  type="file"
                  accept="application/pdf,image/jpeg,image/png"
                  onChange={(e) => setUploadFile(e.target.files?.[0])}
                />
                <button className="secondary" disabled={!uploadFile || busy}>
                  Upload & extract
                </button>
              </form>
            )}
            {(user.roles.includes("DOCUMENTATION_MANAGER") || canEdit) && (
              <button
                className="secondary"
                disabled={busy}
                onClick={runValidation}
              >
                Run validation
              </button>
            )}
            {canEdit && (
              <button
                className="primary"
                disabled={busy || !eligibility?.eligible}
                title={
                  !eligibility?.eligible ? "Resolve all blockers first" : ""
                }
                onClick={exportCsv}
              >
                Export verified CSV
              </button>
            )}
          </div>
        </div>
      </div>
      {error && <div className="error-banner">{error}</div>}
      <div className="detail-grid">
        <section className="panel source-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Source documents</p>
              <h2>Document viewer</h2>
            </div>
          </div>
          <div className="document-tabs">
            {documents.length ? (
              documents.map((doc) => (
                <button
                  className={selected?.id === doc.id ? "active" : ""}
                  key={doc.id}
                  onClick={() => setSelected(doc)}
                >
                  {doc.document_type.replaceAll("_", " ")}
                  <small>{doc.original_filename}</small>
                </button>
              ))
            ) : (
              <p className="muted">No documents uploaded.</p>
            )}
          </div>
          <DocumentViewer shipmentId={shipmentId} document={selected} />
          {selected && (
            <button
              className="text-button"
              onClick={() => runExtraction(selected.id)}
            >
              Re-run extraction
            </button>
          )}
        </section>
        <section className="panel review-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Structured review</p>
              <h2>Extracted fields</h2>
            </div>
            <span className="muted">{roleLabel(user.roles)}</span>
          </div>
          {reviewDocs.length ? (
            reviewDocs.map((doc) => (
              <div className="review-document" key={doc.id}>
                <div className="review-doc-heading">
                  <strong>{doc.document_type.replaceAll("_", " ")}</strong>
                  <span>
                    {doc.page_count} page{doc.page_count === 1 ? "" : "s"} ·{" "}
                    {doc.extraction_status || "not processed"}
                  </span>
                </div>
                {doc.extraction_error_code && (
                  <div className="error-banner">
                    {doc.extraction_error_code}
                  </div>
                )}
                {doc.fields.map((field) => (
                  <FieldRow
                    key={field.id}
                    field={field}
                    canEdit={canEdit}
                    onChanged={load}
                  />
                ))}
              </div>
            ))
          ) : (
            <div className="state-card">
              No extracted fields yet. Upload a document and run extraction.
            </div>
          )}
        </section>
      </div>
      <div className="bottom-grid">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Controls</p>
              <h2>Validation results</h2>
            </div>
            <span
              className={`eligibility ${eligibility?.eligible ? "good" : "blocked"}`}
            >
              {eligibility?.eligible ? "Eligible for export" : "Export blocked"}
            </span>
          </div>
          {eligibility && !eligibility.eligible && (
            <div className="blocker-list">
              {eligibility.blockers.map((blocker, index) => (
                <div key={`${blocker.code}-${index}`}>
                  <strong>{blocker.code.replaceAll("_", " ")}</strong>
                  <span>
                    {blocker.message}
                    {blocker.field_path
                      ? ` · ${prettyPath(blocker.field_path)}`
                      : ""}
                  </span>
                </div>
              ))}
            </div>
          )}
          {review.validations.length ? (
            <div className="validation-list">
              {review.validations.map((validation) => (
                <div key={validation.id}>
                  <span
                    className={`validation-dot ${validation.status.toLowerCase()}`}
                  />{" "}
                  <strong>{validation.rule_key.replaceAll("_", " ")}</strong>
                  <span>{validation.status}</span>
                  <small>{JSON.stringify(validation.details)}</small>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted">
              Validation has not been run yet. Missing comparisons remain
              unresolved.
            </p>
          )}
        </section>
      </div>
    </>
  );
}

function AccuracyReport({ onBack }: { onBack: () => void }) {
  const [report, setReport] = useState<{
    field_metrics: AccuracyMetric[];
    supplier_metrics: AccuracyMetric[];
  }>();
  const [error, setError] = useState("");
  useEffect(() => {
    apiFetch<typeof report>("/reports/accuracy")
      .then(setReport)
      .catch((e) => setError(e.message));
  }, []);
  const table = (title: string, metrics: AccuracyMetric[]) => (
    <section className="panel">
      <p className="eyebrow">{title}</p>
      <h2>Accuracy</h2>
      <div className="metric-table">
        {metrics.map((metric) => (
          <div className="metric-row" key={metric.key}>
            <strong>{metric.key}</strong>
            <span>{metric.reviewed_count} reviewed</span>
            <span>{metric.corrected_count} corrected</span>
            <span>{metric.rejected_count} rejected</span>
            <b>
              {metric.accuracy_percent == null
                ? "—"
                : `${metric.accuracy_percent.toFixed(1)}%`}
            </b>
          </div>
        ))}
      </div>
    </section>
  );
  return (
    <>
      <button className="text-button" onClick={onBack}>
        ← All shipments
      </button>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Manager reporting</p>
          <h1>Accuracy report</h1>
          <p className="muted">
            Field and supplier-level outcomes from human review.
          </p>
        </div>
      </div>
      {error ? (
        <div className="error-banner">{error}</div>
      ) : !report ? (
        <div className="state-card">Loading report…</div>
      ) : (
        <div className="report-grid">
          {table("Field-level", report.field_metrics)}
          {table("Supplier-level", report.supplier_metrics)}
        </div>
      )}
    </>
  );
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [view, setView] = useState<"list" | "create" | "detail" | "accuracy">(
    "list",
  );
  const [shipmentId, setShipmentId] = useState("");
  const [booting, setBooting] = useState(true);
  useEffect(() => {
    apiFetch<User>("/auth/me")
      .then(setUser)
      .catch(() => undefined)
      .finally(() => setBooting(false));
  }, []);
  if (booting) return <div className="loading-screen">Loading ShipmentIQ…</div>;
  if (!user) return <Login onLogin={setUser} />;
  async function logout() {
    await apiFetch("/auth/logout", { method: "POST" });
    setUser(null);
    setView("list");
  }
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span>SI</span>
          <div>
            <strong>ShipmentIQ</strong>
            <small>Control tower</small>
          </div>
        </div>
        <div className="side-note">
          <span className="live-dot" />
          Authenticated workspace
        </div>
        <div className="sidebar-footer">
          <span>{user.email}</span>
          <small>{roleLabel(user.roles)}</small>
          <button className="text-button light" onClick={logout}>
            Sign out
          </button>
        </div>
      </aside>
      <main className="content">
        <header className="topbar">
          <span>Documentation operations</span>
          <span className="date-stamp">
            {new Date().toLocaleDateString(undefined, { dateStyle: "long" })}
          </span>
        </header>
        {view === "list" && (
          <ShipmentList
            user={user}
            onOpen={(id) => {
              setShipmentId(id);
              setView("detail");
            }}
            onCreate={() => setView("create")}
            onAccuracy={() => setView("accuracy")}
          />
        )}
        {view === "create" && (
          <CreateShipment
            onCancel={() => setView("list")}
            onCreated={(shipment) => {
              setShipmentId(shipment.id);
              setView("detail");
            }}
          />
        )}
        {view === "detail" && (
          <ShipmentDetail
            user={user}
            shipmentId={shipmentId}
            onBack={() => setView("list")}
          />
        )}
        {view === "accuracy" && (
          <AccuracyReport onBack={() => setView("list")} />
        )}
      </main>
    </div>
  );
}
