"""Document parsers: PDF, DOCX, TXT/Markdown.

Implements the failure-mode handling required by the document-parsing
skill: a parser must distinguish "parsed successfully but short/sparse"
from "failed to parse, output is garbage" rather than always returning a
string and calling it done.
"""

from __future__ import annotations

import hashlib
import io
import uuid

from docx import Document as DocxDocument
from pypdf import PdfReader

from compliance_platform.models.schemas import (
    FileType,
    ParsedDocument,
    ParseStatus,
    SourceDocumentMetadata,
)

# Below this many characters per page, a "successfully parsed" PDF is
# almost certainly a scanned/image-only document that happened to extract
# a few stray characters (e.g. a running header), not real text. OCR is
# explicitly out of scope for the MVP (see PROJECT_CHARTER.md MVP scope).
_MIN_CHARS_PER_PAGE = 20


def _content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _new_document_id() -> str:
    return str(uuid.uuid4())


def parse_pdf(content: bytes) -> tuple[str, ParseStatus, list[str]]:
    warnings: list[str] = []
    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception as exc:  # pypdf raises varied exception types on malformed PDFs
        return "", ParseStatus.FAILED, [f"Could not open PDF: {exc}"]

    page_count = len(reader.pages)
    if page_count == 0:
        return "", ParseStatus.EMPTY, ["PDF has zero pages."]

    page_texts: list[str] = []
    for i, page in enumerate(reader.pages):
        try:
            page_texts.append(page.extract_text() or "")
        except Exception as exc:
            warnings.append(f"Failed to extract text from page {i + 1}: {exc}")
            page_texts.append("")

    text = "\n\n".join(page_texts)
    avg_chars_per_page = len(text) / page_count

    if avg_chars_per_page < _MIN_CHARS_PER_PAGE:
        warnings.append(
            f"Average {avg_chars_per_page:.1f} extracted characters per page "
            f"across {page_count} page(s); this looks like a scanned or "
            "image-only PDF, which the MVP does not support (no OCR)."
        )
        return text, ParseStatus.UNSUPPORTED_SCANNED, warnings

    return text, ParseStatus.SUCCESS, warnings


def parse_docx(content: bytes) -> tuple[str, ParseStatus, list[str]]:
    warnings: list[str] = []
    try:
        doc = DocxDocument(io.BytesIO(content))
    except Exception as exc:
        return "", ParseStatus.FAILED, [f"Could not open DOCX: {exc}"]

    lines: list[str] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style_name = (para.style.name if para.style else "") or ""
        if style_name.lower().startswith("heading"):
            lines.append(f"# {text}")
        else:
            lines.append(text)

    full_text = "\n".join(lines)
    if not full_text.strip():
        warnings.append("DOCX contained no extractable paragraph text.")
        return full_text, ParseStatus.EMPTY, warnings

    return full_text, ParseStatus.SUCCESS, warnings


def parse_plain_text(content: bytes) -> tuple[str, ParseStatus, list[str]]:
    warnings: list[str] = []
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        warnings.append(
            "Content is not valid UTF-8; decoded with latin-1 as a fallback. "
            "Review this document for encoding issues before trusting extracted evidence."
        )
        text = content.decode("latin-1", errors="replace")
        if not text.strip():
            return "", ParseStatus.ENCODING_FAILURE, warnings

    if not text.strip():
        return text, ParseStatus.EMPTY, ["File contained no text content."]

    return text, ParseStatus.SUCCESS, warnings


_PARSERS = {
    FileType.PDF: parse_pdf,
    FileType.DOCX: parse_docx,
    FileType.TXT: parse_plain_text,
    FileType.MARKDOWN: parse_plain_text,
}

_EXTENSION_TO_FILE_TYPE = {
    "pdf": FileType.PDF,
    "docx": FileType.DOCX,
    "txt": FileType.TXT,
    "md": FileType.MARKDOWN,
}


def file_type_from_extension(filename: str) -> FileType:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext not in _EXTENSION_TO_FILE_TYPE:
        raise ValueError(f"Unsupported file extension: .{ext}")
    return _EXTENSION_TO_FILE_TYPE[ext]


def parse_document(
    filename: str,
    content: bytes,
    submitter: str | None = None,
) -> ParsedDocument:
    """Dispatch to the correct parser and wrap the result as a ParsedDocument.

    This is the single entry point services/ingestion_service.py calls. It
    never raises for a malformed document (see parser functions above) —
    it returns a status the caller must handle explicitly instead.
    """
    file_type = file_type_from_extension(filename)
    parser = _PARSERS[file_type]
    text, status, warnings = parser(content)

    metadata = SourceDocumentMetadata(
        document_id=_new_document_id(),
        filename=filename,
        file_type=file_type,
        submitter=submitter,
        content_hash=_content_hash(content),
    )

    return ParsedDocument(
        metadata=metadata,
        raw_text=text,
        parse_status=status,
        parse_warnings=warnings,
    )
