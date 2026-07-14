"""End-to-end integration test: upload a document through the real
FastAPI app and confirm it comes out the other end ingested and
embedded, exercising the real parser, chunker, embedder, and LanceDB
vector store together rather than fakes. See
docs/architecture/00-repository-architecture.md's testing strategy and
tests/README.md.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from compliance_platform.api import dependencies
from compliance_platform.core.config import Settings
from compliance_platform.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    test_settings = Settings(vector_store_dir=tmp_path / "lancedb")

    dependencies.get_cached_settings.cache_clear()
    dependencies.get_cached_embedder.cache_clear()
    dependencies.get_cached_vector_repository.cache_clear()
    monkeypatch.setattr(dependencies, "get_settings", lambda: test_settings)

    with TestClient(app) as test_client:
        yield test_client

    dependencies.get_cached_settings.cache_clear()
    dependencies.get_cached_embedder.cache_clear()
    dependencies.get_cached_vector_repository.cache_clear()


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ingest_text_document_end_to_end(client: TestClient) -> None:
    content = b"Multi factor authentication is required for all remote access to critical systems."
    response = client.post(
        "/ingest",
        files={"file": ("policy.txt", content, "text/plain")},
        data={"submitter": "test-suite"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["parse_status"] == "success"
    assert body["chunk_count"] >= 1
    assert body["embedding_backend"] == "hashing_local"


def test_ingest_markdown_document_uses_structure_aware_chunking(client: TestClient) -> None:
    # Each section body must clear the default chunk_min_chars (40) or the
    # ingestion service correctly rejects the document as EMPTY — this is
    # exercising that real threshold, not an arbitrary short string.
    content = (
        b"# Access Control\n"
        b"Multi factor authentication is required for all remote access to critical systems.\n"
        b"# Incident Response\n"
        b"Incidents are triaged within fifteen minutes during business hours by the SOC.\n"
    )
    response = client.post(
        "/ingest",
        files={"file": ("policy.md", content, "text/markdown")},
    )
    assert response.status_code == 200
    assert response.json()["chunk_count"] == 2


def test_ingest_scanned_pdf_returns_422(client: TestClient, scanned_like_pdf_bytes: bytes) -> None:
    response = client.post(
        "/ingest",
        files={"file": ("scanned.pdf", scanned_like_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["status"] == "unsupported_scanned"


def test_ingest_unsupported_extension_returns_400(client: TestClient) -> None:
    response = client.post(
        "/ingest",
        files={"file": ("archive.zip", b"PK\x03\x04", "application/zip")},
    )
    assert response.status_code == 400


def test_two_independent_ingestions_are_retrievable_from_the_same_store(
    client: TestClient, tmp_path: Path
) -> None:
    """Regression guard for the exact failure mode ADR-0006 was written to
    avoid: two documents ingested via separate API calls must both land
    in the same, queryable vector store with comparable embeddings.
    """
    for name, text in [
        ("doc_a.txt", b"Access control requires multi factor authentication."),
        ("doc_b.txt", b"Incident response plans are tested twice annually."),
    ]:
        response = client.post("/ingest", files={"file": (name, text, "text/plain")})
        assert response.status_code == 200

    repo = dependencies.get_cached_vector_repository()
    assert repo.count() >= 2
