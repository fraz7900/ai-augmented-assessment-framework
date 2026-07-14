"""End-to-end integration test: ingest a document through the real API,
create an assessment, link evidence to it, and move it through the
status state machine to finalization — exercising the real SQLite
store, LanceDB vector store, and FastAPI app together, not fakes. See
docs/architecture/00-repository-architecture.md's testing strategy.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from compliance_platform.api import dependencies
from compliance_platform.core.config import Settings
from compliance_platform.main import app

_CACHED_DEPENDENCIES = (
    dependencies.get_cached_settings,
    dependencies.get_cached_embedder,
    dependencies.get_cached_vector_repository,
    dependencies.get_cached_assessment_repository,
)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    test_settings = Settings(
        vector_store_dir=tmp_path / "lancedb",
        assessments_db_path=tmp_path / "assessments.db",
    )

    for cached in _CACHED_DEPENDENCIES:
        cached.cache_clear()
    monkeypatch.setattr(dependencies, "get_settings", lambda: test_settings)

    with TestClient(app) as test_client:
        yield test_client

    for cached in _CACHED_DEPENDENCIES:
        cached.cache_clear()


def _ingest_sample_document(client: TestClient) -> str:
    content = b"Multi factor authentication is required for all remote access to critical systems."
    response = client.post("/ingest", files={"file": ("policy.txt", content, "text/plain")})
    assert response.status_code == 200
    return response.json()["document_id"]


def test_full_assessment_lifecycle(client: TestClient) -> None:
    document_id = _ingest_sample_document(client)

    create_response = client.post(
        "/assessments", json={"name": "Q3 C2M2 Self Assessment", "framework_name": "C2M2"}
    )
    assert create_response.status_code == 200
    assessment = create_response.json()
    assessment_id = assessment["id"]
    assert assessment["status"] == "draft"

    evidence_response = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "AM-1a"},
    )
    assert evidence_response.status_code == 200
    assert evidence_response.json()["review_status"] == "accepted"

    to_review = client.post(f"/assessments/{assessment_id}/status", json={"status": "in_review"})
    assert to_review.status_code == 200
    assert to_review.json()["status"] == "in_review"

    finalize = client.post(f"/assessments/{assessment_id}/status", json={"status": "finalized"})
    assert finalize.status_code == 200
    assert finalize.json()["status"] == "finalized"

    history = client.get(f"/assessments/{assessment_id}/status-history")
    assert history.status_code == 200
    statuses = [entry["to_status"] for entry in history.json()]
    assert statuses == ["draft", "in_review", "finalized"]

    evidence_list = client.get(f"/assessments/{assessment_id}/evidence")
    assert evidence_list.status_code == 200
    assert len(evidence_list.json()) == 1

    blocked = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "AM-1b"},
    )
    assert blocked.status_code == 409


def test_evidence_rejected_for_document_never_ingested(client: TestClient) -> None:
    create_response = client.post(
        "/assessments", json={"name": "Test", "framework_name": "NIST CSF 2.0"}
    )
    assessment_id = create_response.json()["id"]
    response = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": "never-ingested", "practice_reference": "GV.OC-01"},
    )
    assert response.status_code == 422


def test_invalid_status_transition_returns_409(client: TestClient) -> None:
    create_response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create_response.json()["id"]
    response = client.post(f"/assessments/{assessment_id}/status", json={"status": "finalized"})
    assert response.status_code == 409


def test_get_unknown_assessment_returns_404(client: TestClient) -> None:
    response = client.get("/assessments/does-not-exist")
    assert response.status_code == 404


def test_list_assessments_returns_created_assessments(client: TestClient) -> None:
    client.post("/assessments", json={"name": "One", "framework_name": "C2M2"})
    client.post("/assessments", json={"name": "Two", "framework_name": "NIST CSF 2.0"})
    response = client.get("/assessments")
    assert response.status_code == 200
    names = {a["name"] for a in response.json()}
    assert {"One", "Two"} <= names
