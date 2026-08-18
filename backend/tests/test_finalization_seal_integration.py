"""The finalization seal against a real database, including tampering
with that database behind the application's back.

R-12's prevention half stops this application from modifying a finalized
assessment (AssessmentRepository._assert_writable). It cannot stop
anything else: assessments.db is a SQLite file. These tests do exactly
what that risk describes — open the file directly and edit a finalized
record — and assert the platform can then say so. Nothing here is
hypothetical; the UPDATE statements below are the attack.
"""

from __future__ import annotations

import io
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import openpyxl
import pytest
from fastapi.testclient import TestClient

from compliance_platform.api import dependencies
from compliance_platform.core.config import Settings
from compliance_platform.main import app

_CACHED_DEPENDENCIES = (
    dependencies.get_cached_settings,
    dependencies.get_cached_vector_repository,
    dependencies.get_cached_assessment_repository,
    dependencies.get_cached_framework_registry,
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "assessments.db"


@pytest.fixture
def client(tmp_path: Path, db_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    test_settings = Settings(
        vector_store_dir=tmp_path / "lancedb",
        assessments_db_path=db_path,
        data_raw_dir=tmp_path / "raw",
    )
    for cached in _CACHED_DEPENDENCIES:
        cached.cache_clear()
    monkeypatch.setattr(dependencies, "get_settings", lambda: test_settings)

    with TestClient(app) as test_client:
        yield test_client

    for cached in _CACHED_DEPENDENCIES:
        cached.cache_clear()


def _finalized_assessment(client: TestClient) -> str:
    """Ingest, link accepted evidence, and finalize — the shortest path
    through ADR-0058's readiness gate to a sealed record."""
    content = b"Multi factor authentication is required for all remote access to critical systems."
    ingest = client.post("/ingest", files={"file": ("policy.txt", content, "text/plain")})
    assert ingest.status_code == 200
    document_id = ingest.json()["document_id"]

    created = client.post(
        "/assessments", json={"name": "Sealed Assessment", "framework_name": "C2M2"}
    )
    assert created.status_code == 200
    assessment_id = created.json()["id"]

    linked = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1a"},
    )
    assert linked.status_code == 200

    for status in ("in_review", "finalized"):
        moved = client.post(f"/assessments/{assessment_id}/status", json={"status": status})
        assert moved.status_code == 200, moved.text
    return assessment_id


def _tamper(db_path: Path, sql: str) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(sql)
        connection.commit()
    finally:
        connection.close()


def test_finalizing_writes_a_seal(client: TestClient) -> None:
    assessment_id = _finalized_assessment(client)

    verified = client.get(f"/assessments/{assessment_id}/verify")

    assert verified.status_code == 200
    body = verified.json()
    assert body["status"] == "verified"
    assert body["sealed_digest"] == body["computed_digest"]
    assert len(body["sealed_digest"]) == 64  # SHA-256, hex
    assert body["seal_version"] == "1"


def test_verification_is_stable_when_nothing_changes(client: TestClient) -> None:
    # Re-reading a record must not be able to make it look altered —
    # the false-positive case that would destroy trust in the feature.
    assessment_id = _finalized_assessment(client)

    first = client.get(f"/assessments/{assessment_id}/verify").json()
    second = client.get(f"/assessments/{assessment_id}/verify").json()

    assert first["computed_digest"] == second["computed_digest"]
    assert second["status"] == "verified"


def test_an_edited_finding_rationale_is_detected(client: TestClient, db_path: Path) -> None:
    assessment_id = _finalized_assessment(client)
    client.get(f"/assessments/{assessment_id}/verify")

    # Rewriting a practice reference straight in the file — the exact
    # thing no amount of application-layer locking can prevent.
    _tamper(
        db_path,
        "UPDATE evidencelink SET practice_reference = 'ACCESS-9z' "
        f"WHERE assessment_id = '{assessment_id}'",
    )

    body = client.get(f"/assessments/{assessment_id}/verify").json()
    assert body["status"] == "altered"
    assert body["sealed_digest"] != body["computed_digest"]
    assert "no longer matches" in body["detail"]


def test_a_deleted_evidence_link_is_detected(client: TestClient, db_path: Path) -> None:
    # Deletion is the tamper a per-row hash on surviving rows would
    # miss: nothing that remains has been touched.
    assessment_id = _finalized_assessment(client)

    _tamper(db_path, f"DELETE FROM evidencelink WHERE assessment_id = '{assessment_id}'")

    assert client.get(f"/assessments/{assessment_id}/verify").json()["status"] == "altered"


def test_a_backdated_history_row_is_detected(client: TestClient, db_path: Path) -> None:
    assessment_id = _finalized_assessment(client)

    _tamper(
        db_path,
        "UPDATE assessmentstatuschange SET note = 'Approved by the audit committee' "
        f"WHERE assessment_id = '{assessment_id}'",
    )

    assert client.get(f"/assessments/{assessment_id}/verify").json()["status"] == "altered"


def test_a_never_finalized_assessment_reports_unsealed_not_verified(
    client: TestClient,
) -> None:
    # "Unverified" and "verified" must not be the same answer, which is
    # why the endpoint does not return a boolean.
    created = client.post("/assessments", json={"name": "Draft", "framework_name": "C2M2"})
    assessment_id = created.json()["id"]

    body = client.get(f"/assessments/{assessment_id}/verify").json()

    assert body["status"] == "unsealed"
    assert body["sealed_digest"] is None


def test_the_seal_leaves_the_database_in_the_exported_report(client: TestClient) -> None:
    """The point of the whole mechanism.

    A digest stored beside the record it protects proves nothing against
    someone who edits the record and recomputes the digest. It becomes
    evidence when a copy exists elsewhere — so every export prints it,
    and the holder of an old report can compare.
    """
    assessment_id = _finalized_assessment(client)
    seal = client.get(f"/assessments/{assessment_id}/verify").json()["sealed_digest"]

    export = client.get(f"/assessments/{assessment_id}/report/xlsx")
    assert export.status_code == 200

    workbook = openpyxl.load_workbook(io.BytesIO(export.content))
    printed = {
        row[1]
        for row in workbook["Situation"].iter_rows(min_col=1, max_col=2, values_only=True)
    }
    assert seal in printed


def test_the_dashboard_carries_the_seal(client: TestClient) -> None:
    assessment_id = _finalized_assessment(client)
    seal = client.get(f"/assessments/{assessment_id}/verify").json()["sealed_digest"]

    dashboard = client.get(f"/assessments/{assessment_id}/dashboard").json()

    assert dashboard["situation"]["finalization_seal"] == seal
