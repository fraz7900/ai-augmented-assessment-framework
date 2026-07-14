"""Unit tests for the assessment engine, using fakes for both
repositories so the test suite exercises state-machine and
evidence-linking logic without a real SQLite database or LanceDB store.
See services/README.md and tests/README.md.
"""

from __future__ import annotations

import pytest

from compliance_platform.models.assessment import (
    Assessment,
    AssessmentStatus,
    AssessmentStatusChange,
    EvidenceLink,
    EvidenceReviewStatus,
    EvidenceSource,
)
from compliance_platform.services.assessment_service import (
    AssessmentFinalizedError,
    AssessmentNotFoundError,
    AssessmentService,
    EvidenceDocumentNotIngestedError,
    InvalidStatusTransitionError,
)


class _FakeAssessmentRepository:
    def __init__(self) -> None:
        self._assessments: dict[str, Assessment] = {}
        self._history: dict[str, list[AssessmentStatusChange]] = {}
        self._evidence: dict[str, list[EvidenceLink]] = {}

    def create_assessment(self, name: str, framework_name: str) -> Assessment:
        assessment = Assessment(name=name, framework_name=framework_name)
        self._assessments[assessment.id] = assessment
        self._history[assessment.id] = [
            AssessmentStatusChange(
                assessment_id=assessment.id, from_status=None, to_status=assessment.status
            )
        ]
        self._evidence[assessment.id] = []
        return assessment

    def get_assessment(self, assessment_id: str) -> Assessment | None:
        return self._assessments.get(assessment_id)

    def list_assessments(self) -> list[Assessment]:
        return list(self._assessments.values())

    def update_status(
        self, assessment_id: str, new_status: AssessmentStatus, note: str | None = None
    ) -> Assessment | None:
        assessment = self._assessments.get(assessment_id)
        if assessment is None:
            return None
        previous = assessment.status
        assessment.status = new_status
        self._history[assessment_id].append(
            AssessmentStatusChange(
                assessment_id=assessment_id, from_status=previous, to_status=new_status, note=note
            )
        )
        return assessment

    def status_history(self, assessment_id: str) -> list[AssessmentStatusChange]:
        return list(self._history.get(assessment_id, []))

    def add_evidence_link(self, link: EvidenceLink) -> EvidenceLink:
        self._evidence.setdefault(link.assessment_id, []).append(link)
        return link

    def evidence_for_assessment(self, assessment_id: str) -> list[EvidenceLink]:
        return list(self._evidence.get(assessment_id, []))


class _FakeVectorRepository:
    def __init__(self, known_documents: dict[str, list[str]] | None = None) -> None:
        self._known = known_documents or {}

    def chunks_for_document(self, document_id: str) -> list[dict]:
        if document_id not in self._known:
            return []
        return [{"chunk_id": cid, "document_id": document_id} for cid in self._known[document_id]]


def _make_service(
    known_documents: dict[str, list[str]] | None = None,
) -> tuple[AssessmentService, _FakeAssessmentRepository, _FakeVectorRepository]:
    assessment_repo = _FakeAssessmentRepository()
    vector_repo = _FakeVectorRepository(known_documents)
    return AssessmentService(assessment_repo, vector_repo), assessment_repo, vector_repo


def test_create_assessment_starts_in_draft_with_history_entry() -> None:
    service, _, _ = _make_service()
    assessment = service.create_assessment("Test Assessment", "C2M2")
    assert assessment.status == AssessmentStatus.DRAFT
    history = service.status_history(assessment.id)
    assert len(history) == 1
    assert history[0].from_status is None
    assert history[0].to_status == AssessmentStatus.DRAFT


def test_get_assessment_raises_for_unknown_id() -> None:
    service, _, _ = _make_service()
    with pytest.raises(AssessmentNotFoundError):
        service.get_assessment("does-not-exist")


def test_valid_status_transition_updates_status_and_history() -> None:
    service, _, _ = _make_service()
    assessment = service.create_assessment("A", "NIST CSF 2.0")
    updated = service.transition_status(assessment.id, AssessmentStatus.IN_REVIEW, note="ready")
    assert updated.status == AssessmentStatus.IN_REVIEW
    history = service.status_history(assessment.id)
    assert history[-1].to_status == AssessmentStatus.IN_REVIEW
    assert history[-1].note == "ready"


def test_invalid_status_transition_is_rejected() -> None:
    service, _, _ = _make_service()
    assessment = service.create_assessment("A", "C2M2")
    with pytest.raises(InvalidStatusTransitionError):
        service.transition_status(assessment.id, AssessmentStatus.FINALIZED)


def test_finalized_assessment_cannot_transition_further() -> None:
    service, _, _ = _make_service()
    assessment = service.create_assessment("A", "C2M2")
    service.transition_status(assessment.id, AssessmentStatus.IN_REVIEW)
    service.transition_status(assessment.id, AssessmentStatus.FINALIZED)
    with pytest.raises(InvalidStatusTransitionError):
        service.transition_status(assessment.id, AssessmentStatus.DRAFT)


def test_link_evidence_succeeds_for_ingested_document() -> None:
    service, _, _ = _make_service(known_documents={"doc-1": ["chunk-a", "chunk-b"]})
    assessment = service.create_assessment("A", "C2M2")
    link = service.link_evidence(assessment.id, "doc-1", practice_reference="AM-1a")
    assert link.document_id == "doc-1"
    assert link.review_status == EvidenceReviewStatus.ACCEPTED
    assert service.evidence_for_assessment(assessment.id) == [link]


def test_link_evidence_rejects_document_never_ingested() -> None:
    service, _, _ = _make_service(known_documents={})
    assessment = service.create_assessment("A", "C2M2")
    with pytest.raises(EvidenceDocumentNotIngestedError):
        service.link_evidence(assessment.id, "unknown-doc", practice_reference="AM-1a")


def test_link_evidence_rejects_unknown_chunk_id_for_known_document() -> None:
    service, _, _ = _make_service(known_documents={"doc-1": ["chunk-a"]})
    assessment = service.create_assessment("A", "C2M2")
    with pytest.raises(EvidenceDocumentNotIngestedError):
        service.link_evidence(
            assessment.id, "doc-1", practice_reference="AM-1a", chunk_id="chunk-does-not-exist"
        )


def test_ai_proposed_evidence_defaults_to_pending_review() -> None:
    service, _, _ = _make_service(known_documents={"doc-1": ["chunk-a"]})
    assessment = service.create_assessment("A", "C2M2")
    link = service.link_evidence(
        assessment.id, "doc-1", practice_reference="AM-1a", source=EvidenceSource.AI_PROPOSED
    )
    assert link.review_status == EvidenceReviewStatus.PENDING


def test_link_evidence_rejected_once_assessment_finalized() -> None:
    service, _, _ = _make_service(known_documents={"doc-1": ["chunk-a"]})
    assessment = service.create_assessment("A", "C2M2")
    service.transition_status(assessment.id, AssessmentStatus.IN_REVIEW)
    service.transition_status(assessment.id, AssessmentStatus.FINALIZED)
    with pytest.raises(AssessmentFinalizedError):
        service.link_evidence(assessment.id, "doc-1", practice_reference="AM-1a")
