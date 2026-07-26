"""Assessment engine: state machine, evidence linking, and framework
scoring (Sprint 2, extended Sprint 3).

See services/README.md: business logic lives here, depends on
repositories/ through their interfaces, and is called by api/. No
sqlmodel or lancedb import here directly — that boundary is what keeps
this unit-testable with fakes (see tests/test_assessment_service.py and
the assessment-generation skill).
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Protocol

from compliance_platform.ai.embeddings import Embedder
from compliance_platform.models.assessment import (
    Assessment,
    AssessmentStatus,
    AssessmentStatusChange,
    Document,
    EvidenceLink,
    EvidenceRequest,
    EvidenceReviewStatus,
    EvidenceSource,
    PracticeFinding,
    PracticeFindingChange,
    PracticeFindingStatus,
    SanitizationApproval,
)
from compliance_platform.models.chat import ChatResponse, ChatResult
from compliance_platform.models.framework import FrameworkDefinition
from compliance_platform.models.report import DashboardReport
from compliance_platform.models.sanitization import SanitizationPreview
from compliance_platform.models.schemas import DocumentDetail
from compliance_platform.services.chat_service import answer_question
from compliance_platform.services.export_service import build_pdf_report, build_xlsx_report
from compliance_platform.services.mapping_service import find_mapping_candidates
from compliance_platform.services.report_service import (
    build_dashboard,
    performed_and_excluded_practice_ids,
)
from compliance_platform.services.sanitization_service import sanitize_dashboard_report
from compliance_platform.services.scoring_service import compute_assessment_domain_scores

# Security hardening (controlled-pilot readiness audit §A.12): every log
# call below logs IDs, counts, and statuses only -- never evidence text,
# finding rationale, or sanitization custom_terms, the same fields this
# project's own sanitization design already treats as the sensitive
# surface (models/sanitization.py).
_logger = logging.getLogger(__name__)


def _sanitized_report_hash(report: DashboardReport) -> str:
    """SHA-256 of the sanitized report's own JSON content, the same
    hashing convention services/document_parsers.py uses for uploaded
    document bytes — deterministic (sort_keys) so re-sanitizing
    identical underlying data always reproduces the same hash, and any
    real content change (a new finding, an edited rationale) always
    changes it.
    """
    canonical = json.dumps(report.model_dump(mode="json"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

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


class DocumentNotFoundError(Exception):
    def __init__(self, document_id: str) -> None:
        self.document_id = document_id
        super().__init__(f"Document '{document_id}' not found.")


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


class MissingFindingRationaleError(Exception):
    def __init__(self, practice_reference: str) -> None:
        self.practice_reference = practice_reference
        super().__init__(
            f"A rationale is required when setting a practice finding for "
            f"'{practice_reference}'."
        )


class MissingEvidenceRequestNoteError(Exception):
    def __init__(self, practice_reference: str) -> None:
        self.practice_reference = practice_reference
        super().__init__(
            f"A note describing what's needed is required when requesting more evidence for "
            f"'{practice_reference}'."
        )


class EvidenceRequestNotFoundError(Exception):
    def __init__(self, request_id: str) -> None:
        self.request_id = request_id
        super().__init__(f"Evidence request '{request_id}' not found on this assessment.")


class SanitizationNotApprovedError(Exception):
    """Raised on a sanitized export request when no SanitizationApproval
    exists at all for this assessment yet — see
    services/sanitization_service.py and ADR-0032's "never silently
    publish an AI-sanitized report" rule.
    """

    def __init__(self, assessment_id: str) -> None:
        self.assessment_id = assessment_id
        super().__init__(
            f"Assessment '{assessment_id}' has no approved sanitization yet; "
            "request a preview and approve it before exporting a sanitized report."
        )


class SanitizationApprovalStaleError(Exception):
    """Raised on a sanitized export request when a SanitizationApproval
    exists, but the report content it was computed against has since
    changed (a new/edited finding, an evidence decision, etc.) — the
    freshly recomputed sanitized report no longer hashes to what was
    actually approved.
    """

    def __init__(self, assessment_id: str) -> None:
        self.assessment_id = assessment_id
        super().__init__(
            f"Assessment '{assessment_id}''s report has changed since its sanitization was "
            "last approved; request a new preview and approval before exporting."
        )


class MappingEngineUnavailableError(Exception):
    def __init__(self) -> None:
        super().__init__("No embedder configured; cannot propose evidence mappings.")


class ChatEngineUnavailableError(Exception):
    def __init__(self) -> None:
        super().__init__("No embedder configured; cannot answer questions over evidence.")


class AssessmentRepositoryProtocol(Protocol):
    def create_assessment(
        self, name: str, framework_name: str, framework_version: str | None = None
    ) -> Assessment: ...
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
    def set_practice_finding(
        self,
        assessment_id: str,
        practice_reference: str,
        status: PracticeFindingStatus,
        rationale: str,
        set_by: str = "human",
    ) -> PracticeFinding: ...
    def practice_findings_for_assessment(self, assessment_id: str) -> list[PracticeFinding]: ...
    def practice_finding_history(
        self, assessment_id: str, practice_reference: str
    ) -> list[PracticeFindingChange]: ...
    def create_sanitization_approval(
        self, approval: SanitizationApproval
    ) -> SanitizationApproval: ...
    def latest_sanitization_approval(self, assessment_id: str) -> SanitizationApproval | None: ...
    def get_document(self, document_id: str) -> Document | None: ...
    def document_superseded_by(self, document_id: str) -> Document | None: ...
    def create_evidence_request(self, request: EvidenceRequest) -> EvidenceRequest: ...
    def get_evidence_request(self, request_id: str) -> EvidenceRequest | None: ...
    def evidence_requests_for_assessment(self, assessment_id: str) -> list[EvidenceRequest]: ...
    def resolve_evidence_request(
        self, request_id: str, resolved_by: str
    ) -> EvidenceRequest | None: ...


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
        """Pins FrameworkDefinition.version at creation time (ADR-0031),
        so this assessment's own record of what it was scored against
        survives a later framework_mapping/*.yaml content change.
        framework_version stays None if framework_name isn't a
        recognized/loaded schema at creation time — the same graceful
        fallback InvalidPracticeReferenceError's docstring already
        documents for unrecognized framework names, not an error here.
        """
        framework = self._frameworks.get(framework_name) if self._frameworks else None
        created = self._assessments.create_assessment(
            name=name,
            framework_name=framework_name,
            framework_version=framework.version if framework is not None else None,
        )
        _logger.info(
            "assessment created id=%s framework=%s framework_version=%s",
            created.id,
            framework_name,
            created.framework_version,
        )
        return created

    def get_assessment(self, assessment_id: str) -> Assessment:
        assessment = self._assessments.get_assessment(assessment_id)
        if assessment is None:
            raise AssessmentNotFoundError(assessment_id)
        return assessment

    def list_assessments(self) -> list[Assessment]:
        return self._assessments.list_assessments()

    def get_document_detail(self, document_id: str) -> DocumentDetail:
        """Document versioning (ADR-0039): the durable Document record
        plus the reverse "has this been superseded" lookup, so a
        reviewer can check whether the document an EvidenceLink points
        to is now out of date — the actual pain point Section A #3 of
        the controlled-pilot readiness audit named ("a re-upload gets a
        fresh, unlinked document_id").
        """
        document = self._assessments.get_document(document_id)
        if document is None:
            raise DocumentNotFoundError(document_id)
        superseded_by = self._assessments.document_superseded_by(document_id)
        return DocumentDetail(
            id=document.id,
            filename=document.filename,
            file_type=document.file_type,
            content_hash=document.content_hash,
            submitter=document.submitter,
            uploaded_at=document.uploaded_at,
            supersedes_document_id=document.supersedes_document_id,
            superseded_by_document_id=superseded_by.id if superseded_by is not None else None,
            parser_version=document.parser_version,
        )

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
        _logger.info(
            "assessment status transition id=%s %s -> %s", assessment_id, assessment.status, new_status
        )
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
        created = self._assessments.add_evidence_link(link)
        _logger.info(
            "evidence linked assessment=%s document=%s practice=%s source=%s",
            assessment_id,
            document_id,
            practice_reference,
            source,
        )
        return created

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
        human-in-the-loop invariant. A practice with an explicit
        PracticeFinding (ADR-0030) is scored per that finding instead:
        SATISFIED counts as performed regardless of evidence-link state,
        NOT_SATISFIED/INSUFFICIENT_EVIDENCE/PARTIALLY_SATISFIED never
        count as performed even with accepted evidence, and
        NOT_APPLICABLE removes the practice from scoring entirely
        (neither performed nor a gap).
        """
        assessment = self.get_assessment(assessment_id)
        framework = self._frameworks.get(assessment.framework_name) if self._frameworks else None
        if framework is None:
            raise FrameworkScoringUnavailableError(assessment.framework_name)

        evidence_links = self._assessments.evidence_for_assessment(assessment_id)
        findings = self._assessments.practice_findings_for_assessment(assessment_id)
        performed_practice_ids, excluded_practice_ids = performed_and_excluded_practice_ids(
            evidence_links, findings
        )
        return compute_assessment_domain_scores(
            framework, performed_practice_ids, excluded_practice_ids
        )

    def build_dashboard(self, assessment_id: str) -> DashboardReport:
        """Executive dashboard for this assessment (Sprint 6): situation,
        MECE gap analysis by domain, and a prioritized resolution list —
        see services/report_service.py. Same framework-availability and
        existence checks as compute_scores, since the dashboard is built
        from the same inputs (framework schema, evidence links, and now
        practice findings — ADR-0030).
        """
        assessment = self.get_assessment(assessment_id)
        framework = self._frameworks.get(assessment.framework_name) if self._frameworks else None
        if framework is None:
            raise FrameworkScoringUnavailableError(assessment.framework_name)

        evidence_links = self._assessments.evidence_for_assessment(assessment_id)
        findings = self._assessments.practice_findings_for_assessment(assessment_id)
        return build_dashboard(assessment, framework, evidence_links, findings)

    def generate_dashboard_pdf(self, assessment_id: str, sanitized: bool = False) -> bytes:
        """PDF rendering of the same DashboardReport build_dashboard
        returns — see services/export_service.py and ADR-0013. Reuses
        build_dashboard rather than recomputing anything, and therefore
        raises the same AssessmentNotFoundError /
        FrameworkScoringUnavailableError it does. sanitized=True (ADR-0032)
        renders the approved sanitized report instead, raising
        SanitizationNotApprovedError/SanitizationApprovalStaleError if
        no current approval covers the report's real current content —
        never falls back to exporting unsanitized content silently.
        """
        if not sanitized:
            return build_pdf_report(self.build_dashboard(assessment_id))
        return build_pdf_report(self._approved_sanitized_report(assessment_id))

    def generate_dashboard_xlsx(self, assessment_id: str, sanitized: bool = False) -> bytes:
        """XLSX rendering of the same DashboardReport — see
        services/export_service.py and ADR-0013. See
        generate_dashboard_pdf's docstring for the sanitized=True behavior.
        """
        if not sanitized:
            return build_xlsx_report(self.build_dashboard(assessment_id))
        return build_xlsx_report(self._approved_sanitized_report(assessment_id))

    def preview_sanitization(
        self, assessment_id: str, custom_terms: list[str] | None = None
    ) -> SanitizationPreview:
        """Builds a fresh sanitization preview (ADR-0032) — the
        preview/diff a human reviewer inspects before approving. Never
        persisted by itself; approve_sanitization is the only thing
        that writes a durable record, and only after this exact preview
        content is re-derived server-side, not trusted from the caller.
        """
        dashboard = self.build_dashboard(assessment_id)
        return sanitize_dashboard_report(dashboard, custom_terms)

    def approve_sanitization(
        self, assessment_id: str, custom_terms: list[str] | None, approved_by: str
    ) -> SanitizationApproval:
        """Records a human's explicit approval of one specific sanitized
        report (ADR-0032). Recomputes the sanitization server-side from
        real current data — never trusts a client-supplied "already
        sanitized" payload — and hashes exactly that content, so a
        later sanitized export can prove it matches what was approved.
        """
        self.get_assessment(assessment_id)  # raises AssessmentNotFoundError if missing
        preview = self.preview_sanitization(assessment_id, custom_terms)
        approval = SanitizationApproval(
            assessment_id=assessment_id,
            sanitized_content_hash=_sanitized_report_hash(preview.sanitized_report),
            custom_terms_json=json.dumps(custom_terms or []),
            approved_by=approved_by,
        )
        created = self._assessments.create_sanitization_approval(approval)
        # custom_terms is deliberately never logged -- it is precisely
        # the sensitive organizational identifiers (facility/vendor/
        # employee names) this whole feature exists to keep out of an
        # export; logging it here would defeat that purpose.
        _logger.info(
            "sanitization approved assessment=%s approved_by=%s custom_term_count=%d",
            assessment_id,
            approved_by,
            len(custom_terms or []),
        )
        return created

    def _approved_sanitized_report(self, assessment_id: str) -> DashboardReport:
        approval = self._assessments.latest_sanitization_approval(assessment_id)
        if approval is None:
            raise SanitizationNotApprovedError(assessment_id)
        custom_terms = json.loads(approval.custom_terms_json)
        preview = self.preview_sanitization(assessment_id, custom_terms)
        if _sanitized_report_hash(preview.sanitized_report) != approval.sanitized_content_hash:
            raise SanitizationApprovalStaleError(assessment_id)
        return preview.sanitized_report

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
        _logger.info(
            "evidence reviewed assessment=%s link=%s decision=%s",
            assessment_id,
            evidence_link_id,
            decision,
        )
        return updated

    def set_practice_finding(
        self,
        assessment_id: str,
        practice_reference: str,
        status: PracticeFindingStatus,
        rationale: str,
        set_by: str = "human",
    ) -> PracticeFinding:
        """Records (or updates) a reviewer's explicit compliance
        judgment for one practice — ADR-0030. Distinct from
        review_evidence: that method judges one proposed evidence-to-
        practice LINK; this one judges the PRACTICE itself, independent
        of how many evidence links (if any) it has. Blocked on a
        finalized assessment for the same audit-immutability reason
        link_evidence/review_evidence already are.
        """
        assessment = self.get_assessment(assessment_id)
        if assessment.status == AssessmentStatus.FINALIZED:
            raise AssessmentFinalizedError(assessment_id)
        if not rationale or not rationale.strip():
            raise MissingFindingRationaleError(practice_reference)

        if self._frameworks is not None:
            framework = self._frameworks.get(assessment.framework_name)
            if framework is not None and practice_reference not in framework.all_practice_ids():
                raise InvalidPracticeReferenceError(practice_reference, assessment.framework_name)

        finding = self._assessments.set_practice_finding(
            assessment_id=assessment_id,
            practice_reference=practice_reference,
            status=status,
            rationale=rationale,
            set_by=set_by,
        )
        # rationale is deliberately never logged -- human-authored free
        # text is exactly the class of content this project's own
        # sanitization design treats as potentially sensitive.
        _logger.info(
            "practice finding set assessment=%s practice=%s status=%s set_by=%s",
            assessment_id,
            practice_reference,
            status,
            set_by,
        )
        return finding

    def practice_findings_for_assessment(self, assessment_id: str) -> list[PracticeFinding]:
        self.get_assessment(assessment_id)  # raises AssessmentNotFoundError if missing
        return self._assessments.practice_findings_for_assessment(assessment_id)

    def practice_finding_history(
        self, assessment_id: str, practice_reference: str
    ) -> list[PracticeFindingChange]:
        self.get_assessment(assessment_id)  # raises AssessmentNotFoundError if missing
        return self._assessments.practice_finding_history(assessment_id, practice_reference)

    def request_more_evidence(
        self, assessment_id: str, practice_reference: str, note: str, requested_by: str
    ) -> EvidenceRequest:
        """Records a reviewer's explicit request that someone go find
        and upload more evidence for a practice (Sprint 18, ADR-0043) —
        a workflow action distinct from PracticeFindingStatus (a
        compliance judgment); the two can coexist for the same practice.
        Blocked on a finalized assessment for the same audit-immutability
        reason link_evidence/review_evidence/set_practice_finding
        already are.
        """
        assessment = self.get_assessment(assessment_id)
        if assessment.status == AssessmentStatus.FINALIZED:
            raise AssessmentFinalizedError(assessment_id)
        if not note or not note.strip():
            raise MissingEvidenceRequestNoteError(practice_reference)

        if self._frameworks is not None:
            framework = self._frameworks.get(assessment.framework_name)
            if framework is not None and practice_reference not in framework.all_practice_ids():
                raise InvalidPracticeReferenceError(practice_reference, assessment.framework_name)

        request = self._assessments.create_evidence_request(
            EvidenceRequest(
                assessment_id=assessment_id,
                practice_reference=practice_reference,
                note=note,
                requested_by=requested_by,
            )
        )
        # note is deliberately never logged -- same free-text-is-
        # potentially-sensitive discipline as set_practice_finding's
        # rationale/approve_sanitization's custom_terms above.
        _logger.info(
            "evidence requested assessment=%s practice=%s requested_by=%s",
            assessment_id,
            practice_reference,
            requested_by,
        )
        return request

    def evidence_requests_for_assessment(self, assessment_id: str) -> list[EvidenceRequest]:
        self.get_assessment(assessment_id)  # raises AssessmentNotFoundError if missing
        return self._assessments.evidence_requests_for_assessment(assessment_id)

    def resolve_evidence_request(
        self, assessment_id: str, request_id: str, resolved_by: str
    ) -> EvidenceRequest:
        """Resolution is always explicit, never inferred from a new
        evidence link being added -- linking evidence doesn't guarantee
        it actually addresses what was requested. Blocked on a
        finalized assessment for the same reason creation is: once
        finalized, an unresolved request stays open forever as a real,
        meaningful historical record, not silently closed out.
        """
        assessment = self.get_assessment(assessment_id)
        if assessment.status == AssessmentStatus.FINALIZED:
            raise AssessmentFinalizedError(assessment_id)

        request = self._assessments.get_evidence_request(request_id)
        if request is None or request.assessment_id != assessment_id:
            raise EvidenceRequestNotFoundError(request_id)

        resolved = self._assessments.resolve_evidence_request(request_id, resolved_by=resolved_by)
        if resolved is None:  # pragma: no cover - existence already checked above
            raise EvidenceRequestNotFoundError(request_id)
        _logger.info(
            "evidence request resolved assessment=%s request=%s resolved_by=%s",
            assessment_id,
            request_id,
            resolved_by,
        )
        return resolved

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
        _logger.info(
            "propose-mappings assessment=%s documents=%d proposals_created=%d",
            assessment_id,
            len(document_ids),
            len(created),
        )
        return created
