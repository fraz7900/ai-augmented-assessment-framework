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
import zipfile

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

# Content-sniffing (controlled-pilot readiness audit §A.12, security
# hardening): file-type validation was extension-only before this —
# a file renamed to a different extension went straight to that
# extension's parser regardless of its real content. Checked against
# real magic bytes / a binary-content heuristic before any format-specific
# parser ever sees the bytes, not just trusted from the filename.
_PDF_SIGNATURE = b"%PDF-"
# DOCX (OOXML) is a ZIP archive; PK\x03\x04 is a normal non-empty
# archive, PK\x05\x06 an empty one — both are genuine zip signatures.
_ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06")
_BINARY_SNIFF_BYTES = 8192


def _looks_like_binary_content(content: bytes) -> bool:
    # TXT/MD have no magic-byte signature to check; a NUL byte within the
    # first few KB is a standard, low-false-positive signal that this is
    # not real text content, however it got its .txt/.md extension. Real
    # invalid-UTF-8 text (mojibake, stray high bytes) does not typically
    # contain NUL bytes, so this does not fight the existing latin-1
    # fallback path in parse_plain_text.
    return b"\x00" in content[:_BINARY_SNIFF_BYTES]


def _content_matches_file_type(content: bytes, file_type: FileType) -> bool:
    if file_type == FileType.PDF:
        return content.startswith(_PDF_SIGNATURE)
    if file_type == FileType.DOCX:
        return content.startswith(_ZIP_SIGNATURES)
    if file_type in (FileType.TXT, FileType.MARKDOWN):
        return not _looks_like_binary_content(content)
    return True


# Decompression-bomb ceiling (same audit finding): a DOCX is a ZIP
# archive, and ZipInfo.file_size is real uncompressed-size metadata from
# the archive's own central directory -- readable without decompressing
# a single byte of entry content, so this check costs nothing close to
# what an actual decompression would. 200MB is far beyond any real policy
# document's extracted size but well below what a crafted archive could
# claim to decompress to from a small uploaded file.
_MAX_DOCX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024


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
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            total_uncompressed_bytes = sum(info.file_size for info in archive.infolist())
    except zipfile.BadZipFile as exc:
        return "", ParseStatus.FAILED, [f"Could not open DOCX: {exc}"]

    if total_uncompressed_bytes > _MAX_DOCX_UNCOMPRESSED_BYTES:
        return "", ParseStatus.FAILED, [
            f"DOCX would decompress to {total_uncompressed_bytes} bytes, exceeding the "
            f"{_MAX_DOCX_UNCOMPRESSED_BYTES}-byte safety ceiling. Rejected before extraction "
            "to guard against a decompression-bomb-style malformed file."
        ]

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

    if not _content_matches_file_type(content, file_type):
        text, status, warnings = "", ParseStatus.FAILED, [
            f"File content does not match its .{filename.rsplit('.', 1)[-1].lower()} extension "
            "(failed a magic-byte/binary-content check). Rejected before parsing, not passed to "
            "a format-specific parser expecting content it doesn't actually contain."
        ]
    else:
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
