"""Every decision in the audit trail names the person who made it
(ADR-0061), against the real API and the real database.

Before this, the trail recorded what changed and when and never who —
so a finalized assessment, the artifact whose whole purpose is being
defensible later, could not name the human behind a single judgment in
it. The identity comes from the proxy that already authenticates every
request (`X-Remote-User`), never from the request body.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from compliance_platform.api import dependencies
from compliance_platform.core.config import Settings
from compliance_platform.core.identity import UNAUTHENTICATED_ACTOR
from compliance_platform.main import app

_CACHED_DEPENDENCIES = (
    dependencies.get_cached_settings,
    dependencies.get_cached_vector_repository,
    dependencies.get_cached_assessment_repository,
    dependencies.get_cached_framework_registry,
)

PRIYA = {"X-Remote-User": "priya"}


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    test_settings = Settings(
        vector_store_dir=tmp_path / "lancedb",
        assessments_db_path=tmp_path / "assessments.db",
        data_raw_dir=tmp_path / "raw",
    )
    for cached in _CACHED_DEPENDENCIES:
        cached.cache_clear()
    monkeypatch.setattr(dependencies, "get_settings", lambda: test_settings)
    with TestClient(app) as test_client:
        yield test_client
    for cached in _CACHED_DEPENDENCIES:
        cached.cache_clear()


def _document(client: TestClient) -> str:
    content = b"Multi factor authentication is required for all remote access to critical systems."
    response = client.post("/ingest", files={"file": ("policy.txt", content, "text/plain")})
    assert response.status_code == 200
    return response.json()["document_id"]


def _assessment(client: TestClient, headers: dict[str, str] | None = None) -> str:
    created = client.post(
        "/assessments", json={"name": "Attributed", "framework_name": "C2M2"}, headers=headers
    )
    assert created.status_code == 200
    return created.json()["id"]


def test_a_linked_evidence_item_names_who_linked_it(client: TestClient) -> None:
    document_id = _document(client)
    assessment_id = _assessment(client)

    linked = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1a"},
        headers=PRIYA,
    )

    assert linked.status_code == 200
    assert linked.json()["created_by"] == "priya"
    assert linked.json()["reviewed_by"] is None


def test_a_review_decision_names_the_reviewer(client: TestClient) -> None:
    document_id = _document(client)
    assessment_id = _assessment(client)
    link = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={
            "document_id": document_id,
            "practice_reference": "ACCESS-1a",
            "source": "ai_proposed",
        },
        headers=PRIYA,
    ).json()

    reviewed = client.post(
        f"/assessments/{assessment_id}/evidence/{link['id']}/review",
        json={"decision": "accepted"},
        headers={"X-Remote-User": "marcus"},
    )

    assert reviewed.status_code == 200
    # Proposed under one identity, accepted under another — the two are
    # recorded separately because they are different claims by different
    # people.
    assert reviewed.json()["created_by"] == "priya"
    assert reviewed.json()["reviewed_by"] == "marcus"


def test_freezing_an_assessment_names_who_froze_it(client: TestClient) -> None:
    document_id = _document(client)
    assessment_id = _assessment(client)
    client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1a"},
        headers=PRIYA,
    )

    for status in ("in_review", "finalized"):
        moved = client.post(
            f"/assessments/{assessment_id}/status", json={"status": status}, headers=PRIYA
        )
        assert moved.status_code == 200, moved.text

    history = client.get(f"/assessments/{assessment_id}/status-history").json()
    finalization = [row for row in history if row["to_status"] == "finalized"]
    assert len(finalization) == 1
    # The most consequential attribution in the product: "this was frozen
    # as authoritative" is a claim somebody made.
    assert finalization[0]["actor"] == "priya"


def test_a_practice_finding_names_its_decider_rather_than_the_word_human(
    client: TestClient,
) -> None:
    assessment_id = _assessment(client)

    finding = client.put(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1a",
        json={"status": "not_satisfied", "rationale": "No MFA on the vendor VPN."},
        headers=PRIYA,
    )

    assert finding.status_code == 200
    assert finding.json()["set_by"] == "priya"


def test_a_client_cannot_attribute_an_evidence_request_to_someone_else(
    client: TestClient,
) -> None:
    # The request body still carries requested_by, and the authenticated
    # identity outranks it. A caller naming whoever it likes is not
    # attribution.
    assessment_id = _assessment(client)

    requested = client.post(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1a/evidence-requests",
        json={"note": "Please send the access review export.", "requested_by": "the_ciso"},
        headers=PRIYA,
    )

    assert requested.status_code == 200
    assert requested.json()["requested_by"] == "priya"


def test_an_unproxied_request_is_recorded_as_unauthenticated(client: TestClient) -> None:
    # Local development, or a deployment misconfigured to bypass the
    # proxy. The record says so rather than inventing a name — and
    # `unauthenticated` is deliberately not a plausible username.
    document_id = _document(client)
    assessment_id = _assessment(client)

    linked = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1a"},
    )

    assert linked.json()["created_by"] == UNAUTHENTICATED_ACTOR


def test_the_seal_covers_who_decided(client: TestClient) -> None:
    # Sealing attribution is the point of bumping the payload to v2: a
    # reviewer who can be silently swapped after finalization is no
    # better recorded than one who was never named.
    document_id = _document(client)
    assessment_id = _assessment(client)
    client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1a"},
        headers=PRIYA,
    )
    for status in ("in_review", "finalized"):
        client.post(
            f"/assessments/{assessment_id}/status", json={"status": status}, headers=PRIYA
        )

    verified = client.get(f"/assessments/{assessment_id}/verify").json()

    assert verified["status"] == "verified"
    assert verified["seal_version"] == "2"
