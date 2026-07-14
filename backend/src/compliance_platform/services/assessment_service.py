"""Assessment engine: state machine + evidence linking (Sprint 2).

See services/README.md: business logic lives here, depends on
repositories/ through their interfaces, and is called by api/. No
sqlmodel or lancedb import here directly — that boundary is what keeps
this unit-testable with fakes (see tests/test_assessment_service.py and
the assessment-generation skill).
"""

from __future__ import annotations

from typing import Protocol

from compliance_platform.models.assessment import (
    Assessment,
    AssessmentStatus,
    AssessmentStatusChange,
    EvidenceLink,
    EvidenceReviewStatus,
    EvidenceSource,
)

_ALLOWED_TRANSITIONS: dict[AssessmentStatus, set[AssessmentStatus]] = {
    AssessmentStatus.DRAFT: {AssessmentStatus.IN_REVIEW},
    AssessmentStatus.IN_REVIEW: {AssessmentStatus.DRAFT, AssessmentStatus.FINALIZED},
    AssessmentStatus.FINALIZED: set(),
}


class AssessmentNotFoundError(Exception):
    def __init__(self, assessment_id: str) -> None:
        self.assessment_id = assessment_id
        super().__init__(f"Assessment '{assessment_id}' not found.")


class InvalidStatusTransitionError(Exception):
    def __init__(self, current: AssessmentStatus, requested: AssessmentStatus) -> None:
        self.current = current
        self.requested = requested
        super().__init__(
            f"Cannot transition assessment from '{current.value}' to '{requested.value}'."
        )


class AssessmentFinalizedError(Exception):
    def __init__(self, assessment_id: str) -> None:
        self.assessment_id = assessment_id
        super().__init__(
            f"Assessment '{assessment_id}' is finalized; evidence links can no longer be added."
        )


class EvidenceDocumentNotIngestedError(Exception):
    """Raised when evidence is linked to a document_id (or chunk_id) that
    does not exist in the vector store — the structural enforcement of
    the assessment-generation skill's core invariant: no score exists
    without a linked evidence trail, because you cannot link evidence
    that was never actually ingested.
    """

    def __init__(self, document_id: str) -> None:
        self.document_id = document_id
        super().__init__(
            f"Document '{document_id}' has not been ingested "
            "(no matching chunks found in the vector store)."
        )


class AssessmentRepositoryProtocol(Protocol):
    def create_assessment(self, name: str, framework_name: str) -> Assessment: ...
    def get_assessment(self, assessment_id: str) -> Assessment | None: ...
    def list_assessments(self) -> list[Assessment]: ...
    def update_status(
        self, assessment_id: str, new_status: AssessmentStatus, note: str | None = None
    ) -> Assessment | None: ...
    def status_history(self, assessment_id: str) -> list[AssessmentStatusChange]: ...
    def add_evidence_link(self, link: EvidenceLink) -> EvidenceLink: ...
    def evidence_for_assessment(self, assessment_id: str) -> list[EvidenceLink]: ...


class VectorRepositoryProtocol(Protocol):
    def chunks_for_document(self, document_id: str) -> list[dict]: ...


class AssessmentService:
    def __init__(
        self,
        assessment_repository: AssessmentRepositoryProtocol,
        vector_repository: VectorRepositoryProtocol,
    ) -> None:
        self._assessments = assessment_repository
        self._vectors = vector_repository

    def create_assessment(self, name: str, framework_name: str) -> Assessment:
        return self._assessments.create_assessment(name=name, framework_name=framework_name)

    def get_assessment(self, assessment_id: str) -> Assessment:
        assessment = self._assessments.get_assessment(assessment_id)
        if assessment is None:
            raise AssessmentNotFoundError(assessment_id)
        return assessment

    def list_assessments(self) -> list[Assessment]:
        return self._assessments.list_assessments()

    def transition_status(
        self, assessment_id: str, new_status: AssessmentStatus, note: str | None = None
    ) -> Assessment:
        assessment = self.get_assessment(assessment_id)
        allowed = _ALLOWED_TRANSITIONS[assessment.status]
        if new_status not in allowed:
            raise InvalidStatusTransitionError(assessment.status, new_status)
        updated = self._assessments.update_status(assessment_id, new_status, note=note)
        if updated is None:  # pragma: no cover - existence already checked above
            raise AssessmentNotFoundError(assessment_id)
        return updated

    def status_history(self, assessment_id: str) -> list[AssessmentStatusChange]:
        self.get_assessment(assessment_id)  # raises AssessmentNotFoundError if missing
        return self._assessments.status_history(assessment_id)

    def link_evidence(
        self,
        assessment_id: str,
        document_id: str,
        practice_reference: str,
        chunk_id: str | None = None,
        note: str | None = None,
        source: EvidenceSource = EvidenceSource.MANUAL,
    ) -> EvidenceLink:
        assessment = self.get_assessment(assessment_id)
        if assessment.status == AssessmentStatus.FINALIZED:
            raise AssessmentFinalizedError(assessment_id)

        existing_chunks = self._vectors.chunks_for_document(document_id)
        if not existing_chunks:
            raise EvidenceDocumentNotIngestedError(document_id)
        if chunk_id is not None:
            known_chunk_ids = {row["chunk_id"] for row in existing_chunks}
            if chunk_id not in known_chunk_ids:
                raise EvidenceDocumentNotIngestedError(document_id)

        review_status = (
            EvidenceReviewStatus.PENDING
            if source == EvidenceSource.AI_PROPOSED
            else EvidenceReviewStatus.ACCEPTED
        )
        link = EvidenceLink(
            assessment_id=assessment_id,
            document_id=document_id,
            chunk_id=chunk_id,
            practice_reference=practice_reference,
            note=note,
            source=source,
            review_status=review_status,
        )
        return self._assessments.add_evidence_link(link)

    def evidence_for_assessment(self, assessment_id: str) -> list[EvidenceLink]:
        self.get_assessment(assessment_id)  # raises AssessmentNotFoundError if missing
        return self._assessments.evidence_for_assessment(assessment_id)
