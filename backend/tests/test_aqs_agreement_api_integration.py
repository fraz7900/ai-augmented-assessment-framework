"""The agreement endpoint against the real stack (ADR-0070).

The point of exposing this is that it can be pointed at a real
assessment somebody has actually reviewed. So these tests drive it the
way that happens: plant proposals at known confidences, review some of
them through the real review endpoint, and read the measurement back.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from compliance_platform.api import dependencies
from compliance_platform.core.config import Settings
from compliance_platform.main import app
from compliance_platform.models.assessment import (
    EvidenceLink,
    EvidenceReviewStatus,
    EvidenceSource,
)

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


def _assessment(client: TestClient) -> str:
    created = client.post("/assessments", json={"name": "AQS", "framework_name": "C2M2"})
    assert created.status_code == 200
    return created.json()["id"]


def _ingest(client: TestClient) -> str:
    body = (
        b"Access control policy. Multi factor authentication is required for all remote "
        b"access to critical systems, reviewed quarterly by the security team."
    )
    response = client.post("/ingest", files={"file": ("policy.txt", body, "text/plain")})
    assert response.status_code == 200
    return response.json()["document_id"]


def _plant(assessment_id: str, document_id: str, practice: str, confidence: float) -> str:
    repository = dependencies.get_cached_assessment_repository()
    return repository.add_evidence_link(
        EvidenceLink(
            assessment_id=assessment_id,
            document_id=document_id,
            practice_reference=practice,
            source=EvidenceSource.AI_PROPOSED,
            review_status=EvidenceReviewStatus.PENDING,
            confidence=confidence,
        )
    ).id


def test_a_fresh_assessment_reports_undefined_rather_than_zero(client: TestClient) -> None:
    assessment_id = _assessment(client)

    report = client.get(f"/assessments/{assessment_id}/aqs/agreement").json()

    assert report["overall"]["agreement_rate"] is None
    assert report["overall"]["total_ai_proposed"] == 0
    assert len(report["by_confidence_band"]) == 4


def test_real_review_decisions_move_the_measurement(client: TestClient) -> None:
    assessment_id = _assessment(client)
    document_id = _ingest(client)
    high = _plant(assessment_id, document_id, "ACCESS-1a", 0.82)
    low = _plant(assessment_id, document_id, "ASSET-1a", 0.57)
    _plant(assessment_id, document_id, "THREAT-1a", 0.60)

    client.post(
        f"/assessments/{assessment_id}/evidence/{high}/review", json={"decision": "accepted"}
    )
    client.post(
        f"/assessments/{assessment_id}/evidence/{low}/review", json={"decision": "rejected"}
    )

    report = client.get(f"/assessments/{assessment_id}/aqs/agreement").json()

    assert report["overall"]["total_ai_proposed"] == 3
    assert report["overall"]["pending"] == 1
    assert report["overall"]["agreement_rate"] == 0.5
    bands = {band["label"]: band for band in report["by_confidence_band"]}
    # The question this endpoint exists to answer: does a human accept
    # more of what scored higher? Here, on this tiny sample, yes.
    assert bands["Above any measured correct match (> 0.78)"]["agreement"]["agreement_rate"] == 1.0
    assert bands["Borderline (0.55-0.65)"]["agreement"]["agreement_rate"] == 0.0


def test_bulk_reject_decisions_are_measured_like_any_other(client: TestClient) -> None:
    """Bulk reject (ADR-0067) writes real review decisions, so it has to
    show up here — otherwise the measurement would quietly ignore the
    fastest way a reviewer now works."""
    assessment_id = _assessment(client)
    document_id = _ingest(client)
    ids = [
        _plant(assessment_id, document_id, "ACCESS-1a", 0.60),
        _plant(assessment_id, document_id, "ACCESS-1b", 0.62),
    ]

    client.post(
        f"/assessments/{assessment_id}/evidence/bulk-reject",
        json={"evidence_link_ids": ids},
    )

    report = client.get(f"/assessments/{assessment_id}/aqs/agreement").json()
    bands = {band["label"]: band for band in report["by_confidence_band"]}

    assert report["overall"]["agreement_rate"] == 0.0
    assert bands["Borderline (0.55-0.65)"]["agreement"]["rejected"] == 2


def test_the_endpoint_says_what_it_is_not_measuring(client: TestClient) -> None:
    assessment_id = _assessment(client)

    report = client.get(f"/assessments/{assessment_id}/aqs/agreement").json()

    assert "not a quality score for this assessment" in report["interpretation"]


def test_an_unknown_assessment_is_a_404(client: TestClient) -> None:
    assert client.get("/assessments/nope/aqs/agreement").status_code == 404


def test_the_measurement_changes_nothing(client: TestClient) -> None:
    """Read-only, never persisted. An evaluation endpoint that mutated
    the thing it measures would be worse than not having one."""
    assessment_id = _assessment(client)
    document_id = _ingest(client)
    _plant(assessment_id, document_id, "ACCESS-1a", 0.7)
    before = client.get(f"/assessments/{assessment_id}/evidence").json()

    client.get(f"/assessments/{assessment_id}/aqs/agreement")
    client.get(f"/assessments/{assessment_id}/aqs/agreement")

    assert client.get(f"/assessments/{assessment_id}/evidence").json() == before
