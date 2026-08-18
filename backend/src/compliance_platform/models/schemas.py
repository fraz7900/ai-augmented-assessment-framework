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
    # Parsed successfully, but the text was recovered by OCR from a
    # scanned/image-only PDF rather than read from a real text layer
    # (ADR-0055). Distinct from SUCCESS on purpose: OCR output is
    # approximate, and a reviewer quoting it as evidence is entitled to
    # know that before relying on it. Downstream code that accepts
    # SUCCESS must decide about this case explicitly rather than
    # inheriting an answer.
    SUCCESS_OCR = "success_ocr"
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
    # Row boundaries (Sprint 18, ADR-0052): (char_start, char_end, row_number,
    # sheet_name) per rendered "Row N: ..." line, relative to raw_text --
    # populated only by parse_xlsx/parse_csv (every other format has no row
    # concept). sheet_name is always None for CSV (no sheet concept); XLSX
    # sets it per the sheet the row came from. None (not an empty list) for
    # every non-tabular format, same "format doesn't apply" convention as
    # page_boundaries above.
    row_boundaries: list[tuple[int, int, int, str | None]] | None = None


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
    # Row/sheet provenance (Sprint 18, ADR-0052): the 1-indexed spreadsheet
    # row (matching the "Row N" label already rendered into the chunk's own
    # text by document_parsers.py) and, for XLSX, the sheet it came from.
    # Both None for every non-tabular format. sheet_name is also already
    # available via section_reference for XLSX chunks (structure-aware
    # chunking's heading detection already captures it) -- this is a
    # dedicated, typed field so a consumer doesn't need to know the source
    # file_type to know what section_reference means for this document.
    # A chunk is attributed to the FIRST row it actually contains, not
    # necessarily the row nearest its char_start -- unlike page_number's
    # "starting page only" simplification, a chunk that opens on a sheet's
    # "# Heading" line (common: the heading is the first thing in every
    # sheet's section, so most sheets' opening chunk starts there, not on
    # row 2) would otherwise always report row_number=None despite plainly
    # containing real row data.
    row_number: int | None = None
    sheet_name: str | None = None


class IngestionResult(BaseModel):
    """Returned by the ingestion API and service layer."""

    document_id: str
    filename: str
    parse_status: ParseStatus
    parse_warnings: list[str] = Field(default_factory=list)
    chunk_count: int
    embedding_backend: str
    parser_version: str


class SealVerificationStatus(StrEnum):
    """The outcome of checking a finalized assessment against its seal.

    Four values, not a boolean: "no seal exists" and "the seal does not
    match" are opposite situations that a boolean would collapse into
    the same false. An unsealed assessment is unverified, which is not
    the same as untrustworthy; an altered one is a finding.
    """

    VERIFIED = "verified"
    ALTERED = "altered"
    # Never finalized, or finalized before sealing existed. Deliberately
    # not back-filled — see Assessment.sealed_digest.
    UNSEALED = "unsealed"
    # Sealed by a build that knows a payload shape this one does not.
    # Reported as its own state rather than as ALTERED, because the
    # record may be perfectly intact and this build simply cannot say.
    UNVERIFIABLE = "unverifiable"


class SealVerification(BaseModel):
    """Whether a finalized assessment still matches the seal written at
    finalization (R-12). Both digests are returned so a holder of an
    exported report can compare against what the export printed."""

    assessment_id: str
    status: SealVerificationStatus
    sealed_digest: str | None = None
    computed_digest: str | None = None
    sealed_at: datetime | None = None
    seal_version: str | None = None
    detail: str


class FinalizationBlockerCategory(StrEnum):
    """Why an assessment cannot be finalized yet (ADR-0058).

    A closed enum rather than free-text messages: the frontend disables
    a button and renders a checklist from these, and parsing English
    prose to decide that would break the first time the wording is
    improved.
    """

    PENDING_AI_REVIEW = "pending_ai_review"
    UNRESOLVED_EVIDENCE_REQUEST = "unresolved_evidence_request"
    UNSUPPORTED_SATISFIED_FINDING = "unsupported_satisfied_finding"
    UNSUPPORTED_NOT_APPLICABLE_FINDING = "unsupported_not_applicable_finding"
    FRAMEWORK_VERSION_UNRESOLVED = "framework_version_unresolved"


class FinalizationBlocker(BaseModel):
    """One reason finalization is blocked, with the specific items to fix.

    `affected_ids` holds evidence-link ids, evidence-request ids or
    practice references depending on the category — whichever the
    reviewer needs to act on. It is capped by the service so a pathological
    assessment cannot return an unbounded response body; `count` is always
    the true total, so a caller can tell "3 of 300" from "3 of 3".
    """

    category: FinalizationBlockerCategory
    count: int
    affected_ids: list[str] = []
    summary: str


class FinalizationReadiness(BaseModel):
    """Whether an assessment may be finalized, and what stands in the way.

    Gaps do NOT appear here. A finalized assessment that reports an
    organization as non-compliant is a legitimate, complete result — the
    point of the platform. What blocks finalization is unfinished
    *review work*: unreviewed AI proposals, outstanding evidence
    requests, and findings that move a score without the evidence to
    support it.
    """

    assessment_id: str
    status: str
    is_ready: bool
    blockers: list[FinalizationBlocker] = []


class DocumentSummary(BaseModel):
    """One row in a list of ingested documents — what a chooser needs to
    let a reviewer recognise a document, and nothing more.

    Separate from DocumentDetail rather than reusing it: the list is
    resolved with a BULK supersession lookup that answers "is this
    superseded" without identifying the superseding document, so this
    carries an honest `is_superseded` boolean instead of a
    `superseded_by_document_id` that could only be filled with a
    placeholder. content_hash is omitted too — it identifies a document
    to a machine, not to a human picking one off a list.
    """

    id: str
    filename: str
    file_type: str
    submitter: str | None = None
    uploaded_at: datetime
    is_superseded: bool = False
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
