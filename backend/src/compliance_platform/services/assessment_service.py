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
import hmac
import json
import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, Protocol

from compliance_platform.ai.embeddings import Embedder
from compliance_platform.core.errors import (
    AssessmentFinalizedError,
    CrossOrganizationAttachmentError,
    # Re-exported: this module was its home until the repository needed
    # to raise it too (ADR-0067), and core/errors.py's own convention is
    # that a move must not force unrelated call sites to change.
    EvidenceLinkNotFoundError,
    OrganizationNotFoundError,
)
from compliance_platform.core.identity import UNAUTHENTICATED_ACTOR
from compliance_platform.models.aqs import AssessmentAgreementReport
from compliance_platform.models.assessment import (
    Assessment,
    AssessmentDocument,
    AssessmentStatus,
    AssessmentStatusChange,
    Document,
    EvidenceLink,
    EvidenceRequest,
    EvidenceReviewStatus,
    EvidenceSource,
    Organization,
    PracticeFinding,
    PracticeFindingChange,
    PracticeFindingStatus,
    SanitizationApproval,
)
from compliance_platform.models.chat import ChatResponse, ChatResult
from compliance_platform.models.framework import FrameworkDefinition
from compliance_platform.models.report import (
    DashboardReport,
    EvidenceDomainCount,
    EvidenceQueueSummary,
)
from compliance_platform.models.sanitization import SanitizationPreview
from compliance_platform.models.schemas import (
    BulkReviewResult,
    BulkReviewSkip,
    DocumentDetail,
    DocumentSummary,
    FinalizationBlocker,
    FinalizationBlockerCategory,
    FinalizationReadiness,
    SealVerification,
    SealVerificationStatus,
    resolve_text_provenance,
)
from compliance_platform.services import audit_seal
from compliance_platform.services.aqs_service import build_agreement_report
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

# Cap on ids echoed back per finalization blocker (ADR-0058). The count
# is always the true total; this only bounds the response body so an
# assessment with hundreds of pending proposals cannot return a payload
# the size of its own evidence table.
_MAX_BLOCKER_IDS = 50

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


class AssessmentNotReadyForFinalizationError(Exception):
    """Raised when finalization is attempted with outstanding review work
    (ADR-0058).

    Carries the structured blockers rather than only a message, so the
    409 response body is the same machine-readable shape the readiness
    endpoint returns and a caller never has to parse prose to find out
    what to fix.
    """

    def __init__(self, assessment_id: str, blockers: list[FinalizationBlocker]) -> None:
        self.assessment_id = assessment_id
        self.blockers = blockers
        categories = ", ".join(sorted({b.category.value for b in blockers}))
        super().__init__(
            f"Assessment '{assessment_id}' is not ready to finalize; outstanding: {categories}."
        )


class OrganizationNameRequiredError(Exception):
    """An organisation was created or renamed with a blank name (ADR-0063).

    A rule about what an organisation may be called, so it lives here
    rather than in core/errors.py -- unlike the boundary itself, no lower
    layer needs to raise it.
    """

    def __init__(self) -> None:
        super().__init__("An organization needs a name.")


