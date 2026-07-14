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


class ParsedDocument(BaseModel):
    """Output of services/document_parsers.py, before chunking."""

    metadata: SourceDocumentMetadata
    raw_text: str
    parse_status: ParseStatus
    parse_warnings: list[str] = Field(default_factory=list)


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


class IngestionResult(BaseModel):
    """Returned by the ingestion API and service layer."""

    document_id: str
    filename: str
    parse_status: ParseStatus
    parse_warnings: list[str] = Field(default_factory=list)
    chunk_count: int
    embedding_backend: str
