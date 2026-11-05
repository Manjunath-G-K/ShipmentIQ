"""Seed clearly synthetic shipments and labelled PDF documents for a local demo."""

from __future__ import annotations

from io import BytesIO

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import DocumentType, Shipment, ShipmentDocument, User
from app.db.session import get_session_factory
from app.modules.auth.service import seed_demo_users
from app.modules.documents.service import upload_document
from app.modules.documents.storage import PrivateFileStorage
from app.modules.extraction.api import get_ai_provider, get_ocr_provider
from app.modules.extraction.service import process_extraction


def _pdf(lines: list[str]) -> bytes:
    """Build a minimal text PDF without adding a document-generation dependency."""

    def escape(value: str) -> bytes:
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode("latin-1", "replace")

    stream_lines = [b"BT", b"/F1 11 Tf", b"72 740 Td"]
    for line in lines:
        stream_lines.extend([b"(" + escape(line) + b") Tj", b"0 -16 Td"])
    stream_lines.append(b"ET")
    stream = b"\n".join(stream_lines) + b"\n"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"endstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode("ascii"))
        pdf.extend(body)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


DEMO_SHIPMENTS = [
    {
        "reference": "SHP-24811",
        "importer": "Synthetic Importer Pvt Ltd",
        "supplier": "Company B (China)",
        "origin": "China",
        "description": "Synthetic demo: invoice and packing-list gross weights differ by 45 kg.",
        "documents": [
            (
                DocumentType.INVOICE,
                "SHP-24811-invoice-synthetic.pdf",
                [
                    "SYNTHETIC DEMO DOCUMENT - NOT A CUSTOMS RECORD",
                    "Importer: Synthetic Importer Pvt Ltd",
                    "Supplier: Company B (China)",
                    "Invoice Number: INV-24811",
                    "Invoice Date: 2026-11-05",
                    "Currency: USD",
                    "Incoterm: FOB",
                    "Invoice Total: 16320",
                    "Packages: 240",
                    "Gross Weight (kg): 3120",
                    "Net Weight (kg): 3000",
                    "LED panel light 40W | 2400 | 6.80 | 9405",
                    "Container: SYNTH24811",
                ],
            ),
            (
                DocumentType.PACKING_LIST,
                "SHP-24811-packing-list-synthetic.pdf",
                [
                    "SYNTHETIC DEMO DOCUMENT - NOT A CUSTOMS RECORD",
                    "Importer: Synthetic Importer Pvt Ltd",
                    "Supplier: Company B (China)",
                    "Packages: 240",
                    "Gross Weight (kg): 3165",
                    "Net Weight (kg): 3000",
                    "LED panel light 40W | 2400 | 6.80 | 9405",
                ],
            ),
        ],
    },
    {
        "reference": "SHP-24812",
        "importer": "Synthetic Importer Pvt Ltd",
        "supplier": "Company C (Sweden)",
        "origin": "Sweden",
        "description": "Synthetic demo: invoice-only sample; document comparisons remain unresolved.",
        "documents": [
            (
                DocumentType.INVOICE,
                "SHP-24812-invoice-synthetic.pdf",
                [
                    "SYNTHETIC DEMO DOCUMENT - NOT A CUSTOMS RECORD",
                    "Importer: Synthetic Importer Pvt Ltd",
                    "Supplier: Company C (Sweden)",
                    "Invoice Number: INV-24812",
                    "Invoice Date: 2026-11-05",
                    "Currency: EUR",
                    "Incoterm: CIF",
                    "Invoice Total: 7650",
                    "Packages: 18",
                    "Gross Weight (kg): 1460",
                    "Net Weight (kg): 1400",
                    "Steel ball valve DN50 | 180 | 42.50 | 8481",
                ],
            ),
        ],
    },
]


def main() -> None:
    settings = get_settings()
    if settings.environment.lower() == "production":
        raise ValueError("Synthetic demo data seeding is disabled in production")
    with get_session_factory()() as session:
        users = seed_demo_users(session, settings)
        executive = next(user for user in users if user.email == settings.demo_executive_email.casefold())
        storage = PrivateFileStorage(settings.document_storage_path, settings.document_max_size_bytes)
        for item in DEMO_SHIPMENTS:
            shipment = session.scalar(select(Shipment).where(Shipment.shipment_reference == item["reference"]))
            if shipment is None:
                shipment = Shipment(
                    created_by_id=executive.id,
                    shipment_reference=item["reference"],
                    importer=item["importer"],
                    supplier=item["supplier"],
                    origin_country=item["origin"],
                    description=item["description"],
                    status="DRAFT",
                )
                session.add(shipment)
                session.flush()
            for document_type, filename, lines in item["documents"]:
                existing = session.scalar(
                    select(ShipmentDocument).where(
                        ShipmentDocument.shipment_id == shipment.id,
                        ShipmentDocument.document_type == document_type.value,
                    )
                )
                if existing is not None:
                    continue
                document = upload_document(
                    session,
                    executive,
                    shipment.id,
                    document_type,
                    BytesIO(_pdf(lines)),
                    filename=filename,
                    declared_content_type="application/pdf",
                    storage=storage,
                )
                process_extraction(
                    session,
                    executive,
                    shipment.id,
                    document.id,
                    storage,
                    get_ocr_provider(settings),
                    get_ai_provider(settings),
                )
        session.commit()
    print("Verified synthetic demo shipments SHP-24811 and SHP-24812.")


if __name__ == "__main__":
    main()
