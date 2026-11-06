from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.pdfbase.pdfmetrics import stringWidth


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "pdf" / "TDD.pdf"

NAVY = colors.HexColor("#143C4A")
FOREST = colors.HexColor("#1C5E4A")
SAGE = colors.HexColor("#DCE9DF")
SAND = colors.HexColor("#F5F1EA")
INK = colors.HexColor("#1F2926")
MUTED = colors.HexColor("#53615C")
LINE = colors.HexColor("#D5DED8")
RUST = colors.HexColor("#A64B3C")
AMBER = colors.HexColor("#A8752A")
WHITE = colors.white


class SectionRule(Flowable):
    def __init__(self, color=FOREST, width=36 * mm, space=5):
        super().__init__()
        self.color = color
        self.width = width
        self.space = space
        self.height = space + 2

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(2)
        self.canv.line(0, self.space, self.width, self.space)


class BoxDiagram(Flowable):
    def __init__(self, kind: str):
        super().__init__()
        self.kind = kind
        self.width = 165 * mm
        self.height = 73 * mm

    def draw_box(self, x, y, w, h, label, fill, stroke=NAVY, size=8.2):
        c = self.canv
        c.setFillColor(fill)
        c.setStrokeColor(stroke)
        c.setLineWidth(0.8)
        c.roundRect(x, y, w, h, 5, fill=1, stroke=1)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", size)
        for idx, line in enumerate(label.split("\n")):
            c.drawCentredString(x + w / 2, y + h / 2 + (len(label.split("\n")) - 1) * 4 - idx * 10, line)

    def arrow(self, x1, y1, x2, y2):
        c = self.canv
        c.setStrokeColor(FOREST)
        c.setFillColor(FOREST)
        c.setLineWidth(1.2)
        c.line(x1, y1, x2, y2)
        if x2 >= x1:
            c.line(x2, y2, x2 - 5, y2 + 3)
            c.line(x2, y2, x2 - 5, y2 - 3)
        else:
            c.line(x2, y2, x2 + 5, y2 + 3)
            c.line(x2, y2, x2 + 5, y2 - 3)

    def draw(self):
        if self.kind == "architecture":
            self.draw_architecture()
        elif self.kind == "er":
            self.draw_er()
        else:
            self.draw_workflow()

    def draw_architecture(self):
        self.draw_box(53 * mm, 55 * mm, 60 * mm, 13 * mm, "React + TypeScript + Vite", SAGE)
        self.draw_box(42 * mm, 35 * mm, 82 * mm, 13 * mm, "FastAPI modular monolith", colors.HexColor("#E7EFEA"))
        self.draw_box(3 * mm, 10 * mm, 36 * mm, 13 * mm, "PostgreSQL\n+ Alembic", colors.HexColor("#E8EEF2"))
        self.draw_box(46 * mm, 10 * mm, 42 * mm, 13 * mm, "Private storage", colors.HexColor("#F4E8D4"))
        self.draw_box(95 * mm, 10 * mm, 55 * mm, 13 * mm, "OCR / extraction\nproviders", colors.HexColor("#F0E7E4"))
        self.arrow(83 * mm, 55 * mm, 83 * mm, 48 * mm)
        self.arrow(55 * mm, 35 * mm, 30 * mm, 23 * mm)
        self.arrow(83 * mm, 35 * mm, 67 * mm, 23 * mm)
        self.arrow(109 * mm, 35 * mm, 122 * mm, 23 * mm)
        c = self.canv
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 7.5)
        c.drawCentredString(83 * mm, 1.5 * mm, "Credentialed REST, exact Origin allowlist, signed CSRF header/cookie validation")

    def draw_er(self):
        boxes = [
            (4, 50, 34, 13, "users"),
            (49, 50, 31, 13, "roles"),
            (98, 50, 54, 13, "shipments"),
            (98, 28, 54, 13, "shipment_documents"),
            (4, 28, 55, 13, "review_fields"),
            (4, 6, 55, 13, "field_revisions"),
            (98, 6, 54, 13, "document_extractions"),
        ]
        for x, y, w, h, label in boxes:
            self.draw_box(x * mm, y * mm, w * mm, h * mm, label, colors.HexColor("#EFF4F0"), size=7.2)
        self.draw_box(49 * mm, 6 * mm, 31 * mm, 13 * mm, "validations", colors.HexColor("#F4E8D4"), size=7.2)
        self.arrow(38 * mm, 56.5 * mm, 49 * mm, 56.5 * mm)
        self.arrow(80 * mm, 56.5 * mm, 98 * mm, 56.5 * mm)
        self.arrow(125 * mm, 50 * mm, 125 * mm, 41 * mm)
        self.arrow(98 * mm, 34 * mm, 59 * mm, 34 * mm)
        self.arrow(31 * mm, 28 * mm, 31 * mm, 19 * mm)
        self.arrow(59 * mm, 12.5 * mm, 98 * mm, 12.5 * mm)
        c = self.canv
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 7.2)
        c.drawString(3 * mm, 70 * mm, "Nine current tables; user-role association and server-side foreign keys omitted from the drawing for readability.")

    def draw_workflow(self):
        nodes = [
            (4, 50, 28, 13, "Sign in", SAGE),
            (43, 50, 34, 13, "Create\nshipment", colors.HexColor("#E7EFEA")),
            (88, 50, 38, 13, "Upload +\nextract", colors.HexColor("#F4E8D4")),
            (137, 50, 25, 13, "Review", colors.HexColor("#F0E7E4")),
            (43, 20, 35, 13, "Validate", colors.HexColor("#E8EEF2")),
            (91, 20, 35, 13, "Eligible?", colors.HexColor("#E8EEF2")),
            (137, 20, 25, 13, "CSV", SAGE),
        ]
        for x, y, w, h, label, fill in nodes:
            self.draw_box(x * mm, y * mm, w * mm, h * mm, label, fill, size=7.2)
        self.arrow(32 * mm, 56.5 * mm, 43 * mm, 56.5 * mm)
        self.arrow(77 * mm, 56.5 * mm, 88 * mm, 56.5 * mm)
        self.arrow(126 * mm, 56.5 * mm, 137 * mm, 56.5 * mm)
        self.arrow(151 * mm, 50 * mm, 60 * mm, 33 * mm)
        self.arrow(78 * mm, 26.5 * mm, 91 * mm, 26.5 * mm)
        self.arrow(126 * mm, 26.5 * mm, 137 * mm, 26.5 * mm)
        c = self.canv
        c.setFillColor(RUST)
        c.setFont("Helvetica-Bold", 7.2)
        c.drawString(7 * mm, 28 * mm, "Failed / unresolved / missing values return to review.")

