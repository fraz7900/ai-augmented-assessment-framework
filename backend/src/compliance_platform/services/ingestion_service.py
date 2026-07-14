"""Ingestion service: orchestrates parse -> chunk -> validate -> embed -> store.

See services/README.md: business logic lives here, depends on
repositories/ and ai/ through their interfaces, and is called by api/.
This module has no FastAPI or LanceDB import in it directly — that
boundary is what keeps it unit-testable without a running server or a
real vector store (a fake VectorRepository / Embedder is enough).
"""

from __future__ import annotations

from compliance_platform.ai.embeddings import Embedder
from compliance_platform.core.config import Settings
from compliance_platform.models.schemas import IngestionResult, ParseStatus
from compliance_platform.repositories.vector_repository import VectorRepository
from compliance_platform.services import chunking, document_parsers


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


class IngestionService:
    def __init__(
        self,
        settings: Settings,
        vector_repository: VectorRepository,
        embedder: Embedder,
    ) -> None:
        self._settings = settings
        self._vector_repository = vector_repository
        self._embedder = embedder

    def ingest(
        self, filename: str, content: bytes, submitter: str | None = None
    ) -> IngestionResult:
        if len(content) > self._settings.max_upload_bytes:
            raise ValueError(
                f"File exceeds maximum upload size of {self._settings.max_upload_bytes} bytes."
            )

        parsed = document_parsers.parse_document(filename, content, submitter=submitter)

        if parsed.parse_status != ParseStatus.SUCCESS:
            # A failed/unsupported/empty parse is a real, expected outcome
            # per the document-parsing skill — never silently continue past it.
            raise UnsupportedDocumentError(parsed.parse_status, parsed.parse_warnings)

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

        return IngestionResult(
            document_id=parsed.metadata.document_id,
            filename=parsed.metadata.filename,
            parse_status=parsed.parse_status,
            parse_warnings=parsed.parse_warnings,
            chunk_count=len(chunks),
            embedding_backend=self._embedder.backend_name,
        )
