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
    test_settings = Settings(
        vector_store_dir=tmp_path / "lancedb",
        # Document versioning (ADR-0039) wired IngestionService to
        # AssessmentRepository -- without also isolating
        # assessments_db_path/get_cached_assessment_repository here, an
        # uncleared cache would resolve to Settings' default path and
        # write real Document rows into the live project database this
        # test suite is never supposed to touch. Confirmed as a real,
        # not hypothetical, risk before this fix landed.
        assessments_db_path=tmp_path / "assessments.db",
    )

    # get_cached_embedder is deliberately NOT cleared per-test (Sprint
    # 9, R-13) — see the matching comment in
    # tests/test_assessment_api_integration.py for why reusing it across
    # the whole test session is both safe and measurably faster.
    dependencies.get_cached_settings.cache_clear()
    dependencies.get_cached_vector_repository.cache_clear()
    dependencies.get_cached_assessment_repository.cache_clear()
    monkeypatch.setattr(dependencies, "get_settings", lambda: test_settings)

    with TestClient(app) as test_client:
        yield test_client

    dependencies.get_cached_settings.cache_clear()
    dependencies.get_cached_vector_repository.cache_clear()
    dependencies.get_cached_assessment_repository.cache_clear()


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
    # Default backend as of ADR-0008; hashing_local remains selectable
    # (see ai/tests/test_embeddings.py) but is no longer the default.
    assert body["embedding_backend"] == "semantic_local_onnx"


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


# --- Document versioning (Sprint 18, ADR-0039) ---


def test_ingested_document_is_retrievable_via_documents_endpoint(client: TestClient) -> None:
    response = client.post(
        "/ingest",
        files={"file": ("policy.txt", b"Multi factor authentication is required.", "text/plain")},
        data={"submitter": "test-suite"},
    )
    document_id = response.json()["document_id"]

    detail = client.get(f"/documents/{document_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["filename"] == "policy.txt"
    assert body["submitter"] == "test-suite"
    assert body["supersedes_document_id"] is None
    assert body["superseded_by_document_id"] is None


def test_unknown_document_returns_404(client: TestClient) -> None:
    assert client.get("/documents/does-not-exist").status_code == 404


def test_supersedes_relationship_is_recorded_and_visible_both_directions(
    client: TestClient,
) -> None:
    v1 = client.post(
        "/ingest",
        files={"file": ("policy_v1.txt", b"Passwords must be at least eight characters.", "text/plain")},
    ).json()["document_id"]

    v2 = client.post(
        "/ingest",
        files={"file": ("policy_v2.txt", b"Passwords must be at least twelve characters.", "text/plain")},
        data={"supersedes_document_id": v1},
    ).json()["document_id"]

    v1_detail = client.get(f"/documents/{v1}").json()
    assert v1_detail["superseded_by_document_id"] == v2

    v2_detail = client.get(f"/documents/{v2}").json()
    assert v2_detail["supersedes_document_id"] == v1


def test_ingest_rejects_supersedes_reference_to_unknown_document(client: TestClient) -> None:
    response = client.post(
        "/ingest",
        files={"file": ("policy.txt", b"Some real synthetic policy content here.", "text/plain")},
        data={"supersedes_document_id": "does-not-exist"},
    )
    assert response.status_code == 422
