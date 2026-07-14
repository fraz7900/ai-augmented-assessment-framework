from __future__ import annotations

import pytest

from compliance_platform.models.schemas import FileType, ParseStatus
from compliance_platform.services import document_parsers


def test_parse_plain_text_success() -> None:
    parsed = document_parsers.parse_document("notes.txt", b"Some real evidence content here.")
    assert parsed.parse_status == ParseStatus.SUCCESS
    assert parsed.metadata.file_type == FileType.TXT
    assert "evidence" in parsed.raw_text


def test_parse_plain_text_empty() -> None:
    parsed = document_parsers.parse_document("empty.txt", b"   \n\n  ")
    assert parsed.parse_status == ParseStatus.EMPTY


def test_parse_plain_text_handles_invalid_utf8_gracefully(invalid_utf8_bytes: bytes) -> None:
    parsed = document_parsers.parse_document("weird.txt", invalid_utf8_bytes)
    # latin-1 fallback can decode any byte sequence, so this still succeeds,
    # but must carry a warning flagging the fallback for human review.
    assert parsed.parse_status == ParseStatus.SUCCESS
    assert parsed.parse_warnings


def test_parse_markdown_dispatches_as_markdown() -> None:
    parsed = document_parsers.parse_document("policy.md", b"# Heading\nBody text.")
    assert parsed.metadata.file_type == FileType.MARKDOWN
    assert parsed.parse_status == ParseStatus.SUCCESS


def test_parse_docx_success(sample_docx_bytes: bytes) -> None:
    parsed = document_parsers.parse_document("policy.docx", sample_docx_bytes)
    assert parsed.parse_status == ParseStatus.SUCCESS
    assert "# Sample Policy" in parsed.raw_text
    assert "# Second Section" in parsed.raw_text


def test_parse_pdf_success(sample_pdf_bytes: bytes) -> None:
    parsed = document_parsers.parse_document("policy.pdf", sample_pdf_bytes)
    assert parsed.parse_status == ParseStatus.SUCCESS
    assert len(parsed.raw_text.strip()) > 0


def test_parse_pdf_detects_scanned_document(scanned_like_pdf_bytes: bytes) -> None:
    parsed = document_parsers.parse_document("scanned.pdf", scanned_like_pdf_bytes)
    assert parsed.parse_status == ParseStatus.UNSUPPORTED_SCANNED
    assert parsed.parse_warnings


def test_parse_unsupported_extension_raises() -> None:
    with pytest.raises(ValueError):
        document_parsers.parse_document("archive.zip", b"PK\x03\x04")


def test_content_hash_is_deterministic_but_document_id_is_not() -> None:
    content = b"identical content"
    p1 = document_parsers.parse_document("a.txt", content)
    p2 = document_parsers.parse_document("b.txt", content)
    assert p1.metadata.content_hash == p2.metadata.content_hash
    assert p1.metadata.document_id != p2.metadata.document_id
