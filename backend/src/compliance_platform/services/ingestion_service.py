"""Ingestion service: orchestrates parse -> chunk -> validate -> embed -> store.

See services/README.md: business logic lives here, depends on
repositories/ and ai/ through their interfaces, and is called by api/.
This module has no FastAPI or LanceDB import in it directly — that
boundary is what keeps it unit-testable without a running server or a
real vector store (a fake VectorRepository / Embedder is enough).
"""

from __future__ import annotations

import logging
from typing import Protocol

from compliance_platform.ai.embeddings import Embedder
from compliance_platform.core.config import Settings
from compliance_platform.models.assessment import Document
from compliance_platform.models.schemas import IngestionResult, ParseStatus
from compliance_platform.repositories.vector_repository import VectorRepository
from compliance_platform.services import chunking, document_parsers

_logger = logging.getLogger(__name__)


class UnsupportedDocumentError(Exception):
    """Raised when a document cannot be usefully ingested (e.g. scanned
    PDF, encoding failure, empty content). Distinct from a parser bug:
    this is an expected, user-facing outcome the API layer should turn
    into a 4xx response, not a 500 (see api/ingestion.py).
    """

    def __init__(self, status: ParseStatus, warnings: list[str]) -> None:
        self.status = status
        self.warnings = warnings
        super().__init__(
            f"Document could not be ingested: {status.value} ({'; '.join(warnings) or 'no detail'})"
        )


class UnknownSupersededDocumentError(Exception):
    """Raised when supersedes_document_id doesn't refer to any document
    actually present in the vector store (Document-registry existence,
    not FK existence — the same "has real chunks in the vector store"
    check assessment_service.py's EvidenceDocumentNotIngestedError
    already uses, so a document ingested before the Document registry
    (ADR-0039) existed can still legitimately be named as superseded).
    """

    def __init__(self, document_id: str) -> None:
        self.document_id = document_id
        super().__init__(
            f"supersedes_document_id '{document_id}' does not refer to any ingested document."
        )


class DocumentRepositoryProtocol(Protocol):
    def create_document(self, document: Document) -> Document: ...
    def get_document(self, document_id: str) -> Document | None: ...


class IngestionService:
    def __init__(
        self,
        settings: Settings,
        vector_repository: VectorRepository,
        embedder: Embedder,
        document_repository: DocumentRepositoryProtocol,
    ) -> None:
        self._settings = settings
        self._vector_repository = vector_repository
        self._embedder = embedder
        self._documents = document_repository

    def ingest(
        self,
        filename: str,
        content: bytes,
        submitter: str | None = None,
        supersedes_document_id: str | None = None,
    ) -> IngestionResult:
        if len(content) > self._settings.max_upload_bytes:
            raise ValueError(
                f"File exceeds maximum upload size of {self._settings.max_upload_bytes} bytes."
            )

        # Document versioning (ADR-0039): supersedes_document_id is
        # explicit and human-declared, never inferred -- but it must
        # still refer to something real. Checked against the vector
        # store, not the Document table, so a document ingested before
        # this feature existed can still be named as superseded.
        if supersedes_document_id is not None and not self._vector_repository.chunks_for_document(
            supersedes_document_id
        ):
            raise UnknownSupersededDocumentError(supersedes_document_id)

        parsed = document_parsers.parse_document(filename, content, submitter=submitter)

        if parsed.parse_status != ParseStatus.SUCCESS:
            # A failed/unsupported/empty parse is a real, expected outcome
            # per the document-parsing skill — never silently continue past it.
            _logger.warning(
                "ingestion rejected filename=%s status=%s", filename, parsed.parse_status
            )
            raise UnsupportedDocumentError(parsed.parse_status, parsed.parse_warnings)

        # Decompression-bomb ceiling on EXTRACTED text (security hardening,
        # controlled-pilot readiness audit §A.12). Complements
        # document_parsers.py's DOCX-specific pre-check: this one applies
        # uniformly to every format, including PDF, whose internal stream
        # compression has no equivalent cheap pre-extraction check.
        if len(parsed.raw_text) > self._settings.max_extracted_text_chars:
            _logger.warning(
                "ingestion rejected filename=%s reason=decompression_bomb_ceiling extracted_chars=%d",
                filename,
                len(parsed.raw_text),
            )
            raise UnsupportedDocumentError(
                ParseStatus.FAILED,
                [
                    f"Extracted text is {len(parsed.raw_text)} characters, exceeding the "
                    f"{self._settings.max_extracted_text_chars}-character safety ceiling. "
                    "Rejected to guard against a decompression-bomb-style malformed document."
                ],
            )

        chunks = chunking.chunk_document(
            document_id=parsed.metadata.document_id,
            text=parsed.raw_text,
            settings=self._settings,
        )

        if not chunks:
            raise UnsupportedDocumentError(
                ParseStatus.EMPTY,
                ["Document parsed successfully but produced zero chunks above the minimum length."],
            )

        vectors = self._embedder.embed([chunk.text for chunk in chunks])
        self._vector_repository.add_chunks(chunks, vectors)

        self._documents.create_document(
            Document(
                id=parsed.metadata.document_id,
                filename=parsed.metadata.filename,
                file_type=parsed.metadata.file_type.value,
                content_hash=parsed.metadata.content_hash,
                submitter=submitter,
                supersedes_document_id=supersedes_document_id,
            )
        )

        _logger.info(
            "document ingested id=%s filename=%s file_type=%s chunk_count=%d supersedes=%s",
            parsed.metadata.document_id,
            filename,
            parsed.metadata.file_type,
            len(chunks),
            supersedes_document_id,
        )
        return IngestionResult(
            document_id=parsed.metadata.document_id,
            filename=parsed.metadata.filename,
            parse_status=parsed.parse_status,
            parse_warnings=parsed.parse_warnings,
            chunk_count=len(chunks),
            embedding_backend=self._embedder.backend_name,
        )