def make_styles():
    base = getSampleStyleSheet()
    return {
        "cover": ParagraphStyle("cover", parent=base["Title"], fontName="Helvetica-Bold", fontSize=28, leading=31, textColor=NAVY, spaceAfter=7),
        "subtitle": ParagraphStyle("subtitle", parent=base["Normal"], fontName="Helvetica", fontSize=11, leading=15, textColor=MUTED, spaceAfter=8),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=NAVY, spaceBefore=2, spaceAfter=5, keepWithNext=True),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=FOREST, spaceBefore=7, spaceAfter=3, keepWithNext=True),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontName="Helvetica", fontSize=9.2, leading=12.4, textColor=INK, spaceAfter=5),
        "small": ParagraphStyle("small", parent=base["BodyText"], fontName="Helvetica", fontSize=7.5, leading=9.6, textColor=MUTED, spaceAfter=2),
        "bullet": ParagraphStyle("bullet", parent=base["BodyText"], fontName="Helvetica", fontSize=8.9, leading=11.8, leftIndent=11, firstLineIndent=-7, bulletIndent=0, textColor=INK, spaceAfter=2),
        "callout": ParagraphStyle("callout", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=NAVY, backColor=SAGE, borderColor=LINE, borderWidth=.5, borderPadding=7, spaceBefore=5, spaceAfter=7),
        "link": ParagraphStyle("link", parent=base["BodyText"], fontName="Helvetica", fontSize=9.5, leading=13, textColor=FOREST, underlineColor=FOREST, underlineWidth=.5, spaceAfter=3),
        "table": ParagraphStyle("table", parent=base["BodyText"], fontName="Helvetica", fontSize=7.5, leading=9.3, textColor=INK),
        "table_head": ParagraphStyle("table_head", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=7.5, leading=9.3, textColor=WHITE),
    }

