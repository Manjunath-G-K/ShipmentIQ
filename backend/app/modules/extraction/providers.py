"""Replaceable local OCR and AI extraction provider implementations."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Protocol

from app.db.models import DocumentType
from app.modules.extraction.schemas import (
    ExtractionResult,
    ExtractedDate,
    ExtractedDecimal,
    ExtractedInteger,
    ExtractedString,
    InvoiceFields,
    LineItem,
    OCRPage,
    PartyFields,
    ShipmentFields,
)


class OCRProviderError(RuntimeError):
    """OCR could not read the supplied document."""


class AIProviderError(RuntimeError):
    """The configured extraction provider failed or returned unusable data."""


class UnconfiguredAIProvider:
    """Provider object used to persist a safe failure for incomplete configuration."""

    name = "unconfigured"

    def extract(self, pages: list[OCRPage], document_type: DocumentType) -> dict:
        raise AIProviderError("AI provider configuration is incomplete")


class OCRProvider(Protocol):
    name: str

    def extract(self, content: bytes, content_type: str) -> list[OCRPage]: ...


class AIExtractionProvider(Protocol):
    name: str

    def extract(
        self, pages: list[OCRPage], document_type: DocumentType
    ) -> ExtractionResult | dict: ...


class LocalOCRProvider:
    name = "local-pypdf-tesseract"

    def extract(self, content: bytes, content_type: str) -> list[OCRPage]:
        if content_type == "application/pdf":
            return self._extract_pdf(content)
        if content_type in {"image/jpeg", "image/png"}:
            return [self._extract_image(content, page=1)]
        raise OCRProviderError("unsupported content type")

    def _extract_pdf(self, content: bytes) -> list[OCRPage]:
        try:
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(content))
        except Exception as exc:
            raise OCRProviderError("PDF could not be read") from exc
        pages: list[OCRPage] = []
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                text = (page.extract_text() or "").strip()
            except Exception:
                text = ""
            if text:
                pages.append(OCRPage(page=page_number, text=text, readable=True, source="embedded_text"))
            else:
                pages.append(self._ocr_pdf_page(content, page_number))
        return pages

    def _ocr_pdf_page(self, content: bytes, page_number: int) -> OCRPage:
        try:
            import fitz
            import pytesseract
            from PIL import Image

            with fitz.open(stream=content, filetype="pdf") as pdf:
                pixmap = pdf.load_page(page_number - 1).get_pixmap(matrix=fitz.Matrix(2, 2))
                text = pytesseract.image_to_string(Image.open(BytesIO(pixmap.tobytes("png")))).strip()
        except Exception as exc:
            raise OCRProviderError("Scanned PDF OCR requires PyMuPDF, Pillow, and Tesseract") from exc
        return OCRPage(page=page_number, text=text, readable=bool(text), source="ocr" if text else "unreadable")

    def _extract_image(self, content: bytes, page: int) -> OCRPage:
        try:
            import pytesseract
            from PIL import Image

            text = pytesseract.image_to_string(Image.open(BytesIO(content))).strip()
        except Exception as exc:
            raise OCRProviderError("Image OCR requires Pillow and Tesseract") from exc
        return OCRPage(page=page, text=text, readable=bool(text), source="ocr" if text else "unreadable")


def _field(value, confidence: float, page: int, locator: str) -> dict:
    return {"value": value, "confidence": confidence, "sources": [{"page": page, "locator": locator}]}


class LocalRuleBasedProvider:
    """Free deterministic fallback that only extracts explicitly labelled values."""

    name = "local-labelled-text"
    _date = r"(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})"
    _incoterms = "EXW|FOB|CIF|CFR|FCA|DAP|DDP|CIP|DPU"

    @staticmethod
    def _column_values(
        pages: list[OCRPage], labels: tuple[str, ...]
    ) -> list[tuple[str, int, str]] | None:
        """Read a table whose labels are emitted as one row and values as the next row."""

        expected = tuple(label.casefold() for label in labels)
        for page in pages:
            if not page.readable:
                continue
            lines = [line.strip() for line in page.text.splitlines()]
            normalized = [line.casefold() for line in lines]
            for index in range(len(lines) - (len(labels) * 2) + 1):
                if tuple(normalized[index : index + len(labels)]) != expected:
                    continue
                value_start = index + len(labels)
                values = lines[value_start : value_start + len(labels)]
                if all(values):
                    return [
                        (value, page.page, f"line:{value_start + offset + 1}")
                        for offset, value in enumerate(values)
                    ]
        return None

    @staticmethod
    def _block_value(
        pages: list[OCRPage], heading: str, stop_headings: tuple[str, ...]
    ) -> tuple[str, int, str] | None:
        """Read the first value in a labelled party block, skipping table labels."""

        heading = heading.casefold()
        stops = {value.casefold() for value in stop_headings}
        ignored = {"company", "address"}
        for page in pages:
            if not page.readable:
                continue
            lines = [line.strip() for line in page.text.splitlines()]
            for index, line in enumerate(lines):
                if line.casefold() != heading:
                    continue
                for value_index in range(index + 1, len(lines)):
                    candidate = lines[value_index]
                    if candidate.casefold() in stops:
                        break
                    if candidate and candidate.casefold() not in ignored:
                        return candidate.split("<br/>", 1)[0].strip(), page.page, f"line:{value_index + 1}"
        return None

    @staticmethod
    def _party_pair(
        pages: list[OCRPage], heading: str
    ) -> tuple[tuple[str, int, str], tuple[str, int, str]] | None:
        """Read the two company values in an exporter/shipper and consignee block."""

        for page in pages:
            if not page.readable:
                continue
            lines = [line.strip() for line in page.text.splitlines()]
            for index, line in enumerate(lines):
                if line.casefold() != heading.casefold():
                    continue
                consignee_index = next(
                    (
                        candidate_index
                        for candidate_index in range(index + 1, len(lines))
                        if lines[candidate_index].casefold() == "consignee"
                    ),
                    None,
                )
                if consignee_index is None:
                    continue
                values = [
                    value.split("<br/>", 1)[0].strip()
                    for value in lines[consignee_index + 1 : consignee_index + 3]
                    if value
                ]
                if len(values) == 2:
                    return (
                        (values[0], page.page, f"line:{consignee_index + 2}"),
                        (values[1], page.page, f"line:{consignee_index + 3}"),
                    )
        return None

    @staticmethod
    def _number(value: str) -> str | None:
        match = re.search(r"-?\d[\d,]*(?:\.\d+)?", value)
        return match.group(0) if match else None

    @classmethod
    def _date_from_text(cls, value: str) -> date | None:
        for format_string in (
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d %B %Y",
            "%d %b %Y",
        ):
            try:
                return datetime.strptime(value.strip().replace("/", "-"), format_string).date()
            except ValueError:
                continue
        return None

    def extract(self, pages: list[OCRPage], document_type: DocumentType) -> ExtractionResult:
        def find(pattern: str):
            for page in pages:
                if not page.readable:
                    continue
                match = re.search(pattern, page.text, flags=re.IGNORECASE | re.MULTILINE)
                if match:
                    return match.group(1).strip(), page.page, f"text:{match.start()}"
            return None

        def string_from_found(found, confidence: float = 0.92) -> ExtractedString:
            return ExtractedString() if not found else ExtractedString(**_field(found[0], confidence, found[1], found[2]))

        def decimal_from_found(found, confidence: float = 0.9) -> ExtractedDecimal:
            if not found:
                return ExtractedDecimal()
            number = self._number(found[0])
            if number is None:
                return ExtractedDecimal()
            try:
                value = Decimal(number.replace(",", ""))
            except InvalidOperation:
                return ExtractedDecimal()
            return ExtractedDecimal(**_field(value, confidence, found[1], found[2]))

        def integer_from_found(found, confidence: float = 0.9) -> ExtractedInteger:
            if not found:
                return ExtractedInteger()
            number = self._number(found[0])
            if number is None:
                return ExtractedInteger()
            try:
                value = int(number.replace(",", ""))
            except ValueError:
                return ExtractedInteger()
            return ExtractedInteger(**_field(value, confidence, found[1], found[2]))

        invoice_columns = self._column_values(
            pages, ("Invoice date", "Currency", "Origin", "Destination")
        )
        shipment_columns = None
        if document_type == DocumentType.INVOICE:
            shipment_columns = self._column_values(
                pages, ("Packages", "Net weight", "Gross weight", "Delivery terms")
            )
        elif document_type == DocumentType.PACKING_LIST:
            shipment_columns = self._column_values(
                pages, ("Packages", "Net weight", "Gross weight", "Dimensions")
            )
        elif document_type == DocumentType.BILL_OF_LADING:
            shipment_columns = self._column_values(
                pages, ("Packages", "Description", "Gross weight", "Marks")
            )

        invoice_date_found = invoice_columns[0] if invoice_columns else find(
            r"(?:invoice\s+date|date\s+of\s+invoice)\s*[:#-]?\s*(" + self._date + r")"
        )
        parsed_date = ExtractedDate()
        if invoice_date_found:
            parsed = self._date_from_text(invoice_date_found[0])
            if parsed:
                parsed_date = ExtractedDate(**_field(parsed, 0.9, invoice_date_found[1], invoice_date_found[2]))

        invoice_number = find(
            r"(?:invoice\s*(?:no|number)|inv\.?\s*no\.?|document\s+reference)\s*[:#-]\s*([A-Z0-9][A-Z0-9-]*)"
        )
        invoice_currency = invoice_columns[1] if invoice_columns else find(
            r"currency\s*[:#-]\s*([A-Z]{3})"
        )
        if invoice_currency and not re.fullmatch(r"[A-Z]{3}", invoice_currency[0], re.IGNORECASE):
            currency_match = re.search(r"\b([A-Z]{3})\b", invoice_currency[0])
            invoice_currency = (
                (currency_match.group(1), invoice_currency[1], invoice_currency[2])
                if currency_match
                else None
            )

        incoterm_found = find(
            rf"(?:incoterm|delivery\s+terms)\s*[:#-]\s*({self._incoterms})\b"
        )
        if not incoterm_found and shipment_columns and document_type == DocumentType.INVOICE:
            term_match = re.search(rf"\b({self._incoterms})\b", shipment_columns[3][0], re.IGNORECASE)
            if term_match:
                incoterm_found = (term_match.group(1).upper(), shipment_columns[3][1], shipment_columns[3][2])

        total_found = find(
            r"(?:invoice\s+total|grand\s+total|total\s+amount)\s*[:#-]\s*([\d,.]+)"
        )

        line_items: list[LineItem] = []
        for page in pages:
            if not page.readable:
                continue
            for line_number, line in enumerate(page.text.splitlines(), start=1):
                match = re.match(r"^\s*(.+?)\s*[|\t]\s*(\d+(?:\.\d+)?)\s*[|\t]\s*(\d+(?:\.\d+)?)\s*(?:[|\t]\s*(\d{4,8}))?\s*$", line)
                if not match:
                    continue
                source = {"page": page.page, "locator": f"line:{line_number}"}
                line_items.append(LineItem(
                    description=ExtractedString(value=match.group(1).strip(), confidence=0.82, sources=[source]),
                    quantity=ExtractedDecimal(value=Decimal(match.group(2)), confidence=0.82, sources=[source]),
                    unit_price=ExtractedDecimal(value=Decimal(match.group(3)), confidence=0.82, sources=[source]),
                    hsn_code=ExtractedString(value=match.group(4), confidence=0.82, sources=[source]) if match.group(4) else ExtractedString(),
                ))

            lines = [line.strip() for line in page.text.splitlines()]
            header_index = next(
                (
                    index
                    for index in range(len(lines) - 4)
                    if lines[index : index + 5]
                    == ["Line", "Description", "Quantity", "Unit price", "Line total"]
                ),
                None,
            )
            if header_index is not None:
                index = header_index + 5
                while index + 3 < len(lines) and lines[index] != "TOTAL":
                    if not re.fullmatch(r"\d+", lines[index]):
                        index += 1
                        continue
                    source = {"page": page.page, "locator": f"line:{index + 1}"}
                    quantity = self._number(lines[index + 2])
                    unit_price = self._number(lines[index + 3])
                    if quantity is None or unit_price is None:
                        index += 1
                        continue
                    line_items.append(
                        LineItem(
                            description=ExtractedString(value=lines[index + 1], confidence=0.82, sources=[source]),
                            quantity=ExtractedDecimal(value=Decimal(quantity.replace(",", "")), confidence=0.82, sources=[source]),
                            unit_price=ExtractedDecimal(value=Decimal(unit_price.replace(",", "")), confidence=0.82, sources=[source]),
                        )
                    )
                    index += 4
                if total_found is None and index < len(lines) and lines[index] == "TOTAL":
                    if index + 2 < len(lines):
                        total_found = (lines[index + 2], page.page, f"line:{index + 3}")

        containers = []
        for page in pages:
            if page.readable:
                containers.extend(
                    ExtractedString(value=match.group(1), confidence=0.9, sources=[{"page": page.page, "locator": f"text:{match.start()}"}])
                    for match in re.finditer(r"(?:container(?:s)?|container\s+no(?:s|\.)?)\s*[:#-]?\s*([A-Z0-9-]{6,})", page.text, re.IGNORECASE)
                )
        if document_type == DocumentType.INVOICE:
            supplier_found = self._block_value(pages, "Seller / Exporter", ("Buyer / Importer",)) or find(
                r"(?:supplier|seller)\s*[:#-]\s*([^\n]+)"
            )
            importer_found = self._block_value(pages, "Buyer / Importer", ("Invoice date",)) or find(
                r"(?:importer|buyer)\s*[:#-]\s*([^\n]+)"
            )
        else:
            pair = self._party_pair(
                pages,
                "Exporter / Consignee" if document_type == DocumentType.PACKING_LIST else "Shipper / Consignee",
            )
            supplier_found = pair[0] if pair else find(r"(?:supplier|shipper|exporter)\s*[:#-]\s*([^\n]+)")
            importer_found = pair[1] if pair else find(r"(?:consignee|buyer|importer)\s*[:#-]\s*([^\n]+)")

        return ExtractionResult(
            document_type=document_type,
            pages=pages,
            parties=PartyFields(
                importer=string_from_found(importer_found),
                supplier=string_from_found(supplier_found),
                consignee=string_from_found(importer_found) if document_type != DocumentType.INVOICE else ExtractedString(),
                exporter=string_from_found(supplier_found) if document_type != DocumentType.INVOICE else ExtractedString(),
            ),
            invoice=(
                InvoiceFields(
                    number=string_from_found(invoice_number),
                    date=parsed_date,
                    currency=string_from_found(invoice_currency),
                    incoterm=string_from_found(incoterm_found),
                    total=decimal_from_found(total_found),
                )
                if document_type == DocumentType.INVOICE
                else InvoiceFields()
            ),
            line_items=line_items,
            shipment=ShipmentFields(
                packages=integer_from_found(shipment_columns[0] if shipment_columns else find(r"(?:total\s+)?packages?\s*[:#-]?\s*([\d,]+)")),
                gross_weight_kg=decimal_from_found(shipment_columns[2] if shipment_columns else find(r"gross\s+weight(?:\s*\(\s*kg\s*\))?\s*[:#-]?\s*([\d,.]+)")),
                net_weight_kg=decimal_from_found(shipment_columns[1] if shipment_columns else find(r"net\s+weight(?:\s*\(\s*kg\s*\))?\s*[:#-]?\s*([\d,.]+)")),
                containers=containers,
            ),
        )


class OpenAICompatibleProvider:
    """Optional provider adapter, selected only through explicit environment settings."""

    name = "openai-compatible"

    def __init__(self, api_url: str, api_key: str, model: str, timeout_seconds: int) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def extract(self, pages: list[OCRPage], document_type: DocumentType) -> dict:
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [{
                "role": "user",
                "content": "Return JSON only. Extract only values explicitly present. Include confidence 0..1 and sources with page and locator. Missing values must be null with empty sources. Do not approve or verify anything.\n" + json.dumps({"document_type": document_type.value, "pages": [page.model_dump(mode="json") for page in pages]}, ensure_ascii=False),
            }],
        }
        request = urllib.request.Request(self.api_url, data=json.dumps(payload).encode("utf-8"), headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
            return json.loads(body["choices"][0]["message"]["content"])
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AIProviderError("Configured AI provider failed or returned malformed JSON") from exc
