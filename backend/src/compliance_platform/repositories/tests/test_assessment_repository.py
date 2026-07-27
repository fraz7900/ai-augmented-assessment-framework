"""Unit tests for AssessmentRepository against a real SQLite database at
tmp_path (ADR-0007) — no dedicated test file existed for this repository
before; it was only exercised indirectly through the assessment_service
unit tests (which use a fake, per services/README.md's boundary) and the
API integration tests. This file exists specifically to cover two pieces
of real, non-trivial SQL logic a fake cannot exercise honestly: the
schema-migration helper (ADR-0030) and PracticeFinding's upsert +
append-only-history behavior.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine

from compliance_platform.models.assessment import (
    Document,
    EvidenceLink,
    EvidenceRequest,
    EvidenceReviewStatus,
    EvidenceSource,
    PracticeFindingStatus,
)
from compliance_platform.repositories.assessment_repository import AssessmentRepository


def _repo(tmp_path: Path) -> AssessmentRepository:
    return AssessmentRepository(tmp_path / "assessments.db")


def test_fresh_database_has_evidencelink_original_practice_reference_column(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    with repo._engine.connect() as conn:  # noqa: SLF001 - direct schema inspection, test-only
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(evidencelink)")}
    assert "original_practice_reference" in columns


def test_fresh_database_has_assessment_framework_version_column(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    with repo._engine.connect() as conn:  # noqa: SLF001
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(assessment)")}
    assert "framework_version" in columns


def test_create_assessment_persists_framework_version(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    created = repo.create_assessment(
        name="Test", framework_name="PCI DSS", framework_version="4.0.1"
    )
    assert created.framework_version == "4.0.1"

    reloaded = repo.get_assessment(created.id)
    assert reloaded is not None
    assert reloaded.framework_version == "4.0.1"


def test_migration_adds_missing_column_to_a_pre_adr_0030_database_without_data_loss(
    tmp_path: Path,
) -> None:
    """Simulates a database created before ADR-0030 (no
    original_practice_reference column) that already has a real row in
    it, then constructs AssessmentRepository against that same file and
    confirms the column is added and the pre-existing row survives
    untouched — the exact scenario _add_missing_columns exists for.
    """
    db_path = tmp_path / "legacy.db"
    legacy_engine = create_engine(f"sqlite:///{db_path}")
    with legacy_engine.connect() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE evidencelink ("
            "id TEXT PRIMARY KEY, assessment_id TEXT, document_id TEXT, "
            "chunk_id TEXT, practice_reference TEXT, note TEXT, source TEXT, "
            "review_status TEXT, confidence REAL, created_at TEXT, reviewed_at TEXT)"
        )
        conn.exec_driver_sql(
            "INSERT INTO evidencelink (id, assessment_id, document_id, practice_reference, "
            "source, review_status, created_at) VALUES "
            "('link-1', 'assess-1', 'doc-1', 'AM-1a', 'manual', 'accepted', '2026-01-01')"
        )
        conn.commit()
    legacy_engine.dispose()

    repo = AssessmentRepository(db_path)  # runs the migration on an existing file

    with repo._engine.connect() as conn:  # noqa: SLF001
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(evidencelink)")}
        assert "original_practice_reference" in columns
        row = conn.exec_driver_sql(
            "SELECT id, practice_reference, original_practice_reference FROM evidencelink"
        ).fetchone()
        assert row == ("link-1", "AM-1a", None)


def test_update_evidence_link_review_preserves_original_practice_reference_only_on_first_edit(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    assessment = repo.create_assessment(name="Test", framework_name="C2M2")
    link = repo.add_evidence_link(
        EvidenceLink(
            assessment_id=assessment.id,
            document_id="doc-1",
            practice_reference="AM-1a",
            source=EvidenceSource.AI_PROPOSED,
            review_status=EvidenceReviewStatus.PENDING,
        )
    )
    assert link.original_practice_reference is None

    first_edit = repo.update_evidence_link_review(
        link.id, review_status=EvidenceReviewStatus.EDITED, practice_reference="AM-1b"
    )
    assert first_edit is not None
    assert first_edit.practice_reference == "AM-1b"
    assert first_edit.original_practice_reference == "AM-1a"  # the AI's real original proposal

    # A hypothetical second correction (re-opening review isn't allowed by
    # the service layer today, but the repository method itself should
    # still never clobber the true original if ever called again).
    second_edit = repo.update_evidence_link_review(
        link.id, review_status=EvidenceReviewStatus.EDITED, practice_reference="AM-1c"
    )
    assert second_edit is not None
    assert second_edit.practice_reference == "AM-1c"
    assert second_edit.original_practice_reference == "AM-1a"  # unchanged, not overwritten


def test_set_practice_finding_creates_row_and_history_entry(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assessment = repo.create_assessment(name="Test", framework_name="C2M2")

    finding = repo.set_practice_finding(
        assessment.id, "AM-1a", PracticeFindingStatus.NOT_SATISFIED, "No asset inventory exists."
    )
    assert finding.status == PracticeFindingStatus.NOT_SATISFIED
    assert finding.rationale == "No asset inventory exists."

    findings = repo.practice_findings_for_assessment(assessment.id)
    assert len(findings) == 1
    assert findings[0].id == finding.id

    history = repo.practice_finding_history(assessment.id, "AM-1a")
    assert len(history) == 1
    assert history[0].from_status is None
    assert history[0].to_status == PracticeFindingStatus.NOT_SATISFIED


def test_set_practice_finding_upserts_and_records_transition_in_history(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assessment = repo.create_assessment(name="Test", framework_name="C2M2")

    repo.set_practice_finding(
        assessment.id, "AM-1a", PracticeFindingStatus.INSUFFICIENT_EVIDENCE, "Nothing uploaded yet."
    )
    updated = repo.set_practice_finding(
        assessment.id, "AM-1a", PracticeFindingStatus.SATISFIED, "Inventory doc now reviewed."
    )

    # Upsert, not a second row.
    findings = repo.practice_findings_for_assessment(assessment.id)
    assert len(findings) == 1
    assert findings[0].id == updated.id
    assert findings[0].status == PracticeFindingStatus.SATISFIED

    # But the full transition is preserved in history.
    history = repo.practice_finding_history(assessment.id, "AM-1a")
    assert [c.to_status for c in history] == [
        PracticeFindingStatus.INSUFFICIENT_EVIDENCE,
        PracticeFindingStatus.SATISFIED,
    ]
    assert history[1].from_status == PracticeFindingStatus.INSUFFICIENT_EVIDENCE


def test_practice_findings_for_assessment_isolated_per_assessment(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    a1 = repo.create_assessment(name="A1", framework_name="C2M2")
    a2 = repo.create_assessment(name="A2", framework_name="C2M2")

    repo.set_practice_finding(a1.id, "AM-1a", PracticeFindingStatus.SATISFIED, "ok")
    repo.set_practice_finding(a2.id, "AM-1a", PracticeFindingStatus.NOT_APPLICABLE, "n/a for a2")

    assert len(repo.practice_findings_for_assessment(a1.id)) == 1
    assert len(repo.practice_findings_for_assessment(a2.id)) == 1
    finding_a1 = repo.practice_findings_for_assessment(a1.id)[0]
    finding_a2 = repo.practice_findings_for_assessment(a2.id)[0]
    assert finding_a1.status == PracticeFindingStatus.SATISFIED
    assert finding_a2.status == PracticeFindingStatus.NOT_APPLICABLE


# --- Document versioning (Sprint 18, ADR-0039) ---


def _document(doc_id: str, supersedes: str | None = None) -> Document:
    return Document(
        id=doc_id,
        filename=f"{doc_id}.txt",
        file_type="txt",
        content_hash="deadbeef",
        supersedes_document_id=supersedes,
    )


def test_create_and_get_document_round_trip(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.create_document(_document("doc-1"))
    fetched = repo.get_document("doc-1")
    assert fetched is not None
    assert fetched.filename == "doc-1.txt"
    assert fetched.supersedes_document_id is None


def test_get_document_returns_none_for_unknown_id(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert repo.get_document("does-not-exist") is None


def test_document_superseded_by_reverse_lookup(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.create_document(_document("doc-v1"))
    repo.create_document(_document("doc-v2", supersedes="doc-v1"))

    superseded_by = repo.document_superseded_by("doc-v1")
    assert superseded_by is not None
    assert superseded_by.id == "doc-v2"

    # v2 itself has not (yet) been superseded by anything.
    assert repo.document_superseded_by("doc-v2") is None


# --- Evidence requests (Sprint 18, ADR-0043) ---


def test_create_and_get_evidence_request_round_trip(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assessment = repo.create_assessment(name="A1", framework_name="C2M2")
    created = repo.create_evidence_request(
        EvidenceRequest(
            assessment_id=assessment.id,
            practice_reference="AM-1a",
            note="Please provide the current asset inventory spreadsheet.",
            requested_by="priya",
        )
    )
    fetched = repo.get_evidence_request(created.id)
    assert fetched is not None
    assert fetched.practice_reference == "AM-1a"
    assert fetched.resolved_at is None
    assert fetched.resolved_by is None


def test_get_evidence_request_returns_none_for_unknown_id(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert repo.get_evidence_request("does-not-exist") is None


def test_evidence_requests_for_assessment_isolated_per_assessment(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    a1 = repo.create_assessment(name="A1", framework_name="C2M2")
    a2 = repo.create_assessment(name="A2", framework_name="C2M2")
    repo.create_evidence_request(
        EvidenceRequest(
            assessment_id=a1.id, practice_reference="AM-1a", note="need X", requested_by="priya"
        )
    )
    repo.create_evidence_request(
        EvidenceRequest(
            assessment_id=a2.id, practice_reference="AM-1a", note="need Y", requested_by="priya"
        )
    )
    assert len(repo.evidence_requests_for_assessment(a1.id)) == 1
    assert len(repo.evidence_requests_for_assessment(a2.id)) == 1
    assert repo.evidence_requests_for_assessment(a1.id)[0].note == "need X"


def test_multiple_open_requests_can_exist_for_the_same_practice(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assessment = repo.create_assessment(name="A1", framework_name="C2M2")
    repo.create_evidence_request(
        EvidenceRequest(
            assessment_id=assessment.id,
            practice_reference="AM-1a",
            note="first request",
            requested_by="priya",
        )
    )
    repo.create_evidence_request(
        EvidenceRequest(
            assessment_id=assessment.id,
            practice_reference="AM-1a",
            note="second request",
            requested_by="marcus",
        )
    )
    requests = repo.evidence_requests_for_assessment(assessment.id)
    assert len(requests) == 2
    assert {r.note for r in requests} == {"first request", "second request"}


def test_resolve_evidence_request_sets_resolved_fields(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assessment = repo.create_assessment(name="A1", framework_name="C2M2")
    created = repo.create_evidence_request(
        EvidenceRequest(
            assessment_id=assessment.id,
            practice_reference="AM-1a",
            note="need X",
            requested_by="priya",
        )
    )
    resolved = repo.resolve_evidence_request(created.id, resolved_by="sam")
    assert resolved is not None
    assert resolved.resolved_by == "sam"
    assert resolved.resolved_at is not None

    refetched = repo.get_evidence_request(created.id)
    assert refetched is not None
    assert refetched.resolved_by == "sam"


def test_resolve_evidence_request_returns_none_for_unknown_id(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert repo.resolve_evidence_request("does-not-exist", resolved_by="sam") is None