def P(text, style):
    return Paragraph(escape(text).replace("\n", "<br/>"), style)

def rich(text, style):
    return Paragraph(text, style)

def bullets(items, styles):
    return [P("- " + item, styles["bullet"]) for item in items]

def table(data, styles, widths=None):
    rows = []
    for r, row in enumerate(data):
        row_style = styles["table_head"] if r == 0 else styles["table"]
        rows.append([P(str(cell), row_style) for cell in row])
    t = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("GRID", (0, 0), (-1, -1), .35, LINE),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#FBFCFA")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FBFCFA"), colors.HexColor("#F2F6F2")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t

def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(SAND)
    canvas.rect(0, 0, A4[0], 10 * mm, fill=1, stroke=0)
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 13 * mm, A4[0] - 18 * mm, 13 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.4)
    canvas.drawString(18 * mm, 7 * mm, "ShipmentIQ | Technical Design Document")
    canvas.drawRightString(A4[0] - 18 * mm, 7 * mm, f"November 2026  |  {doc.page}")
    canvas.restoreState()

def build():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    styles = make_styles()
    doc = BaseDocTemplate(
        str(OUT), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=15 * mm, bottomMargin=18 * mm, title="ShipmentIQ Technical Design Document",
        author="ShipmentIQ engineering audit",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="main", frames=frame, onPage=header_footer)])
    S = []
    def h1(text): S.extend([P(text, styles["h1"]), SectionRule(), Spacer(1, 2)])
    def h2(text): S.append(P(text, styles["h2"]))
    def body(text): S.append(P(text, styles["body"]))
    def small(text): S.append(P(text, styles["small"]))
    def page(): S.append(PageBreak())

    S.append(Spacer(1, 8 * mm))
    S.append(rich('<b>GitHub:</b> <link href="https://github.com/Manjunath-G-K/ShipmentIQ" color="#1C5E4A">https://github.com/Manjunath-G-K/ShipmentIQ</link>', styles["link"]))
    S.append(Spacer(1, 8 * mm))
    S.append(P("ShipmentIQ", styles["cover"]))
    S.append(P("Technical Design Document", styles["subtitle"]))
    S.append(SectionRule(NAVY, 50 * mm, 8))
    S.append(Spacer(1, 6))
    S.append(P("A reviewer-oriented implementation audit for a customs-broker shipment document cross-check workbench.", styles["subtitle"]))
    S.append(Spacer(1, 7))
    S.append(rich('<b>Live app:</b> <link href="https://manjunath-g-k.github.io/ShipmentIQ/" color="#1C5E4A">https://manjunath-g-k.github.io/ShipmentIQ/</link>', styles["link"]))
    S.append(rich('<b>Backend health:</b> <link href="https://shipmentiq.onrender.com/api/v1/health" color="#1C5E4A">https://shipmentiq.onrender.com/api/v1/health</link>', styles["link"]))
    S.append(Spacer(1, 10))
    S.append(P("Release status", styles["h2"]))
    S.append(P("The public hosts are reachable, but the local CSRF bootstrap fix is not yet deployed. The live Pages bundle still uses the old cross-origin cookie reader and the live API returns 404 for /api/v1/auth/csrf. This document records that limitation explicitly.", styles["callout"]))
    S.append(P("Executive summary", styles["h2"]))
    body("ShipmentIQ helps customs-broker teams turn private invoice, packing-list, and bill-of-lading documents into structured, reviewable shipment data. It keeps source evidence beside extracted values, surfaces uncertainty and discrepancies, records human decisions, and gates provisional CSV export in the backend.")
    body("The exact problem is a manual, error-prone handoff: read several documents, re-key values, identify mismatches, resolve uncertain fields, and prepare a filing import. ShipmentIQ makes those steps explicit and auditable. It does not file customs entries, classify HSN codes, calculate duty, provide importer tracking, or certify regulatory compliance.")
    S.append(Spacer(1, 6))
    S.append(table([
        ["Verification", "Result"],
        ["Repository", "GitHub remote verified"],
        ["Frontend", "GitHub Pages HTTP 200"],
        ["Backend", "Render health HTTP 200"],
        ["Database provider", "Neon documented; not publicly verifiable"],
        ["CSRF bootstrap", "Local only; live endpoint HTTP 404"],
    ], styles, [48*mm, 113*mm]))
    page()

    h1("1. Problem, users, and scope")
    h2("Roles")
    S.append(table([
        ["Role", "Implemented responsibilities"],
        ["Documentation Executive", "Sign in, create/update own shipments, upload, extract, correct, confirm/reject, validate, and request eligible CSV export."],
        ["Documentation Manager", "View shipments in scope, review documents/fields, confirm/reject, validate, and view field/supplier Unchanged Extraction Rate."],
    ], styles, [43*mm, 118*mm]))
    body("The server reloads roles from PostgreSQL on protected requests. Frontend visibility is only a convenience; it is not authorization.")
    h2("Implemented core build")
    S.extend(bullets([
        "Shipment list, creation, and metadata update.",
        "Private invoice, packing-list, and bill-of-lading upload, with one document of each type per shipment.",
        "Synchronous OCR/text extraction and strict structured field materialization.",
        "Side-by-side source viewer and extracted-field review.",
        "Confidence, source-page/locator evidence, missing/unreadable flags, and revision history.",
        "Deterministic invoice-total, package, gross-weight, and net-weight validation.",
        "Human correction, confirmation, rejection, stale-validation handling, eligibility, and provisional CSV.",
        "Manager field-level and supplier-level reporting.",
    ], styles))
    h2("Scope boundary")
    body("No customs-portal filing, HSN classification, duty calculation, importer tracking portal, regulatory certification, autonomous approval, or India data-residency guarantee is implemented.")
    page()

    h1("2. Architecture")
    body("ShipmentIQ is a modular monolith. One FastAPI process owns authentication, authorization, transactions, document handling, extraction orchestration, review, validation, reporting, and export. This fits a small workflow product and avoids distributed infrastructure before measured scale requires it.")
    h2("Technology choices")
    S.append(table([
        ["Layer", "Actual implementation", "Trade-off / boundary"],
        ["Browser", "React 18, TypeScript, Vite, plain CSS", "Feature-local state; no router/state framework."],
        ["API", "FastAPI, dependency injection, OpenAPI", "Synchronous handlers and service transactions."],
        ["Schemas", "Pydantic v2", "Strict provider and request validation."],
        ["Persistence", "SQLAlchemy 2, PostgreSQL, Alembic", "Relational constraints and JSONB evidence."],
        ["Auth", "Argon2id; short-lived JWT HttpOnly cookie", "No refresh-token rotation/password recovery."],
        ["Storage", "Private generated-name filesystem", "Ephemeral on Render; no object store integrated."],
        ["OCR", "pypdf; PyMuPDF/Pillow/Tesseract fallback", "Tesseract executable is external."],
        ["Extraction", "Local labelled-text; optional OpenAI-compatible", "External provider setting is unverified."],
    ], styles, [28*mm, 70*mm, 63*mm]))
    S.append(Spacer(1, 5))
    S.append(BoxDiagram("architecture"))
    small("All mutations pass through authentication, role checks, input validation, exact Origin checks, and signed CSRF validation. The frontend cannot set status or export eligibility.")
    page()

    h1("3. Data model")
    body("The current migrations create nine tables: users, roles, user_roles, shipments, shipment_documents, document_extractions, review_fields, field_revisions, and shipment_validations. Supplier is a string on shipments; there is no separate supplier entity.")
    S.append(table([
        ["Entity", "Implemented facts"],
        ["User", "UUID, email, Argon2id hash, active flag, timestamps."],
        ["Role / user_roles", "Two roles and many-to-many association."],
        ["Shipment", "Unique reference, importer, supplier, origin, description, creator, status, timestamps."],
        ["ShipmentDocument", "Shipment/uploader keys, type, filename, opaque key, content type, size, SHA-256."],
        ["DocumentExtraction", "Latest run, provider names, status, page count, JSON result, safe errors."],
        ["ReviewField", "Path, extracted/current values, value type, confidence, sources, status, version."],
        ["FieldRevision", "Append-only action, actor, old/new values, note, timestamp."],
        ["ShipmentValidation", "One result per shipment/rule, status, evidence, evaluator, timestamps."],
    ], styles, [43*mm, 118*mm]))
    S.append(Spacer(1, 5))
    S.append(BoxDiagram("er"))
    page()

    h1("4. End-to-end workflows")
    h2("Authentication and shipment creation")
    S.extend(bullets([
        "POST /api/v1/auth/login validates credentials and exact allowed Origin, then sets a JWT cookie and signed CSRF cookie.",
        "The client calls /auth/me and loads shipments.",
        "Before writes, the corrected client calls authenticated GET /api/v1/auth/csrf, receives Cache-Control: no-store, and keeps the token in memory.",
        "POST /api/v1/shipments sends credentials, Origin, and X-CSRF-Token. The backend verifies the header/cookie match and signature binding to the JWT.",
        "The created shipment starts in DRAFT status.",
    ], styles))
    h2("Document intake and human review")
    S.extend(bullets([
        "The backend validates PDF/JPG/PNG filename, extension, size, declared type, signature, and shallow structure before storing an opaque key.",
        "Extraction returns ordered page records, strict fields, confidence, and page/locator evidence.",
        "Missing or unreadable values stay NEEDS_REVIEW. Reviewers correct scalar values with optimistic version checking, confirm, reject, and inspect history.",
    ], styles))
    h2("Validation and export")
    body("Reviewers explicitly run invoice-total, package-count, gross-weight, and net-weight checks. Fewer than two values are UNRESOLVED; different normalized values are FAILED; equal values are PASSED. Corrections and rejections make old validations STALE.")
    body("The export service recomputes eligibility inside a shipment lock. It blocks failed, unresolved, stale, missing, rejected, unconfirmed, failed-extraction, and incomplete-document conditions. Successful export streams provisional CSV and marks the shipment EXPORTED.")
    S.append(BoxDiagram("workflow"))
    page()

    h1("5. OCR and extraction design")
    body("The default setting selects LocalRuleBasedProvider. This is deterministic labelled-text parsing, not an LLM. It extracts explicitly labelled values and simple labelled/table forms from OCR text and makes no semantic-understanding or accuracy claim.")
    body("PDFs first use pypdf embedded text page by page. Pages without usable text fall back to PyMuPDF rasterization, Pillow image handling, and the pytesseract wrapper. The Tesseract executable is not installed by requirements.txt; absence becomes a safe OCR failure for scanned files.")
    body("An OpenAICompatibleProvider adapter exists behind explicit provider, URL, key, model, and timeout settings. It requests JSON-only output with confidence and sources, then validates the response strictly. Public source and live HTTP do not expose Render environment values, so no claim is made that an external LLM is configured in production.")
    h2("Evidence and uncertainty")
    S.extend(bullets([
        "Every populated field requires confidence in 0..1 and at least one page/locator source reference.",
        "Unreadable pages, missing values, malformed provider JSON, OCR failures, and provider failures become explicit statuses or safe error codes.",
        "The low-confidence threshold defaults to 0.80. This is an implementation assumption, not a measured quality threshold.",
        "No accuracy percentage is claimed because there is no labelled evaluation dataset.",
        "Deterministic cross-document validation consumes persisted review values and never chooses a winning document.",
    ], styles))
    h2("Human confirmation")
    body("Extraction is assistive. A discrepancy is evidence for human review, not an automatic winner. Export eligibility remains a backend policy decision.")
    page()

    h1("6. UI/UX and security")
    h2("Actual screens and journey")
    body("The frontend implements sign-in, shipment list, shipment creation, shipment detail/review, and manager report views. The detail view places a private document viewer beside structured fields, with upload, rerun, validation, eligibility, and export actions near the shipment heading.")
    body("Each field exposes current and extracted values, confidence, source page/locator, status, flags, correction note, actions, and history. Loading, empty, and error states are explicit. The visual system uses a sand/off-white surface, deep green navigation, restrained red/amber status accents, responsive grids, and a desktop-first detail layout.")
    h2("Security controls")
    S.extend(bullets([
        "Argon2id password hashing and short-lived JWT access tokens in an HttpOnly cookie.",
        "Signed double-submit CSRF cookie/header validation bound to the current JWT.",
        "Authenticated GET /auth/csrf with Cache-Control: no-store; the frontend keeps the token in memory only.",
        "Exact CORS allowlist, credentials enabled, explicit CSRF header, and exact Origin validation. No wildcard origins.",
        "Server-side role and shipment/document/field scoping.",
        "Private generated-name files, restrictive permissions, content checks, size limits, checksums, and path/symlink validation.",
        "Row locks for validation/export decisions and optimistic versions for field corrections.",
    ], styles))
    h2("Reliability limits")
    body("The initial deployment uses ephemeral local filesystem storage. Login rate limiting, refresh-token rotation, password recovery, full malware scanning, durable object storage, browser E2E tests, and operational backup/retention are not implemented.")
    page()

    h1("7. Testing and verification")
    S.append(table([
        ["Check", "Result", "Notes"],
        ["Backend pytest -q tests", "39 passed, 26 skipped", "Integration tests skipped because RUN_DB_INTEGRATION was not set and no isolated PostgreSQL database was provided."],
        ["Frontend npm run test", "9 passed", "Vitest API-client and CSRF bootstrap coverage."],
        ["Frontend npm run build", "Passed", "TypeScript compilation and Vite production bundle."],
        ["git diff --check", "Passed", "No whitespace errors."],
        ["Live frontend", "HTTP 200", "Pages host reachable; public bundle is pre-fix."],
        ["Live backend health", "HTTP 200", "Render health returned {status:ok}."],
        ["Live CSRF bootstrap", "Not passed", "Endpoint returned 404 because the local fix is not deployed."],
    ], styles, [42*mm, 32*mm, 87*mm]))
    h2("Test coverage boundary")
    body("Integration tests cover PostgreSQL migrations, authentication/RBAC, shipment scoping, upload/extraction flows, review/revisions, validation state, and export eligibility. They must run only against an isolated test database, never an unknown or production database. A browser-level Playwright suite is not included.")
    h2("What was not claimed")
    body("No production readiness, regulatory certification, data residency, measured 95% accuracy, measured time reduction, or amendment reduction is claimed. Client success metrics remain targets, not results.")
    page()

    h1("8. Assumptions, limitations, and next work")
    h2("Explicit assumptions")
    S.extend(bullets([
        "0.80 is the default low-confidence threshold because the brief supplies no threshold.",
        "Exact normalized numeric equality is used because no rounding/tolerance policy was supplied.",
        "Managers may review, decide, validate, and report; executive-only corrections, uploads, and CSV generation remain server-enforced.",
        "CSV field order is provisional because the filing template was not supplied.",
        "The documented Neon target is not independently verifiable from public runtime evidence.",
    ], styles))
    h2("Client-provided estimates and targets")
    body("The brief targets reducing data entry from 45 minutes to under 15 minutes, achieving 95% field accuracy on 200 historical shipments, and halving amended Bills of Entry within three months. These are client-provided estimates/targets. ShipmentIQ has no evaluation dataset and makes no measured claim about them.")
    h2("Prioritized follow-on work")
    S.extend(bullets([
        "Deploy the CSRF bootstrap fix with a coordinated Pages rebuild and authenticated browser smoke test.",
        "Replace ephemeral Render storage with approved private object storage and define retention/backup.",
        "Install and verify Tesseract in the chosen runtime and evaluate OCR on labelled documents.",
        "Obtain and implement the actual filing-software CSV template and field mapping.",
        "Add browser tests, rate limiting, malware scanning, token revocation policy, and monitoring.",
    ], styles))
    S.append(Spacer(1, 8))
    S.append(P("Submission note: the required ZIP contains only this PDF and deployment.md. Reviewer passwords are intentionally absent pending explicit private confirmation.", styles["callout"]))
    doc.build(S)

if __name__ == "__main__":
    build()
