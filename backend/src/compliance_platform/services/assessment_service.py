"""Assessment engine: state machine, evidence linking, and framework
scoring (Sprint 2, extended Sprint 3).

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
from compliance_platform.models.framework import FrameworkDefinition
from compliance_platform.services.scoring_service import compute_assessment_domain_scores

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


class InvalidPracticeReferenceError(Exception):
    """Raised when practice_reference does not exist in the loaded
    schema for the assessment's framework — the Sprint 3 fulfillment of
    Decision D-10 (practice_reference was free text in Sprint 2,
    deferred to real validation once framework schemas existed).

    Deliberately NOT raised when no schema is loaded for the
    assessment's framework_name at all (e.g. "NIST CSF 2.0" before
    Sprint 4): an unrecognized framework name falls back to the Sprint 2
    free-text behavior rather than blocking evidence linking on
    framework support that doesn't exist yet. See
    services/framework_loader.py's FrameworkRegistry.get().
    """

    def __init__(self, practice_reference: str, framework_name: str) -> None:
        self.practice_reference = practice_reference
        self.framework_name = framework_name
        super().__init__(
            f"'{practice_reference}' is not a known practice in the {framework_name} schema."
        )


class FrameworkRegistryProtocol(Protocol):
    def get(self, name: str) -> FrameworkDefinition | None: ...


class FrameworkScoringUnavailableError(Exception):
    def __init__(self, framework_name: str) -> None:
        self.framework_name = framework_name
        super().__init__(
            f"No structured schema is loaded for framework '{framework_name}'; "
            "cannot compute scores."
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
        framework_registry: FrameworkRegistryProtocol | None = None,
    ) -> None:
        self._assessments = assessment_repository
        self._vectors = vector_repository
        self._frameworks = framework_registry

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

        if self._frameworks is not None:
            framework = self._frameworks.get(assessment.framework_name)
            if framework is not None and practice_reference not in framework.all_practice_ids():
                raise InvalidPracticeReferenceError(practice_reference, assessment.framework_name)

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

    def compute_scores(self, assessment_id: str) -> dict[str, float]:
        """Per-domain scores for this assessment's framework — cumulative
        MIL (0-3, C2M2) or coverage (0.0-1.0, NIST CSF 2.0), depending on
        the framework's declared scoring_model; see
        services/scoring_service.py. Evidence links still pending or
        rejected review do not count as performed — only accepted or
        edited ones do, per the assessment-generation skill's
        human-in-the-loop invariant.
        """
        assessment = self.get_assessment(assessment_id)
        framework = self._frameworks.get(assessment.framework_name) if self._frameworks else None
        if framework is None:
            raise FrameworkScoringUnavailableError(assessment.framework_name)

        performed_practice_ids = {
            link.practice_reference
            for link in self._assessments.evidence_for_assessment(assessment_id)
            if link.review_status in (EvidenceReviewStatus.ACCEPTED, EvidenceReviewStatus.EDITED)
        }
        return compute_assessment_domain_scores(framework, performed_practice_ids)
