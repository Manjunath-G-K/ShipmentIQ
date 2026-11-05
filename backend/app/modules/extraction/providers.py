"""Replaceable local OCR and AI extraction provider implementations."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime
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

    def extract(self, pages: list[OCRPage], document_type: DocumentType) -> ExtractionResult:
        text = "\n".join(page.text for page in pages if page.readable)

        def find(pattern: str):
            for page in pages:
                if not page.readable:
                    continue
                match = re.search(pattern, page.text, flags=re.IGNORECASE | re.MULTILINE)
                if match:
                    return match.group(1).strip(), page.page, f"text:{match.start()}"
            return None

        def string_field(pattern: str, confidence: float = 0.92) -> ExtractedString:
            found = find(pattern)
            return ExtractedString() if not found else ExtractedString(**_field(found[0], confidence, found[1], found[2]))

        def decimal_field(pattern: str, confidence: float = 0.9) -> ExtractedDecimal:
            found = find(pattern)
            if not found:
                return ExtractedDecimal()
            try:
                value = Decimal(found[0].replace(",", ""))
            except InvalidOperation:
                return ExtractedDecimal()
            return ExtractedDecimal(**_field(value, confidence, found[1], found[2]))

        def integer_field(pattern: str, confidence: float = 0.9) -> ExtractedInteger:
            found = find(pattern)
            if not found:
                return ExtractedInteger()
            try:
                value = int(found[0].replace(",", ""))
            except ValueError:
                return ExtractedInteger()
            return ExtractedInteger(**_field(value, confidence, found[1], found[2]))

        parsed_date = ExtractedDate()
        invoice_date = find(r"(?:invoice\s+date|date\s+of\s+invoice)\s*[:#-]?\s*" + self._date)
        if invoice_date:
            raw = invoice_date[0].replace("/", "-")
            for format_string, confidence in (("%Y-%m-%d", 0.9), ("%d-%m-%Y", 0.85)):
                try:
                    parsed_date = ExtractedDate(**_field(datetime.strptime(raw, format_string).date(), confidence, invoice_date[1], invoice_date[2]))
                    break
                except ValueError:
                    continue

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

        containers = []
        for page in pages:
            if page.readable:
                containers.extend(
                    ExtractedString(value=match.group(1), confidence=0.9, sources=[{"page": page.page, "locator": f"text:{match.start()}"}])
                    for match in re.finditer(r"(?:container(?:s)?|container\s+no(?:s|\.)?)\s*[:#-]?\s*([A-Z0-9-]{6,})", page.text, re.IGNORECASE)
                )
        return ExtractionResult(
            document_type=document_type,
            pages=pages,
            parties=PartyFields(
                importer=string_field(r"(?:importer|buyer)\s*[:#-]\s*([^\n]+)"),
                supplier=string_field(r"(?:supplier|seller)\s*[:#-]\s*([^\n]+)"),
                consignee=string_field(r"consignee\s*[:#-]\s*([^\n]+)"),
                exporter=string_field(r"exporter\s*[:#-]\s*([^\n]+)"),
            ),
            invoice=InvoiceFields(
                number=string_field(r"(?:invoice\s*(?:no|number)|inv\.?\s*no\.?)\s*[:#-]\s*([^\n]+)"),
                date=parsed_date,
                currency=string_field(r"currency\s*[:#-]\s*([A-Z]{3})"),
                incoterm=string_field(r"incoterm\s*[:#-]\s*(EXW|FOB|CIF|CFR|FCA|DAP|DDP|CIP|DPU)"),
                total=decimal_field(r"(?:invoice\s+total|grand\s+total|total\s+amount)\s*[:#-]\s*([\d,.]+)"),
            ),
            line_items=line_items,
            shipment=ShipmentFields(
                packages=integer_field(r"(?:total\s+)?packages?\s*[:#-]\s*([\d,]+)"),
                gross_weight_kg=decimal_field(r"gross\s+weight(?:\s*\(\s*kg\s*\))?\s*[:#-]\s*([\d,.]+)"),
                net_weight_kg=decimal_field(r"net\s+weight(?:\s*\(\s*kg\s*\))?\s*[:#-]\s*([\d,.]+)"),
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
