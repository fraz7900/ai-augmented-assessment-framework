"""Documents belong to assessments, not to the instance (ADR-0062).

The evidence chooser used to list every document ever ingested, so a
reviewer picking evidence for one organisation's assessment was shown
another organisation's policies — and could link them, because nothing
downstream objected. These tests run against the real API and database.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from compliance_platform.api import dependencies
from compliance_platform.core.config import Settings
from compliance_platform.main import app

_CACHED = (
    dependencies.get_cached_settings,
    dependencies.get_cached_vector_repository,
    dependencies.get_cached_assessment_repository,
    dependencies.get_cached_framework_registry,
)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    settings = Settings(
        vector_store_dir=tmp_path / "lancedb",
        assessments_db_path=tmp_path / "assessments.db",
        data_raw_dir=tmp_path / "raw",
    )
    for cached in _CACHED:
        cached.cache_clear()
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)
    with TestClient(app) as test_client:
        yield test_client
    for cached in _CACHED:
        cached.cache_clear()


# Long enough to survive the chunker's minimum-length rule: a shorter
# string is rejected as `empty`, which has nothing to do with what these
# tests are checking.
def _ingest(client: TestClient, filename: str, subject: str) -> str:
    body = (
        f"{subject} Multi factor authentication is required for all remote access to critical "
        "systems, and access reviews are performed quarterly by the security team."
    )
    response = client.post("/ingest", files={"file": (filename, body.encode(), "text/plain")})
    assert response.status_code == 200
    return response.json()["document_id"]


def _assessment(client: TestClient, name: str) -> str:
    created = client.post("/assessments", json={"name": name, "framework_name": "C2M2"})
    assert created.status_code == 200
    return created.json()["id"]


def test_a_new_assessment_has_no_documents(client: TestClient) -> None:
    _ingest(client, "someone_elses_policy.txt", "Another organisation's policy.")
    assessment_id = _assessment(client, "Client B")

    attached = client.get(f"/assessments/{assessment_id}/documents").json()

    # The defect in one assertion: another organisation's document was
    # ingested, and this assessment must not offer it.
    assert attached == []


def test_two_assessments_do_not_see_each_others_documents(client: TestClient) -> None:
    a_document = _ingest(client, "client_a_policy.txt", "Client A policy.")
    b_document = _ingest(client, "client_b_policy.txt", "Client B policy.")
    client_a = _assessment(client, "Client A")
    client_b = _assessment(client, "Client B")

    client.post(f"/assessments/{client_a}/documents", json={"document_id": a_document})
    client.post(f"/assessments/{client_b}/documents", json={"document_id": b_document})

    a_filenames = [d["filename"] for d in client.get(f"/assessments/{client_a}/documents").json()]
    b_filenames = [d["filename"] for d in client.get(f"/assessments/{client_b}/documents").json()]

    assert a_filenames == ["client_a_policy.txt"]
    assert b_filenames == ["client_b_policy.txt"]
    # The global listing still sees both. That endpoint is what the
    # attach flow browses; it is the chooser that had to be scoped.
    assert len(client.get("/documents").json()) == 2


def test_one_document_can_serve_several_assessments(client: TestClient) -> None:
    # The reason Document does not simply gain an assessment_id: one
    # policy legitimately backs a C2M2 assessment and a NIST CSF one for
    # the same organisation, and re-uploading it per framework would
    # duplicate the parse, the chunks and the embeddings.
    document_id = _ingest(client, "shared_policy.txt", "Shared policy.")
    c2m2 = _assessment(client, "C2M2 self-assessment")
    csf = _assessment(client, "NIST CSF self-assessment")

    for assessment_id in (c2m2, csf):
        assert (
            client.post(
                f"/assessments/{assessment_id}/documents", json={"document_id": document_id}
            ).status_code
            == 200
        )

    for assessment_id in (c2m2, csf):
        listed = client.get(f"/assessments/{assessment_id}/documents").json()
        assert [d["id"] for d in listed] == [document_id]


def test_linking_evidence_attaches_the_document(client: TestClient) -> None:
    # Citing a document from an assessment says it belongs to it, so
    # attaching is implicit rather than a second step a reviewer can
    # forget.
    document_id = _ingest(client, "policy.txt", "Access control policy.")
    assessment_id = _assessment(client, "Implicit")

    client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1a"},
    )

    listed = client.get(f"/assessments/{assessment_id}/documents").json()
    assert [d["id"] for d in listed] == [document_id]


def test_attaching_twice_is_not_an_error(client: TestClient) -> None:
    # Attach-then-link is the sensible order, and linking attaches too.
    document_id = _ingest(client, "policy.txt", "Access control policy.")
    assessment_id = _assessment(client, "Idempotent")

    first = client.post(
        f"/assessments/{assessment_id}/documents", json={"document_id": document_id}
    )
    second = client.post(
        f"/assessments/{assessment_id}/documents", json={"document_id": document_id}
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(client.get(f"/assessments/{assessment_id}/documents").json()) == 1


def test_a_document_that_was_never_ingested_cannot_be_attached(client: TestClient) -> None:
    assessment_id = _assessment(client, "Strict")

    refused = client.post(
        f"/assessments/{assessment_id}/documents", json={"document_id": "no-such-document"}
    )

    assert refused.status_code == 422


def test_detaching_is_refused_while_evidence_still_cites_it(client: TestClient) -> None:
    # Detaching would leave a citation pointing at a document the
    # assessment no longer claims — the dangling reference the core
    # invariant exists to prevent.
    document_id = _ingest(client, "policy.txt", "Access control policy.")
    assessment_id = _assessment(client, "Cited")
    client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1a"},
    )

    refused = client.delete(f"/assessments/{assessment_id}/documents/{document_id}")

    assert refused.status_code == 409
    assert "still cited" in refused.json()["detail"]
    assert len(client.get(f"/assessments/{assessment_id}/documents").json()) == 1


def test_an_uncited_document_can_be_detached(client: TestClient) -> None:
    document_id = _ingest(client, "wrong_upload.txt", "Uploaded by mistake.")
    assessment_id = _assessment(client, "Tidy")
    client.post(f"/assessments/{assessment_id}/documents", json={"document_id": document_id})

    detached = client.delete(f"/assessments/{assessment_id}/documents/{document_id}")

    assert detached.status_code == 204
    assert client.get(f"/assessments/{assessment_id}/documents").json() == []
    # The document itself survives: it may be attached elsewhere, and
    # ingestion is too expensive to discard as a side effect of tidying.
    assert len(client.get("/documents").json()) == 1


def test_detaching_something_that_was_never_attached_is_a_404(client: TestClient) -> None:
    document_id = _ingest(client, "policy.txt", "Access control policy.")
    assessment_id = _assessment(client, "Empty")

    assert (
        client.delete(f"/assessments/{assessment_id}/documents/{document_id}").status_code == 404
    )


def test_documents_cannot_be_attached_to_a_finalized_assessment(client: TestClient) -> None:
    document_id = _ingest(client, "policy.txt", "Access control policy.")
    assessment_id = _assessment(client, "Frozen")
    client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1a"},
    )
    for status in ("in_review", "finalized"):
        assert (
            client.post(f"/assessments/{assessment_id}/status", json={"status": status}).status_code
            == 200
        )

    second = _ingest(client, "late.txt", "Arrived after finalization.")
    refused = client.post(f"/assessments/{assessment_id}/documents", json={"document_id": second})

    assert refused.status_code == 409
