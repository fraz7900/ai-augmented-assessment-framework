"""Pydantic schemas for the ingestion pipeline.

Distinct from framework_mapping/ (which holds *what a C2M2/NIST practice
is*, as data per ADR-0002). This module defines *how an ingested document,
chunk, or ingestion result is shaped* as an API/internal object. See
models/README.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class FileType(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MARKDOWN = "md"
    XLSX = "xlsx"
    CSV = "csv"


class ParseStatus(StrEnum):
    SUCCESS = "success"
    UNSUPPORTED_SCANNED = "unsupported_scanned"
    ENCODING_FAILURE = "encoding_failure"
    EMPTY = "empty"
    FAILED = "failed"


class ChunkingStrategy(StrEnum):
    STRUCTURE_AWARE = "structure_aware"
    FIXED_WINDOW = "fixed_window"


class SourceDocumentMetadata(BaseModel):
    """Required metadata per the data-cleaning skill: source id, filename,
    upload timestamp, submitter, content hash. Losing any of these breaks
    the citation requirement in the evidence-extraction skill downstream.
    """

    document_id: str
    filename: str
    file_type: FileType
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    submitter: str | None = None
    content_hash: str
    # Reproducibility provenance (Sprint 18, ADR-0042): which real,
    # installed library version actually parsed this document --
    # "pypdf==6.14.2", not a hand-maintained internal counter someone
    # could forget to bump. If that library is later upgraded and starts
    # parsing PDFs even slightly differently, this field is the honest
    # answer to "was this evidence extracted under the current parser
    # or an older one" -- the same "framework_version pins what mattered
    # at the time" reasoning ADR-0031 already established, applied to
    # the parsing library instead of the framework schema.
    parser_version: str


class ParsedDocument(BaseModel):
    """Output of services/document_parsers.py, before chunking."""

    metadata: SourceDocumentMetadata
    raw_text: str
    parse_status: ParseStatus
    parse_warnings: list[str] = Field(default_factory=list)
    # Page boundaries (Sprint 18, ADR-0042): (char_start, char_end) per
    # page, relative to raw_text -- populated only by parse_pdf (every
    # other format has no page concept). None, not an empty list, when
    # the format doesn't apply, so a caller can distinguish "this format
    # has no pages" from "this PDF had zero pages" (already its own
    # EMPTY status).
    page_boundaries: list[tuple[int, int]] | None = None


class EvidenceChunk(BaseModel):
    """A single chunk of a processed document, with the citation-bearing
    fields evidence-extraction (Sprint 2+) will depend on.
    """

    chunk_id: str
    document_id: str
    chunk_index: int
    text: str
    chunking_strategy: ChunkingStrategy
    section_reference: str | None = None
    char_start: int
    char_end: int
    # Sprint 18, ADR-0042: the 1-indexed PDF page this chunk starts on
    # (raw_text's page boundaries no longer discarded before chunking --
    # controlled-pilot readiness audit §A.3). None for every non-PDF
    # format. A chunk that spans a page boundary (fixed-window chunking
    # doesn't respect them) is attributed to its starting page only --
    # a disclosed simplification, not full multi-page provenance.
    page_number: int | None = None


class IngestionResult(BaseModel):
    """Returned by the ingestion API and service layer."""

    document_id: str
    filename: str
    parse_status: ParseStatus
    parse_warnings: list[str] = Field(default_factory=list)
    chunk_count: int
    embedding_backend: str
    parser_version: str


class DocumentDetail(BaseModel):
    """Document versioning (Sprint 18, ADR-0039): the durable record of
    one ingested document, plus the reverse lookup a reviewer actually
    needs -- "has this document since been superseded by a newer
    upload?" -- computed at read time, not stored (only the forward
    supersedes_document_id declaration is stored, on the newer document).
    """

    id: str
    filename: str
    file_type: str
    content_hash: str
    submitter: str | None = None
    uploaded_at: datetime
    supersedes_document_id: str | None = None
    superseded_by_document_id: str | None = None
    parser_version: str