class OrganizationNameTakenError(Exception):
    """Two organisations cannot share a name (ADR-0063), because a
    chooser whose whole job is telling clients apart cannot do it with
    two identical labels and two opaque ids."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"An organization named '{name}' already exists.")


class DocumentStillCitedError(Exception):
    """Detaching a document that evidence links still point at (ADR-0062)."""

    def __init__(self, document_id: str, citation_count: int) -> None:
        self.document_id = document_id
        self.citation_count = citation_count
        super().__init__(
            f"Document '{document_id}' is still cited by {citation_count} evidence link(s). "
            "Reject or remove them before detaching it."
        )


class DocumentNotAttachedError(Exception):
    def __init__(self, assessment_id: str, document_id: str) -> None:
        self.assessment_id = assessment_id
        self.document_id = document_id
        super().__init__(
            f"Document '{document_id}' is not attached to assessment '{assessment_id}'."
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
    def get(self, name: str, version: str | None = None) -> FrameworkDefinition | None: ...
    def available_versions(self, name: str) -> list[str]: ...


class FrameworkScoringUnavailableError(Exception):
    def __init__(self, framework_name: str) -> None:
        self.framework_name = framework_name
        super().__init__(
            f"No structured schema is loaded for framework '{framework_name}'; "
            "cannot compute scores."
        )


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


class UnknownFrameworkVersionError(Exception):
    """Raised only when framework_name IS recognized (the registry has
    at least one known version for it) but an explicitly REQUESTED
    version isn't among them (Sprint 18, ADR-0053) — deliberately
    distinct from the pre-existing, unchanged tolerance for a totally
    unrecognized framework_name (silently allowed, framework_version
    stays None — see create_assessment's own docstring). A caller who
    explicitly asked for a specific version made a real, checkable
    mistake worth surfacing, not silently swallowed into "whatever's
    latest" or a null pin.
    """

    def __init__(
        self, framework_name: str, requested_version: str, known_versions: list[str]
    ) -> None:
        self.framework_name = framework_name
        self.requested_version = requested_version
        self.known_versions = known_versions
        super().__init__(
            f"'{framework_name}' has no version '{requested_version}' loaded; "
            f"known versions: {', '.join(known_versions)}."
        )


class AssessmentRepositoryProtocol(Protocol):
    def create_assessment(
        self,
        name: str,
        framework_name: str,
        framework_version: str | None = None,
        organization_id: str | None = None,
    ) -> Assessment: ...
    def get_assessment(self, assessment_id: str) -> Assessment | None: ...
    def list_assessments(self, organization_id: str) -> list[Assessment]: ...
    def resolve_organization_id(self, organization_id: str | None = None) -> str: ...
    def create_organization(self, name: str) -> Organization: ...
    def get_organization(self, organization_id: str) -> Organization | None: ...
    def organization_by_name(self, name: str) -> Organization | None: ...
    def list_organizations(self) -> list[Organization]: ...
    def rename_organization(self, organization_id: str, name: str) -> Organization | None: ...
    def update_status(
        self,
        assessment_id: str,
        new_status: AssessmentStatus,
        note: str | None = None,
        actor: str | None = None,
    ) -> Assessment | None: ...
    def status_history(self, assessment_id: str) -> list[AssessmentStatusChange]: ...
    def add_evidence_link(self, link: EvidenceLink) -> EvidenceLink: ...
    def evidence_for_assessment(self, assessment_id: str) -> list[EvidenceLink]: ...
    def get_evidence_link(self, evidence_link_id: str) -> EvidenceLink | None: ...
    def bulk_reject_evidence_links(
        self,
        assessment_id: str,
        evidence_link_ids: list[str],
        reviewed_by: str | None = None,
        note: str | None = None,
    ) -> tuple[int, list[tuple[str, EvidenceReviewStatus]]]: ...
    def update_evidence_link_review(
        self,
        evidence_link_id: str,
        review_status: EvidenceReviewStatus,
        practice_reference: str | None = None,
        note: str | None = None,
        reviewed_by: str | None = None,
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
    def practice_finding_history_for_assessment(
        self, assessment_id: str
    ) -> list[PracticeFindingChange]: ...
    def store_finalization_seal(
        self, assessment_id: str, digest: str, seal_version: str
    ) -> Assessment | None: ...
    def practice_finding_history(
        self, assessment_id: str, practice_reference: str
    ) -> list[PracticeFindingChange]: ...
    def create_sanitization_approval(
        self, approval: SanitizationApproval
    ) -> SanitizationApproval: ...
    def latest_sanitization_approval(self, assessment_id: str) -> SanitizationApproval | None: ...
    def get_document(self, document_id: str) -> Document | None: ...
    def document_superseded_by(self, document_id: str) -> Document | None: ...
    def superseded_document_ids(self, document_ids: Iterable[str]) -> set[str]: ...
    def attach_document(
        self, assessment_id: str, document_id: str, attached_by: str | None = None
    ) -> AssessmentDocument: ...
    def detach_document(self, assessment_id: str, document_id: str) -> bool: ...
    def documents_for_assessment(self, assessment_id: str) -> list[Document]: ...
    def attached_document_ids(self, assessment_id: str) -> list[str]: ...
    def list_documents(self, organization_id: str) -> list[Document]: ...
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
        # 0 keeps pre-ADR-0072 behaviour, which is what the default
        # here means: a caller constructing this service directly
        # (tests, scripts) gets the old engine unless it asks
        # otherwise. The deployed default is Settings', not this one.
        mapping_max_practices_per_chunk: int = 0,
        chat_similarity_threshold: float = 0.35,
        chat_result_limit: int = 5,
    ) -> None:
        self._assessments = assessment_repository
        self._vectors = vector_repository
        self._frameworks = framework_registry
        self._embedder = embedder
        self._mapping_similarity_threshold = mapping_similarity_threshold
        self._mapping_candidates_per_practice = mapping_candidates_per_practice
        self._mapping_max_practices_per_chunk = mapping_max_practices_per_chunk
        self._chat_similarity_threshold = chat_similarity_threshold
        self._chat_result_limit = chat_result_limit

    def create_assessment(
        self,
        name: str,
        framework_name: str,
        framework_version: str | None = None,
        organization_id: str | None = None,
    ) -> Assessment:
        """Pins FrameworkDefinition.version at creation time (ADR-0031),
        so this assessment's own record of what it was scored against
        survives a later framework_mapping/*.yaml content change.
        framework_version stays None if framework_name isn't a
        recognized/loaded schema at creation time — the same graceful
        fallback InvalidPracticeReferenceError's docstring already
        documents for unrecognized framework names, not an error here.

        framework_version (the PARAMETER, Sprint 18, ADR-0053): an
        explicit request to pin against a SPECIFIC version, if the
        registry has more than one loaded for framework_name — None
        (the default) resolves to whatever's currently latest, matching
        this method's pre-ADR-0053 behavior exactly. Only raises
        UnknownFrameworkVersionError when framework_name IS recognized
        but the requested version isn't among its known ones; an
        unrecognized framework_name keeps its existing silent-None
        tolerance regardless of what framework_version was passed.

        organization_id (Sprint 22, ADR-0063): which client this
        assessment belongs to, set once here and never reassignable. May
        be omitted only while exactly one organisation exists -- see
        AssessmentRepository.resolve_organization_id for why that is a
        condition rather than a default.
        """
        if self._frameworks is not None and framework_version is not None:
            known_versions = self._frameworks.available_versions(framework_name)
            if known_versions and framework_version not in known_versions:
                raise UnknownFrameworkVersionError(
                    framework_name, framework_version, known_versions
                )
        framework = (
            self._frameworks.get(framework_name, framework_version)
            if self._frameworks
            else None
        )
        created = self._assessments.create_assessment(
            name=name,
            framework_name=framework_name,
            framework_version=framework.version if framework is not None else None,
            organization_id=organization_id,
        )
        _logger.info(
            "assessment created id=%s framework=%s framework_version=%s organization=%s",
            created.id,
            framework_name,
            created.framework_version,
            created.organization_id,
        )
        return created

    def get_assessment(self, assessment_id: str) -> Assessment:
        assessment = self._assessments.get_assessment(assessment_id)
        if assessment is None:
            raise AssessmentNotFoundError(assessment_id)
        return assessment

    def list_assessments(self, organization_id: str | None = None) -> list[Assessment]:
        """Scoped to one organisation (ADR-0063). Omitting it resolves
        the same way creation does, so a single-organisation deployment
        keeps working without naming one."""
        return self._assessments.list_assessments(
            self._assessments.resolve_organization_id(organization_id)
        )

    def documents_for_assessment(self, assessment_id: str) -> list[DocumentSummary]:
        """The documents attached to one assessment (ADR-0062).

        What the Evidence tab's chooser should offer. It previously
        listed every document on the instance, so a reviewer picking
        evidence for one organisation's assessment was shown another
        organisation's policies -- and could link them, since nothing
        downstream objected.
        """
        self.get_assessment(assessment_id)  # raises if the assessment is unknown
        documents = self._assessments.documents_for_assessment(assessment_id)
        return self._summarise(documents)

    def _assert_same_organization(self, assessment: Assessment, document_id: str) -> None:
        """Refuse a cross-organisation attach before any work is done.

        The repository checks this again inside the write's own
        transaction. This one is not redundant: it is what turns the
        refusal into a 409 rather than a 500, and it happens before the
        attach touches anything. See
        AssessmentRepository._assert_same_organization for why the second
        check has to exist as well.

        A document with no registry row carries no organisation, and is
        allowed through for the reason ADR-0039's 27-of-30 legacy tail
        forces -- disclosed in ADR-0063, not silently ignored.
        """
        document = self._assessments.get_document(document_id)
        if document is None:
            return
        if document.organization_id != assessment.organization_id:
            raise CrossOrganizationAttachmentError(assessment.id, document_id)

    def resolve_organization_id(self, organization_id: str | None = None) -> str:
        return self._assessments.resolve_organization_id(organization_id)

    def list_organizations(self) -> list[Organization]:
        return self._assessments.list_organizations()

    def create_organization(self, name: str) -> Organization:
        """Names are unique, so that two clients cannot be told apart
        only by an opaque id in a chooser whose whole job is telling
        them apart."""
        cleaned = name.strip()
        if not cleaned:
            raise OrganizationNameRequiredError()
        if self._assessments.organization_by_name(cleaned) is not None:
            raise OrganizationNameTakenError(cleaned)
        created = self._assessments.create_organization(cleaned)
        _logger.info("organization created id=%s", created.id)
        return created

    def rename_organization(self, organization_id: str, name: str) -> Organization:
        """A label change that moves no record and invalidates no seal --
        the seal payload covers the organisation's id, not its name."""
        cleaned = name.strip()
        if not cleaned:
            raise OrganizationNameRequiredError()
        existing = self._assessments.organization_by_name(cleaned)
        if existing is not None and existing.id != organization_id:
            raise OrganizationNameTakenError(cleaned)
        renamed = self._assessments.rename_organization(organization_id, cleaned)
        if renamed is None:
            raise OrganizationNotFoundError(organization_id)
        return renamed

    def attach_document(
        self, assessment_id: str, document_id: str, actor: str = UNAUTHENTICATED_ACTOR
    ) -> DocumentSummary:
        """Declare that a document belongs to this assessment.

        Refuses a document that was never ingested, for the same reason
        link_evidence does: an assessment must not reference evidence
        that does not exist. The check is against the vector store
        rather than the document registry, because 27 of 30 documents in
        the original corpus predate the registry (ADR-0039) and are
        perfectly real.
        """
        assessment = self.get_assessment(assessment_id)
        if not self._vectors.chunks_for_document(document_id):
            raise EvidenceDocumentNotIngestedError(document_id)
        self._assert_same_organization(assessment, document_id)
        self._assessments.attach_document(assessment_id, document_id, attached_by=actor)
        _logger.info(
            "document attached assessment=%s document=%s actor=%s",
            assessment_id,
            document_id,
            actor,
        )
        summaries = self._summarise(self._assessments.documents_for_assessment(assessment_id))
        attached = next((s for s in summaries if s.id == document_id), None)
        if attached is not None:
            return attached
        # Ingested, attached, but no registry row -- a pre-ADR-0039
        # document. Report what is actually known rather than refusing a
        # legitimate attachment or inventing metadata for it.
        return DocumentSummary(
            id=document_id,
            filename=document_id,
            file_type="unknown",
            submitter=None,
            uploaded_at=datetime.now(UTC),
            is_superseded=False,
            parser_version="",
        )

    def detach_document(self, assessment_id: str, document_id: str) -> None:
        """Remove a document from this assessment.

        Refused while any evidence link still cites it: detaching would
        leave a citation pointing at a document the assessment no longer
        claims, which is precisely the kind of dangling reference the
        core invariant exists to prevent. Reject or remove the links
        first -- an explicit act, recorded, rather than a silent cascade.
        """
        self.get_assessment(assessment_id)
        citing = [
            link
            for link in self._assessments.evidence_for_assessment(assessment_id)
            if link.document_id == document_id
        ]
        if citing:
            raise DocumentStillCitedError(document_id, len(citing))
        if not self._assessments.detach_document(assessment_id, document_id):
            raise DocumentNotAttachedError(assessment_id, document_id)
        _logger.info(
            "document detached assessment=%s document=%s", assessment_id, document_id
        )

    def _summarise(self, documents: list[Document]) -> list[DocumentSummary]:
        superseded = self._assessments.superseded_document_ids(d.id for d in documents)
        return [
            DocumentSummary(
                id=d.id,
                filename=d.filename,
                file_type=d.file_type,
                submitter=d.submitter,
                uploaded_at=d.uploaded_at,
                is_superseded=d.id in superseded,
                parser_version=d.parser_version,
            )
            for d in documents
        ]

    def list_document_summaries(
        self, organization_id: str | None = None
    ) -> list[DocumentSummary]:
        """Every document, newest first, in the reduced shape a chooser
        needs.

        Deliberately DocumentSummary rather than DocumentDetail. The bulk
        supersession lookup answers "is this superseded", not "by which
        document", and DocumentDetail's superseded_by_document_id is an
        id -- filling it with a placeholder to satisfy the type would put
        a meaningless value in a field every other caller reads as a real
        document id. A boolean field that says exactly what is known is
        honest; a fabricated id is not.

        Supersession is resolved in bulk via superseded_document_ids
        (ADR-0050 added that method for exactly this shape of caller), so
        listing N documents costs two queries rather than N+1.

        Scoped to one organisation since ADR-0063: this is the chooser
        R-39 was about.
        """
        return self._summarise(
            self._assessments.list_documents(
                self._assessments.resolve_organization_id(organization_id)
            )
        )

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

    def finalization_readiness(self, assessment_id: str) -> FinalizationReadiness:
        """Whether this assessment may be finalized, and what blocks it.

        Blockers are unfinished *review work*, never findings. Confirmed
        gaps, rejected evidence, NOT_SATISFIED, PARTIALLY_SATISFIED and
        INSUFFICIENT_EVIDENCE do not appear: an assessment that reports
        an organization as non-compliant is a legitimate, complete
        result, and refusing to finalize it would make the platform
        unable to say the very thing it exists to say.

        Read by GET /assessments/{id}/finalization-readiness and enforced
        by transition_status, so the button the reviewer sees and the
        rule the server applies come from one function rather than two
        that can drift.
        """
        assessment = self.get_assessment(assessment_id)
        blockers: list[FinalizationBlocker] = []

        evidence_links = self._assessments.evidence_for_assessment(assessment_id)
        pending = [
            link for link in evidence_links if link.review_status == EvidenceReviewStatus.PENDING
        ]
        if pending:
            blockers.append(
                FinalizationBlocker(
                    category=FinalizationBlockerCategory.PENDING_AI_REVIEW,
                    count=len(pending),
                    affected_ids=[link.id for link in pending][:_MAX_BLOCKER_IDS],
                    summary=(
                        f"{len(pending)} AI-proposed evidence link(s) still await human review. "
                        "Accept, edit or reject each one — an unreviewed proposal must never be "
                        "part of a finalized assessment."
                    ),
                )
            )

        unresolved = [
            request
            for request in self._assessments.evidence_requests_for_assessment(assessment_id)
            if request.resolved_at is None
        ]
        if unresolved:
            blockers.append(
                FinalizationBlocker(
                    category=FinalizationBlockerCategory.UNRESOLVED_EVIDENCE_REQUEST,
                    count=len(unresolved),
                    affected_ids=[request.id for request in unresolved][:_MAX_BLOCKER_IDS],
                    summary=(
                        f"{len(unresolved)} evidence request(s) are still open. Resolve each one, "
                        "or withdraw it, before declaring the assessment complete."
                    ),
                )
            )

        findings = self._assessments.practice_findings_for_assessment(assessment_id)
        credit = performed_and_excluded_practice_ids(evidence_links, findings)
        if credit.unsupported_satisfied:
            references = sorted(credit.unsupported_satisfied)
            blockers.append(
                FinalizationBlocker(
                    category=FinalizationBlockerCategory.UNSUPPORTED_SATISFIED_FINDING,
                    count=len(references),
                    affected_ids=references[:_MAX_BLOCKER_IDS],
                    summary=(
                        f"{len(references)} practice(s) are marked SATISFIED with no accepted or "
                        "edited evidence, so they contribute no score. Link supporting evidence, "
                        "or change the finding to match what the evidence shows."
                    ),
                )
            )
        if credit.unsupported_not_applicable:
            references = sorted(credit.unsupported_not_applicable)
            blockers.append(
                FinalizationBlocker(
                    category=FinalizationBlockerCategory.UNSUPPORTED_NOT_APPLICABLE_FINDING,
                    count=len(references),
                    affected_ids=references[:_MAX_BLOCKER_IDS],
                    summary=(
                        f"{len(references)} practice(s) are marked NOT_APPLICABLE with no accepted "
                        "or edited evidence, so they remain in the scoring denominator. An "
                        "exclusion moves the score and needs the same evidence basis."
                    ),
                )
            )

        # Only checked when a registry is actually configured. A service
        # built without one (several unit-test call sites) has no
        # framework data at all, which is a deployment condition rather
        # than something wrong with this assessment.
        if self._frameworks is not None and (
            self._frameworks.get(assessment.framework_name, assessment.framework_version) is None
        ):
            pinned = assessment.framework_version or "latest"
            blockers.append(
                FinalizationBlocker(
                    category=FinalizationBlockerCategory.FRAMEWORK_VERSION_UNRESOLVED,
                    count=1,
                    affected_ids=[f"{assessment.framework_name}@{pinned}"],
                    summary=(
                        f"The pinned framework '{assessment.framework_name}' version '{pinned}' no "
                        "longer resolves, so this assessment's scores cannot be reproduced. "
                        "Restore that framework version before finalizing."
                    ),
                )
            )

        return FinalizationReadiness(
            assessment_id=assessment_id,
            status=assessment.status.value,
            is_ready=not blockers,
            blockers=blockers,
        )

    def transition_status(
        self,
        assessment_id: str,
        new_status: AssessmentStatus,
        note: str | None = None,
        actor: str = UNAUTHENTICATED_ACTOR,
    ) -> Assessment:
        assessment = self.get_assessment(assessment_id)
        allowed = _ALLOWED_TRANSITIONS[assessment.status]
        if new_status not in allowed:
            raise InvalidStatusTransitionError(assessment.status, new_status)
        # The gate lives here, not only in the UI (ADR-0058). A disabled
        # button is a usability affordance; this is the integrity
        # boundary, and it holds for any caller — curl, a script, or a
        # future second frontend.
        if new_status == AssessmentStatus.FINALIZED:
            readiness = self.finalization_readiness(assessment_id)
            if not readiness.is_ready:
                raise AssessmentNotReadyForFinalizationError(assessment_id, readiness.blockers)
        updated = self._assessments.update_status(
            assessment_id, new_status, note=note, actor=actor
        )
        if updated is None:  # pragma: no cover - existence already checked above
            raise AssessmentNotFoundError(assessment_id)
        _logger.info(
            "assessment status transition id=%s %s -> %s actor=%s",
            assessment_id,
            assessment.status,
            new_status,
            actor,
        )
        if new_status == AssessmentStatus.FINALIZED:
            updated = self._seal(updated)
        return updated

    def _seal(self, assessment: Assessment) -> Assessment:
        """Write the tamper-evidence digest for a just-finalized
        assessment (R-12, services/audit_seal.py).

        Sealed here rather than inside update_status because the seal
        covers the record as a whole -- evidence links, findings, both
        history trails, evidence requests -- and the repository layer
        deliberately does not know what constitutes "the record".

        The digest is computed from a fresh read of the stored rows, not
        from anything held in memory, so the bytes hashed at
        finalization are the same bytes verification will re-read later.
        """
        digest = audit_seal.compute_seal(
            version=audit_seal.CURRENT_SEAL_VERSION, **self._seal_inputs(assessment)
        )
        sealed = self._assessments.store_finalization_seal(
            assessment.id, digest, audit_seal.CURRENT_SEAL_VERSION
        )
        if sealed is None:  # pragma: no cover - existence already checked by the caller
            raise AssessmentNotFoundError(assessment.id)
        _logger.info(
            "finalization seal written id=%s version=%s digest=%s",
            assessment.id,
            audit_seal.CURRENT_SEAL_VERSION,
            digest,
        )
        return sealed

    def _seal_inputs(self, assessment: Assessment) -> dict[str, Any]:
        return {
            "assessment": assessment,
            "status_history": self._assessments.status_history(assessment.id),
            "evidence_links": self._assessments.evidence_for_assessment(assessment.id),
            "practice_findings": self._assessments.practice_findings_for_assessment(
                assessment.id
            ),
            "practice_finding_history": (
                self._assessments.practice_finding_history_for_assessment(assessment.id)
            ),
            "evidence_requests": self._assessments.evidence_requests_for_assessment(
                assessment.id
            ),
        }

    def verify_finalization_seal(self, assessment_id: str) -> SealVerification:
        """Recompute a finalized assessment's digest and compare it with
        the one stored at finalization.

        This is the question an auditor actually asks -- not "will your
        software let someone edit this?" but "can you show nothing did?"
        A mismatch does not say what changed or who changed it; it says
        the record is no longer the one that was finalized, which is
        itself the finding. Investigation starts there.
        """
        assessment = self.get_assessment(assessment_id)

        if assessment.sealed_digest is None or assessment.seal_version is None:
            return SealVerification(
                assessment_id=assessment_id,
                status=SealVerificationStatus.UNSEALED,
                detail=(
                    "This assessment carries no finalization seal, so there is nothing to "
                    "verify it against. Assessments finalized before sealing existed are "
                    "deliberately not sealed retroactively - a seal written now would attest "
                    "only that the record has not changed since today."
                ),
            )

        try:
            computed = audit_seal.compute_seal(
                version=assessment.seal_version, **self._seal_inputs(assessment)
            )
        except audit_seal.UnknownSealVersionError as exc:
            return SealVerification(
                assessment_id=assessment_id,
                status=SealVerificationStatus.UNVERIFIABLE,
                sealed_digest=assessment.sealed_digest,
                sealed_at=assessment.sealed_at,
                seal_version=assessment.seal_version,
                detail=str(exc),
            )

        matches = hmac.compare_digest(computed, assessment.sealed_digest)
        if not matches:
            _logger.error(
                "finalization seal mismatch id=%s sealed=%s computed=%s",
                assessment_id,
                assessment.sealed_digest,
                computed,
            )
        return SealVerification(
            assessment_id=assessment_id,
            status=(
                SealVerificationStatus.VERIFIED if matches else SealVerificationStatus.ALTERED
            ),
            sealed_digest=assessment.sealed_digest,
            computed_digest=computed,
            sealed_at=assessment.sealed_at,
            seal_version=assessment.seal_version,
            detail=(
                "The stored record still matches the seal written when this assessment was "
                "finalized."
                if matches
                else "The stored record no longer matches the seal written when this "
                "assessment was finalized. Something has changed it since - treat the "
                "assessment as unreliable until the change is explained."
            ),
        )

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
        actor: str = UNAUTHENTICATED_ACTOR,
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

        # Before the link is written, not after. Linking attaches
        # implicitly (ADR-0062) and the attach happens below, so relying
        # on the attach to refuse would leave the evidence link already
        # persisted when it did -- a cross-organisation citation in the
        # database, refused with a 409 that arrived too late to mean
        # anything. The boundary has to hold on this path as much as on
        # the explicit attach, or the refusal there is a locked front
        # door beside an open window (ADR-0063).
        self._assert_same_organization(assessment, document_id)

        if self._frameworks is not None:
            framework = self._frameworks.get(
                assessment.framework_name, assessment.framework_version
            )
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
            created_by=actor,
        )
        # Citing a document from an assessment is a statement that it
        # belongs to it, so attaching is implicit rather than a second
        # step (ADR-0062). Idempotent, and after the link so a rejected
        # link leaves no association behind.
        created = self._assessments.add_evidence_link(link)
        self._assessments.attach_document(assessment_id, document_id, attached_by=actor)
        _logger.info(
            "evidence linked assessment=%s document=%s practice=%s source=%s",
            assessment_id,
            document_id,
            practice_reference,
            source,
        )
        return created

    def evidence_for_assessment(
        self,
        assessment_id: str,
        *,
        review_status: EvidenceReviewStatus | None = None,
        domain: str | None = None,
        min_confidence: float | None = None,
        max_confidence: float | None = None,
    ) -> list[EvidenceLink]:
        """The assessment's evidence links, optionally narrowed
        (ADR-0065).

        Every filter here is a VIEW concern. None of them changes a
        record, and none of them is allowed to become an input to a
        decision -- narrowing what a reviewer reads is safe precisely
        because the accept/edit/reject transition still happens one link
        at a time, on a link a person looked at.

        Filtering runs in this layer rather than in SQL because the
        domain filter cannot be expressed in SQL at all: a link stores a
        practice_reference, and which domain that belongs to is a
        property of the framework DEFINITION, not of the row. Pushing
        the two SQL-able filters down while keeping this one here would
        put the queue's filtering in two places, which is a worse
        outcome than scanning one assessment's links in memory -- a
        bounded set already loaded whole by every other caller.

        The framework is the assessment's PINNED version (ADR-0058), not
        the latest. A reviewer filtering by domain must get the domains
        of the framework they are actually assessing.
        """
        self.get_assessment(assessment_id)  # raises AssessmentNotFoundError if missing
        links = self._assessments.evidence_for_assessment(assessment_id)

        if review_status is not None:
            links = [link for link in links if link.review_status == review_status]

        if min_confidence is not None:
            # A link with no confidence is a manual one (confidence is
            # set only for AI proposals), and it is excluded rather than
            # treated as zero -- a manual link is not a low-confidence
            # link, and folding the two together would misreport the
            # queue in the one filter most likely to be used to judge
            # proposal quality.
            links = [
                link
                for link in links
                if link.confidence is not None and link.confidence >= min_confidence
            ]

        if max_confidence is not None:
            links = [
                link
                for link in links
                if link.confidence is not None and link.confidence <= max_confidence
            ]

        if domain is not None:
            practice_ids = self._practice_ids_for_domain(assessment_id, domain)
            links = [link for link in links if link.practice_reference in practice_ids]

        return links

    def _framework_for_assessment(self, assessment_id: str) -> FrameworkDefinition | None:
        """The pinned framework definition, or None when no registry is
        wired in (the repository-only construction some tests use)."""
        if self._frameworks is None:
            return None
        assessment = self.get_assessment(assessment_id)
        return self._frameworks.get(assessment.framework_name, assessment.framework_version)

    def _practice_ids_for_domain(self, assessment_id: str, domain: str) -> set[str]:
        """Which practice ids belong to one domain of the pinned
        framework.

        Resolved from the framework definition every time rather than
        stored on the link. Domain membership is framework data
        (AGENTS.md rule 1) and belongs in framework_mapping/*.yaml, so
        there is deliberately no `if framework == "c2m2"` anywhere on
        this path and no denormalised domain column to drift from it.

        An unknown domain short code yields an empty set, so the filter
        returns nothing rather than silently returning everything --
        an empty list is a readable answer, and a full one would look
        like the filter worked.
        """
        framework = self._framework_for_assessment(assessment_id)
        if framework is None:
            return set()
        found = framework.domain(domain)
        return found.practice_ids() if found is not None else set()

    def agreement_report(self, assessment_id: str) -> AssessmentAgreementReport:
        """How often this assessment's reviewers accepted an AI proposal
        as-is, overall and per confidence band (ADR-0070).

        Evaluation, not product. It is namespaced under /aqs/ and
        rendered nowhere in the assessment UI, because an agreement rate
        on a dashboard invites being read as a verdict on the assessment
        rather than on the mapping engine -- the interpretation sentence
        travels with the numbers for the same reason.
        """
        self.get_assessment(assessment_id)  # raises AssessmentNotFoundError if missing
        links = self._assessments.evidence_for_assessment(assessment_id)
        return build_agreement_report(links)

    def evidence_queue_summary(self, assessment_id: str) -> EvidenceQueueSummary:
        """Counts over the WHOLE queue, never over a filtered view
        (ADR-0065).

        This exists so the filters cannot mislead. A reviewer looking at
        23 links needs to know whether that is 23 of 23 or 23 of 412,
        and the count that answers it must not itself be filtered or the
        answer is circular.
        """
        links = self._assessments.evidence_for_assessment(assessment_id)
        framework = self._framework_for_assessment(assessment_id)

        by_status: dict[str, int] = {status.value: 0 for status in EvidenceReviewStatus}
        for link in links:
            by_status[link.review_status.value] += 1

        by_domain: list[EvidenceDomainCount] = []
        mapped_practice_ids: set[str] = set()
        if framework is not None:
            for framework_domain in framework.domains:
                practice_ids = framework_domain.practice_ids()
                mapped_practice_ids |= practice_ids
                in_domain = [link for link in links if link.practice_reference in practice_ids]
                if not in_domain:
                    # Domains with nothing in the queue are omitted
                    # rather than listed at zero: a filter control
                    # offering ten empty domains is a worse chooser than
                    # one offering the three that have work in them.
                    continue
                by_domain.append(
                    EvidenceDomainCount(
                        short_code=framework_domain.short_code,
                        full_name=framework_domain.full_name,
                        total=len(in_domain),
                        pending=sum(
                            1
                            for link in in_domain
                            if link.review_status == EvidenceReviewStatus.PENDING
                        ),
                    )
                )

        unmapped = sum(1 for link in links if link.practice_reference not in mapped_practice_ids)

        return EvidenceQueueSummary(
            total=len(links),
            by_status=by_status,
            by_domain=by_domain,
            unmapped=unmapped,
        )

    def compute_scores(self, assessment_id: str) -> dict[str, float]:
        """Per-domain scores for this assessment's framework — cumulative
        MIL (0-3, C2M2) or coverage (0.0-1.0, NIST CSF 2.0), depending on
        the framework's declared scoring_model; see
        services/scoring_service.py. Evidence links still pending or
        rejected review do not count as performed — only accepted or
        edited ones do, per the assessment-generation skill's
        human-in-the-loop invariant. A practice with an explicit
        PracticeFinding (ADR-0030) is folded in on top of that:
        NOT_SATISFIED/INSUFFICIENT_EVIDENCE/PARTIALLY_SATISFIED never
        count as performed even with accepted evidence.

        SATISFIED and NOT_APPLICABLE additionally require an
        accepted/edited evidence link before they move anything
        (ADR-0057, superseding ADR-0030 Decision 3's "counts as performed
        regardless of evidence-link state"): positive credit and a
        shrunk denominator are both score movements, and this
        repository's governing invariant is that no score exists without
        a linked evidence trail. An unsupported finding is still
        recorded, and is reported by finalization_readiness below.
        """
        assessment = self.get_assessment(assessment_id)
        framework = (
            self._frameworks.get(assessment.framework_name, assessment.framework_version)
            if self._frameworks
            else None
        )
        if framework is None:
            raise FrameworkScoringUnavailableError(assessment.framework_name)

        evidence_links = self._assessments.evidence_for_assessment(assessment_id)
        findings = self._assessments.practice_findings_for_assessment(assessment_id)
        credit = performed_and_excluded_practice_ids(evidence_links, findings)
        return compute_assessment_domain_scores(
            framework, credit.performed_practice_ids, credit.excluded_practice_ids
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
        framework = (
            self._frameworks.get(assessment.framework_name, assessment.framework_version)
            if self._frameworks
            else None
        )
        if framework is None:
            raise FrameworkScoringUnavailableError(assessment.framework_name)

        evidence_links = self._assessments.evidence_for_assessment(assessment_id)
        findings = self._assessments.practice_findings_for_assessment(assessment_id)
        # Document-supersession flagging (Sprint 18, ADR-0050): closes the
        # gap ADR-0039 disclosed ("a reviewer can query the endpoint but
        # nothing proactively flags a superseded document... in an
        # export"). One bulk lookup for every document cited by this
        # assessment's evidence, not one query per citation.
        cited_document_ids = {link.document_id for link in evidence_links}
        superseded_document_ids = self._assessments.superseded_document_ids(cited_document_ids)
        organization = self._assessments.get_organization(assessment.organization_id)
        return build_dashboard(
            assessment,
            framework,
            evidence_links,
            findings,
            superseded_document_ids,
            organization.name if organization is not None else "",
        )

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
        # The chunk's own flag is the precise answer; the document's
        # parse status is the fallback for chunks written before
        # per-page provenance existed (ADR-0074).
        parse_status_by_document = {
            hit.document_id: getattr(
                self._assessments.get_document(hit.document_id), "parse_status", None
            )
            for hit in hits
        }
        return ChatResponse(
            question=question,
            results=[
                ChatResult(
                    practice_reference=hit.practice_reference,
                    document_id=hit.document_id,
                    chunk_id=hit.chunk_id,
                    similarity=hit.similarity,
                    chunk_text=hit.chunk_text,
                    text_provenance=resolve_text_provenance(
                        hit.is_ocr_derived, parse_status_by_document.get(hit.document_id)
                    ),
                )
                for hit in hits
            ],
        )

    def bulk_reject_evidence(
        self,
        assessment_id: str,
        evidence_link_ids: list[str],
        note: str | None = None,
        actor: str = UNAUTHENTICATED_ACTOR,
    ) -> BulkReviewResult:
        """Reject many pending links a reviewer has selected (ADR-0067).

        Reject, and only reject. There is no bulk accept and no bulk
        edit anywhere in this service, because the two are not the same
        operation wearing different labels: accepting fabricates a
        compliance claim that gets scored, sealed and exported, while
        rejecting withholds one and leaves the practice visible as a gap
        in the report. AGENTS.md rule 2 forbids auto-ACCEPTING an
        AI-proposed mapping; it says nothing about declining one, and
        the difference is the whole basis of this method existing.

        Takes explicit link ids, never a filter or a threshold. That is
        the design's load-bearing property: the caller sends the rows it
        actually displayed and a person actually confirmed, so the
        decision is made by the reviewer over a set they saw. An
        endpoint accepting "everything above 0.85" would be the
        threshold deciding, which is exactly what ADR-0065 refused and
        what this deliberately cannot express.

        Rejection is still one-shot. An already-reviewed link is skipped
        and reported rather than silently re-decided, the same rule
        review_evidence enforces for a single link.
        """
        assessment = self.get_assessment(assessment_id)
        if assessment.status == AssessmentStatus.FINALIZED:
            raise AssessmentFinalizedError(assessment_id)

        # Deduplicated, order preserved. A UI that sends the same id
        # twice should not have it counted twice in the result a person
        # reads back.
        unique_ids = list(dict.fromkeys(evidence_link_ids))
        if not unique_ids:
            return BulkReviewResult(rejected_count=0, skipped=[])

        rejected, skipped = self._assessments.bulk_reject_evidence_links(
            assessment_id, unique_ids, reviewed_by=actor, note=note
        )
        _logger.info(
            "bulk rejected %d evidence link(s) on assessment=%s by=%s (%d already reviewed)",
            rejected,
            assessment_id,
            actor,
            len(skipped),
        )
        return BulkReviewResult(
            rejected_count=rejected,
            skipped=[
                BulkReviewSkip(evidence_link_id=link_id, review_status=status)
                for link_id, status in skipped
            ],
        )

    def review_evidence(
        self,
        assessment_id: str,
        evidence_link_id: str,
        decision: EvidenceReviewStatus,
        corrected_practice_reference: str | None = None,
        note: str | None = None,
        actor: str = UNAUTHENTICATED_ACTOR,
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
                framework = self._frameworks.get(
                    assessment.framework_name, assessment.framework_version
                )
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
            reviewed_by=actor,
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
        set_by: str | None = None,
        actor: str = UNAUTHENTICATED_ACTOR,
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
            framework = self._frameworks.get(
                assessment.framework_name, assessment.framework_version
            )
            if framework is not None and practice_reference not in framework.all_practice_ids():
                raise InvalidPracticeReferenceError(practice_reference, assessment.framework_name)

        finding = self._assessments.set_practice_finding(
            assessment_id=assessment_id,
            practice_reference=practice_reference,
            status=status,
            rationale=rationale,
            # The authenticated identity, not the literal "human" this
            # defaulted to. `set_by` always meant "who decided"; it just
            # had nobody to name (ADR-0061). An explicit set_by still
            # wins, for a future non-human decider.
            set_by=set_by or actor,
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
        self,
        assessment_id: str,
        practice_reference: str,
        note: str,
        requested_by: str | None = None,
        actor: str = UNAUTHENTICATED_ACTOR,
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
            framework = self._frameworks.get(
                assessment.framework_name, assessment.framework_version
            )
            if framework is not None and practice_reference not in framework.all_practice_ids():
                raise InvalidPracticeReferenceError(practice_reference, assessment.framework_name)

        request = self._assessments.create_evidence_request(
            EvidenceRequest(
                assessment_id=assessment_id,
                practice_reference=practice_reference,
                note=note,
                # The authenticated identity wins over anything the
                # client claimed. A caller naming whoever it likes is
                # not attribution (ADR-0061); the request body's field
                # survives only as a fallback for a direct, unproxied
                # call, where there is no identity to prefer.
                requested_by=(
                    actor if actor != UNAUTHENTICATED_ACTOR else (requested_by or actor)
                ),
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
        self,
        assessment_id: str,
        request_id: str,
        resolved_by: str | None = None,
        actor: str = UNAUTHENTICATED_ACTOR,
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

        # Same precedence as request_more_evidence: an authenticated
        # identity outranks whatever the client put in the body.
        attributed_to = actor if actor != UNAUTHENTICATED_ACTOR else (resolved_by or actor)
        resolved = self._assessments.resolve_evidence_request(
            request_id, resolved_by=attributed_to
        )
        if resolved is None:  # pragma: no cover - existence already checked above
            raise EvidenceRequestNotFoundError(request_id)
        _logger.info(
            "evidence request resolved assessment=%s request=%s resolved_by=%s",
            assessment_id,
            request_id,
            attributed_to,
        )
        return resolved

    def propose_mappings(
        self, assessment_id: str, actor: str = UNAUTHENTICATED_ACTOR
    ) -> list[EvidenceLink]:
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

        framework = (
            self._frameworks.get(assessment.framework_name, assessment.framework_version)
            if self._frameworks
            else None
        )
        if framework is None:
            raise FrameworkScoringUnavailableError(assessment.framework_name)

        existing_links = self._assessments.evidence_for_assessment(assessment_id)
        # Attached documents, not just cited ones (ADR-0062). The old
        # derivation from evidence links could not express "attached but
        # not yet cited" -- which is the state a reviewer is in before
        # the engine has ever run, and made proposing over a newly
        # uploaded document impossible until they had manually linked it
        # first.
        document_ids = sorted(set(self._assessments.attached_document_ids(assessment_id)))
        already_covered = {
            link.practice_reference
            for link in existing_links
            if link.review_status != EvidenceReviewStatus.REJECTED
        }
        # How many live claims each chunk already carries, so ADR-0072's
        # cap counts them. Without this the cap would be per-call: the
        # practices already holding proposals count as covered and drop
        # out, freeing their slots for the next three, so clicking
        # propose repeatedly would rebuild the old flood a tier at a
        # time. Rejected links are excluded on the same reasoning as
        # already_covered directly above.
        existing_claims_per_chunk: dict[str, int] = {}
        for link in existing_links:
            if link.review_status == EvidenceReviewStatus.REJECTED or link.chunk_id is None:
                continue
            existing_claims_per_chunk[link.chunk_id] = (
                existing_claims_per_chunk.get(link.chunk_id, 0) + 1
            )

        proposals = find_mapping_candidates(
            framework=framework,
            document_ids=document_ids,
            already_covered_practice_ids=already_covered,
            embedder=self._embedder,
            vector_repository=self._vectors,
            similarity_threshold=self._mapping_similarity_threshold,
            candidates_per_practice=self._mapping_candidates_per_practice,
            max_practices_per_chunk=self._mapping_max_practices_per_chunk,
            existing_claims_per_chunk=existing_claims_per_chunk,
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
                # The operator who asked for proposals, not a claim that
                # a human chose this mapping -- `source` says the engine
                # did, and review_status says nobody has confirmed it.
                created_by=actor,
            )
            created.append(self._assessments.add_evidence_link(link))
        _logger.info(
            "propose-mappings assessment=%s documents=%d proposals_created=%d",
            assessment_id,
            len(document_ids),
            len(created),
        )
        return created
