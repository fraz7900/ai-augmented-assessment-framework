"""Unit tests for the ingestion service, using a fake embedder and a fake
vector repository so the test suite exercises orchestration logic without
a real LanceDB store or real embedding computation. See services/README.md
and tests/README.md: services must be unit-testable without a live LLM
or a running HTTP server.
"""

from __future__ import annotations

import pytest

from compliance_platform.core.config import Settings
from compliance_platform.models.assessment import Document
from compliance_platform.models.schemas import EvidenceChunk, ParseStatus
from compliance_platform.services.ingestion_service import (
    IngestionService,
    UnknownSupersededDocumentError,
    UnsupportedDocumentError,
)


class _FakeEmbedder:
    backend_name = "fake"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t))] for t in texts]


class _FakeVectorRepository:
    def __init__(self, known_document_ids: set[str] | None = None) -> None:
        self.added: list[tuple[list[EvidenceChunk], list[list[float]]]] = []
        self._known_document_ids = known_document_ids or set()

    def add_chunks(self, chunks: list[EvidenceChunk], vectors: list[list[float]]) -> None:
        self.added.append((chunks, vectors))

    def chunks_for_document(self, document_id: str) -> list[dict]:
        return [{"chunk_id": "c1"}] if document_id in self._known_document_ids else []


class _FakeDocumentRepository:
    def __init__(self) -> None:
        self.documents: dict[str, Document] = {}

    def create_document(self, document: Document) -> Document:
        self.documents[document.id] = document
        return document

    def get_document(self, document_id: str) -> Document | None:
        return self.documents.get(document_id)


def _make_service(
    known_document_ids: set[str] | None = None, **settings_overrides: object
) -> tuple[IngestionService, _FakeVectorRepository, _FakeDocumentRepository]:
    defaults: dict[str, object] = {
        "chunk_target_chars": 1000,
        "chunk_overlap_chars": 50,
        "chunk_min_chars": 5,
    }
    defaults.update(settings_overrides)
    settings = Settings(**defaults)  # type: ignore[arg-type]
    vector_repo = _FakeVectorRepository(known_document_ids)
    document_repo = _FakeDocumentRepository()
    svc = IngestionService(
        settings=settings,
        vector_repository=vector_repo,
        embedder=_FakeEmbedder(),
        document_repository=document_repo,
    )
    return svc, vector_repo, document_repo


def test_ingest_success_stores_chunks_and_returns_result() -> None:
    svc, repo, _ = _make_service()
    result = svc.ingest(
        "notes.txt", b"This is a real synthetic evidence document with enough content to chunk."
    )
    assert result.parse_status == ParseStatus.SUCCESS
    assert result.chunk_count > 0
    assert result.embedding_backend == "fake"
    assert len(repo.added) == 1
    stored_chunks, stored_vectors = repo.added[0]
    assert len(stored_chunks) == len(stored_vectors) == result.chunk_count


def test_ingest_rejects_oversized_upload() -> None:
    svc, _, _ = _make_service(max_upload_bytes=10)
    with pytest.raises(ValueError):
        svc.ingest("big.txt", b"more than ten bytes of content")


def test_ingest_raises_for_empty_document() -> None:
    svc, repo, _ = _make_service()
    with pytest.raises(UnsupportedDocumentError) as exc_info:
        svc.ingest("empty.txt", b"   ")
    assert exc_info.value.status == ParseStatus.EMPTY
    assert repo.added == []  # nothing should be stored for a rejected document


def test_ingest_raises_for_unsupported_scanned_pdf(scanned_like_pdf_bytes: bytes) -> None:
    svc, repo, _ = _make_service()
    with pytest.raises(UnsupportedDocumentError) as exc_info:
        svc.ingest("scanned.pdf", scanned_like_pdf_bytes)
    assert exc_info.value.status == ParseStatus.UNSUPPORTED_SCANNED
    assert repo.added == []


def test_ingest_rejects_extracted_text_beyond_the_decompression_bomb_ceiling() -> None:
    # Security hardening (controlled-pilot readiness audit §A.12): a
    # ceiling on EXTRACTED text, applied after parsing, distinct from
    # document_parsers.py's DOCX-specific pre-extraction ZIP check --
    # this one covers every format uniformly, including PDF/TXT/MD.
    svc, repo, _ = _make_service(max_extracted_text_chars=50)
    with pytest.raises(UnsupportedDocumentError) as exc_info:
        svc.ingest("notes.txt", b"This document's extracted text is well over fifty characters long.")
    assert exc_info.value.status == ParseStatus.FAILED
    assert any("decompression-bomb" in w for w in exc_info.value.warnings)
    assert repo.added == []


# --- Document versioning (Sprint 18, ADR-0039) ---


def test_ingest_persists_a_document_record_on_success() -> None:
    svc, _, documents = _make_service()
    result = svc.ingest("notes.txt", b"Real synthetic evidence content for versioning tests.")
    stored = documents.get_document(result.document_id)
    assert stored is not None
    assert stored.filename == "notes.txt"
    assert stored.supersedes_document_id is None


def test_ingest_records_an_explicit_supersedes_declaration() -> None:
    svc, _, documents = _make_service(known_document_ids={"old-doc-id"})
    result = svc.ingest(
        "notes_v2.txt",
        b"Real synthetic evidence content for versioning tests, v2.",
        supersedes_document_id="old-doc-id",
    )
    stored = documents.get_document(result.document_id)
    assert stored is not None
    assert stored.supersedes_document_id == "old-doc-id"


def test_ingest_rejects_a_supersedes_reference_to_an_unknown_document() -> None:
    # supersedes_document_id is explicit and human-declared, but it must
    # still refer to a real, previously-ingested document -- fail closed
    # rather than silently accepting a bogus reference.
    svc, _, documents = _make_service()  # no known_document_ids -- nothing exists yet
    with pytest.raises(UnknownSupersededDocumentError) as exc_info:
        svc.ingest(
            "notes.txt",
            b"Real synthetic evidence content for versioning tests.",
            supersedes_document_id="does-not-exist",
        )
    assert exc_info.value.document_id == "does-not-exist"
    assert documents.documents == {}  # nothing persisted for a rejected ingest


# --- parser_version (Sprint 18, ADR-0042) ---


def test_ingest_reports_parser_version_in_the_result_and_the_persisted_document() -> None:
    svc, _, documents = _make_service()
    result = svc.ingest("notes.txt", b"Real synthetic evidence content for versioning tests.")
    assert result.parser_version.startswith("compliance_platform.document_parsers==")
    stored = documents.get_document(result.document_id)
    assert stored is not None
    assert stored.parser_version == result.parser_version
