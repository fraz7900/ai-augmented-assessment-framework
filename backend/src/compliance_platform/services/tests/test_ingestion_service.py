"""Unit tests for the ingestion service, using a fake embedder and a fake
vector repository so the test suite exercises orchestration logic without
a real LanceDB store or real embedding computation. See services/README.md
and tests/README.md: services must be unit-testable without a live LLM
or a running HTTP server.
"""

from __future__ import annotations

import pytest

from compliance_platform.core.config import Settings
from compliance_platform.models.schemas import EvidenceChunk, ParseStatus
from compliance_platform.services.ingestion_service import (
    IngestionService,
    UnsupportedDocumentError,
)


class _FakeEmbedder:
    backend_name = "fake"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t))] for t in texts]


class _FakeVectorRepository:
    def __init__(self) -> None:
        self.added: list[tuple[list[EvidenceChunk], list[list[float]]]] = []

    def add_chunks(self, chunks: list[EvidenceChunk], vectors: list[list[float]]) -> None:
        self.added.append((chunks, vectors))


def _make_service(**settings_overrides: object) -> tuple[IngestionService, _FakeVectorRepository]:
    defaults: dict[str, object] = {
        "chunk_target_chars": 1000,
        "chunk_overlap_chars": 50,
        "chunk_min_chars": 5,
    }
    defaults.update(settings_overrides)
    settings = Settings(**defaults)  # type: ignore[arg-type]
    repo = _FakeVectorRepository()
    svc = IngestionService(settings=settings, vector_repository=repo, embedder=_FakeEmbedder())
    return svc, repo


def test_ingest_success_stores_chunks_and_returns_result() -> None:
    svc, repo = _make_service()
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
    svc, _ = _make_service(max_upload_bytes=10)
    with pytest.raises(ValueError):
        svc.ingest("big.txt", b"more than ten bytes of content")


def test_ingest_raises_for_empty_document() -> None:
    svc, repo = _make_service()
    with pytest.raises(UnsupportedDocumentError) as exc_info:
        svc.ingest("empty.txt", b"   ")
    assert exc_info.value.status == ParseStatus.EMPTY
    assert repo.added == []  # nothing should be stored for a rejected document


def test_ingest_raises_for_unsupported_scanned_pdf(scanned_like_pdf_bytes: bytes) -> None:
    svc, repo = _make_service()
    with pytest.raises(UnsupportedDocumentError) as exc_info:
        svc.ingest("scanned.pdf", scanned_like_pdf_bytes)
    assert exc_info.value.status == ParseStatus.UNSUPPORTED_SCANNED
    assert repo.added == []
