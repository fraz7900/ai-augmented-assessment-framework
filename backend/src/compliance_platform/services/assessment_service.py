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

from compliance_platform.ai.embeddings import Embedder
from compliance_platform.models.assessment import (
    Assessment,
    AssessmentStatus,
    AssessmentStatusChange,
    EvidenceLink,
    EvidenceReviewStatus,
    EvidenceSource,
)
from compliance_platform.models.chat import ChatResponse, ChatResult
from compliance_platform.models.framework import FrameworkDefinition
from compliance_platform.models.report import DashboardReport
from compliance_platform.services.chat_service import answer_question
from compliance_platform.services.export_service import build_pdf_report, build_xlsx_report
from compliance_platform.services.mapping_service import find_mapping_candidates
from compliance_platform.services.report_service import build_dashboard
from compliance_platform.services.scoring_service import compute_assessment_domain_scores

_REVIEW_DECISIONS = (
    EvidenceReviewStatus.ACCEPTED,
    EvidenceReviewStatus.EDITED,
    EvidenceReviewStatus.REJECTED,
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


class EvidenceLinkNotFoundError(Exception):
    def __init__(self, evidence_link_id: str) -> None:
        self.evidence_link_id = evidence_link_id
        super().__init__(f"Evidence link '{evidence_link_id}' not found on this assessment.")


class EvidenceAlreadyReviewedError(Exception):
    def __init__(self, evidence_link_id: str, current_status: EvidenceReviewStatus) -> None:
        self.evidence_link_id = evidence_link_id
        self.current_status = current_status
        super().__init__(
            f"Evidence link '{evidence_link_id}' has already been reviewed "
            f"(status: '{current_status.value}'); only pending links can be reviewed."
        )


class InvalidReviewDecisionError(Exception):
    def __init__(self, decision: EvidenceReviewStatus) -> None:
        self.decision = decision
        super().__init__(
            f"'{decision.value}' is not a valid review decision; "
            f"must be one of: {', '.join(d.value for d in _REVIEW_DECISIONS)}."
        )


class MappingEngineUnavailableError(Exception):
    def __init__(self) -> None:
        super().__init__("No embedder configured; cannot propose evidence mappings.")


class ChatEngineUnavailableError(Exception):
    def __init__(self) -> None:
        super().__init__("No embedder configured; cannot answer questions over evidence.")


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
    def get_evidence_link(self, evidence_link_id: str) -> EvidenceLink | None: ...
    def update_evidence_link_review(
        self,
        evidence_link_id: str,
        review_status: EvidenceReviewStatus,
        practice_reference: str | None = None,
        note: str | None = None,
    ) -> EvidenceLink | None: ...


class VectorRepositoryProtocol(Protocol):
    def chunks_for_document(self, document_id: str) -> list[dict]: ...
    def search_within_documents(
        self, query_vector: list[float], document_ids: list[str], limit: int = 5
    ) -> list[dict]: ...


class AssessmentService:
    def __init__(
        self,
        assessment_repository: AssessmentRepositoryProtocol,
        vector_repository: VectorRepositoryProtocol,
        framework_registry: FrameworkRegistryProtocol | None = None,
        embedder: Embedder | None = None,
        mapping_similarity_threshold: float = 0.55,
        mapping_candidates_per_practice: int = 1,
        chat_similarity_threshold: float = 0.35,
        chat_result_limit: int = 5,
    ) -> None:
        self._assessments = assessment_repository
        self._vectors = vector_repository
        self._frameworks = framework_registry
        self._embedder = embedder
        self._mapping_similarity_threshold = mapping_similarity_threshold
        self._mapping_candidates_per_practice = mapping_candidates_per_practice
        self._chat_similarity_threshold = chat_similarity_threshold
        self._chat_result_limit = chat_result_limit

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

    def build_dashboard(self, assessment_id: str) -> DashboardReport:
        """Executive dashboard for this assessment (Sprint 6): situation,
        MECE gap analysis by domain, and a prioritized resolution list —
        see services/report_service.py. Same framework-availability and
        existence checks as compute_scores, since the dashboard is built
        from the same two inputs (framework schema, evidence links).
        """
        assessment = self.get_assessment(assessment_id)
        framework = self._frameworks.get(assessment.framework_name) if self._frameworks else None
        if framework is None:
            raise FrameworkScoringUnavailableError(assessment.framework_name)

        evidence_links = self._assessments.evidence_for_assessment(assessment_id)
        return build_dashboard(assessment, framework, evidence_links)

    def generate_dashboard_pdf(self, assessment_id: str) -> bytes:
        """PDF rendering of the same DashboardReport build_dashboard
        returns — see services/export_service.py and ADR-0013. Reuses
        build_dashboard rather than recomputing anything, and therefore
        raises the same AssessmentNotFoundError /
        FrameworkScoringUnavailableError it does.
        """
        return build_pdf_report(self.build_dashboard(assessment_id))

    def generate_dashboard_xlsx(self, assessment_id: str) -> bytes:
        """XLSX rendering of the same DashboardReport — see
        services/export_service.py and ADR-0013.
        """
        return build_xlsx_report(self.build_dashboard(assessment_id))

    def answer_question(self, assessment_id: str, question: str) -> ChatResponse:
        """Retrieval-only Q&A over this assessment's reviewed evidence
        (Sprint 8) — see services/chat_service.py and ADR-0014. No LLM
        generates the answer; the ranked, cited evidence chunks
        themselves are the answer, so there is nothing to hallucinate
        and no citation-verification step is needed. An empty result
        list (no reviewed evidence, or nothing above the similarity
        threshold) is a valid answer, not an error — same "empty is not
        an error" precedent as propose_mappings.
        """
        self.get_assessment(assessment_id)  # raises AssessmentNotFoundError
        if self._embedder is None:
            raise ChatEngineUnavailableError()

        evidence_links = self._assessments.evidence_for_assessment(assessment_id)
        hits = answer_question(
            question=question,
            evidence_links=evidence_links,
            embedder=self._embedder,
            vector_repository=self._vectors,
            similarity_threshold=self._chat_similarity_threshold,
            limit=self._chat_result_limit,
        )
        return ChatResponse(
            question=question,
            results=[
                ChatResult(
                    practice_reference=hit.practice_reference,
                    document_id=hit.document_id,
                    chunk_id=hit.chunk_id,
                    similarity=hit.similarity,
                    chunk_text=hit.chunk_text,
                )
                for hit in hits
            ],
        )

    def review_evidence(
        self,
        assessment_id: str,
        evidence_link_id: str,
        decision: EvidenceReviewStatus,
        corrected_practice_reference: str | None = None,
        note: str | None = None,
    ) -> EvidenceLink:
        """Applies a human accept/edit/reject decision to a pending
        evidence link — the other half of the human-in-the-loop
        invariant propose_mappings' AI-proposed links exist to satisfy
        (assessment-generation skill). Only PENDING links can be
        reviewed; reviewing is itself blocked on a finalized assessment,
        for the same audit-immutability reason link_evidence already is.
        """
        if decision not in _REVIEW_DECISIONS:
            raise InvalidReviewDecisionError(decision)

        assessment = self.get_assessment(assessment_id)
        if assessment.status == AssessmentStatus.FINALIZED:
            raise AssessmentFinalizedError(assessment_id)

        link = self._assessments.get_evidence_link(evidence_link_id)
        if link is None or link.assessment_id != assessment_id:
            raise EvidenceLinkNotFoundError(evidence_link_id)
        if link.review_status != EvidenceReviewStatus.PENDING:
            raise EvidenceAlreadyReviewedError(evidence_link_id, link.review_status)

        new_practice_reference: str | None = None
        if decision == EvidenceReviewStatus.EDITED:
            if not corrected_practice_reference:
                raise ValueError(
                    "corrected_practice_reference is required when decision is 'edited'."
                )
            if self._frameworks is not None:
                framework = self._frameworks.get(assessment.framework_name)
                if (
                    framework is not None
                    and corrected_practice_reference not in framework.all_practice_ids()
                ):
                    raise InvalidPracticeReferenceError(
                        corrected_practice_reference, assessment.framework_name
                    )
            new_practice_reference = corrected_practice_reference

        updated = self._assessments.update_evidence_link_review(
            evidence_link_id,
            review_status=decision,
            practice_reference=new_practice_reference,
            note=note,
        )
        if updated is None:  # pragma: no cover - existence already checked above
            raise EvidenceLinkNotFoundError(evidence_link_id)
        return updated

    def propose_mappings(self, assessment_id: str) -> list[EvidenceLink]:
        """Runs the retrieval-based mapping engine
        (services/mapping_service.py) for this assessment and persists
        any resulting proposals as AI-proposed, pending-review
        EvidenceLink rows. Returns the newly created links — empty if
        nothing met the confidence threshold, or if the assessment has
        no associated documents yet (from any prior evidence link, of
        any non-rejected status); neither case is an error.
        """
        assessment = self.get_assessment(assessment_id)
        if assessment.status == AssessmentStatus.FINALIZED:
            raise AssessmentFinalizedError(assessment_id)
        if self._embedder is None:
            raise MappingEngineUnavailableError()

        framework = self._frameworks.get(assessment.framework_name) if self._frameworks else None
        if framework is None:
            raise FrameworkScoringUnavailableError(assessment.framework_name)

        existing_links = self._assessments.evidence_for_assessment(assessment_id)
        document_ids = sorted({link.document_id for link in existing_links})
        already_covered = {
            link.practice_reference
            for link in existing_links
            if link.review_status != EvidenceReviewStatus.REJECTED
        }

        proposals = find_mapping_candidates(
            framework=framework,
            document_ids=document_ids,
            already_covered_practice_ids=already_covered,
            embedder=self._embedder,
            vector_repository=self._vectors,
            similarity_threshold=self._mapping_similarity_threshold,
            candidates_per_practice=self._mapping_candidates_per_practice,
        )

        created: list[EvidenceLink] = []
        for proposal in proposals:
            link = EvidenceLink(
                assessment_id=assessment_id,
                document_id=proposal.document_id,
                chunk_id=proposal.chunk_id,
                practice_reference=proposal.practice_id,
                note=(
                    f"AI-proposed via semantic retrieval (confidence "
                    f"{proposal.confidence:.2f}): \"{proposal.chunk_text[:200]}\""
                ),
                source=EvidenceSource.AI_PROPOSED,
                review_status=EvidenceReviewStatus.PENDING,
                confidence=proposal.confidence,
            )
            created.append(self._assessments.add_evidence_link(link))
        return created
