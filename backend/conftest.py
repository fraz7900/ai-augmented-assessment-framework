"""Shared pytest fixtures for both src/**/tests (unit) and tests/ (integration).

Fixtures generate binary test documents (DOCX, PDF) at test time rather
than committing binary fixtures to the repo, per notebooks/README.md's
principle that anything decision-relevant should be reproducible, not
an opaque checked-in artifact.
"""

from __future__ import annotations

import io

import pytest
from docx import Document as DocxDocument
from fpdf import FPDF

SAMPLE_HEADING_TEXT = "Sample Policy"
SAMPLE_BODY_TEXT = "This is a synthetic sentence used only for pipeline testing."


@pytest.fixture
def sample_docx_bytes() -> bytes:
    doc = DocxDocument()
    doc.add_heading(SAMPLE_HEADING_TEXT, level=1)
    doc.add_paragraph(SAMPLE_BODY_TEXT)
    doc.add_heading("Second Section", level=1)
    doc.add_paragraph("A second synthetic paragraph for chunk-boundary testing purposes only.")
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 10, SAMPLE_BODY_TEXT * 5)
    return bytes(pdf.output())


@pytest.fixture
def scanned_like_pdf_bytes() -> bytes:
    """A syntactically valid PDF with an essentially empty page, standing
    in for a scanned/image-only PDF to test the UNSUPPORTED_SCANNED
    detection heuristic in services/document_parsers.py without needing
    a real scanned document or an OCR dependency the MVP doesn't have.
    """
    pdf = FPDF()
    pdf.add_page()
    return bytes(pdf.output())


@pytest.fixture
def invalid_utf8_bytes() -> bytes:
    return b"Some text with an invalid byte: \xff\xfe more text after it"
