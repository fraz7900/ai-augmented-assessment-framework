"""Assessment endpoints. Thin HTTP boundary only, per api/README.md:
parse the request, call the service, return the response. No
state-machine or evidence-linking logic belongs in this file — see
services/assessment_service.py.

Exception-to-HTTP-status mapping is centralized in
api/error_handlers.py (Sprint 9 refactor, ADR-0015): every custom
domain exception listed there maps to the same status code everywhere
it's raised, so endpoints below simply let it propagate rather than
catching it themselves. The one exception is bare ValueError
(review_evidence's missing corrected_practice_reference case), which is
deliberately NOT handled globally — it's too generic a type to
intercept app-wide — so it's still caught locally, right there.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from compliance_platform.api.dependencies import get_assessment_service
from compliance_platform.core.identity import get_actor
from compliance_platform.models.assessment import (
    Assessment,
    AssessmentStatus,
    AssessmentStatusChange,
    EvidenceLink,
    EvidenceRequest,
    EvidenceReviewStatus,
    EvidenceSource,
    PracticeFinding,
    PracticeFindingChange,
    PracticeFindingStatus,
    SanitizationApproval,
)
from compliance_platform.models.chat import ChatResponse
from compliance_platform.models.report import DashboardReport, EvidenceQueueSummary
from compliance_platform.models.sanitization import SanitizationPreview
from compliance_platform.models.schemas import (
    DocumentSummary,
    FinalizationReadiness,
    SealVerification,
)
from compliance_platform.services.assessment_service import AssessmentService

router = APIRouter(prefix="/assessments", tags=["assessments"])


class CreateAssessmentRequest(BaseModel):
    name: str
    framework_name: str
    # Explicit pin to a SPECIFIC framework version, if the registry has
    # more than one loaded for framework_name (Sprint 18, ADR-0053).
    # None (the default) resolves to whatever's currently latest -- the
    # same behavior this endpoint always had before this field existed.
    framework_version: str | None = None
    # Which client this assessment belongs to (Sprint 22, ADR-0063). May
    # be omitted only while exactly one organisation exists; with two or
    # more, omitting it is a 400 rather than a guess.
    organization_id: str | None = None


class StatusTransitionRequest(BaseModel):
    status: AssessmentStatus
    note: str | None = None


class LinkEvidenceRequest(BaseModel):
    document_id: str
    practice_reference: str
    chunk_id: str | None = None
    note: str | None = None
    source: EvidenceSource = EvidenceSource.MANUAL


class ReviewEvidenceRequest(BaseModel):
    decision: EvidenceReviewStatus
    corrected_practice_reference: str | None = None
    note: str | None = None


class ChatQuestionRequest(BaseModel):
    question: str


class SetPracticeFindingRequest(BaseModel):
    status: PracticeFindingStatus
    rationale: str


class RequestMoreEvidenceRequest(BaseModel):
    note: str
    # Optional since ADR-0061: the authenticated identity is preferred
    # and this is ignored whenever one is present. Kept for a direct,
    # unproxied API caller that has no other way to say who it is --
    # removing it outright would break those callers to no benefit,
    # since the server already refuses to trust it when it matters.
    requested_by: str | None = None


class ResolveEvidenceRequestRequest(BaseModel):
    resolved_by: str | None = None


@router.post("", response_model=Assessment)
def create_assessment(
    request: CreateAssessmentRequest,
    service: AssessmentService = Depends(get_assessment_service),
) -> Assessment:
    return service.create_assessment(
        name=request.name,
        framework_name=request.framework_name,
        framework_version=request.framework_version,
        organization_id=request.organization_id,
    )


@router.get("", response_model=list[Assessment])
def list_assessments(
    organization_id: str | None = None,
    service: AssessmentService = Depends(get_assessment_service),
) -> list[Assessment]:
    """Scoped to one organisation (ADR-0063). Omitting it is allowed only
    while exactly one exists, so a single-organisation deployment does
    not have to name it and a multi-client one cannot forget to."""
    return service.list_assessments(organization_id)


@router.get("/{assessment_id}", response_model=Assessment)
def get_assessment(
    assessment_id: str,
    service: AssessmentService = Depends(get_assessment_service),
) -> Assessment:
    return service.get_assessment(assessment_id)


@router.post("/{assessment_id}/status", response_model=Assessment)
def transition_status(
    assessment_id: str,
    request: StatusTransitionRequest,
    service: AssessmentService = Depends(get_assessment_service),
    actor: str = Depends(get_actor),
) -> Assessment:
    return service.transition_status(
        assessment_id, request.status, note=request.note, actor=actor
    )


@router.get("/{assessment_id}/finalization-readiness", response_model=FinalizationReadiness)
def get_finalization_readiness(
    assessment_id: str,
    service: AssessmentService = Depends(get_assessment_service),
) -> FinalizationReadiness:
    """Whether this assessment may be finalized, and what blocks it
    (ADR-0058).

    Blockers are machine-readable categories with the affected ids, so
    the UI renders a checklist and disables its button without parsing
    English. The same function backs the server-side gate in
    transition_status — this endpoint reports the rule, it does not
    define a second one.
    """
    return service.finalization_readiness(assessment_id)


@router.get("/{assessment_id}/verify", response_model=SealVerification)
def verify_seal(
    assessment_id: str,
    service: AssessmentService = Depends(get_assessment_service),
) -> SealVerification:
    """Check a finalized assessment against the seal written when it was
    finalized (R-12).

    Answers the question an auditor asks about a compliance record:
    not "can your software edit this?" but "can you show nothing did?"
    The stored and recomputed digests are both returned, so anyone
    holding an exported report can compare its printed seal against
    this without trusting the verdict field.

    Deliberately a plain 200 for every outcome, including ALTERED. A
    non-2xx would make a detected alteration look like a failure to
    answer, and this endpoint answering successfully is exactly what a
    detected alteration IS.
    """
    return service.verify_finalization_seal(assessment_id)


class AttachDocumentRequest(BaseModel):
    document_id: str


@router.get("/{assessment_id}/documents", response_model=list[DocumentSummary])
def list_assessment_documents(
    assessment_id: str,
    service: AssessmentService = Depends(get_assessment_service),
) -> list[DocumentSummary]:
    """The documents attached to this assessment (ADR-0062).

    What the evidence chooser should offer. `GET /documents` still lists
    every document on the instance and is what the attach flow browses;
    this is the scoped view.
    """
    return service.documents_for_assessment(assessment_id)


@router.post("/{assessment_id}/documents", response_model=DocumentSummary)
def attach_document(
    assessment_id: str,
    request: AttachDocumentRequest,
    service: AssessmentService = Depends(get_assessment_service),
    actor: str = Depends(get_actor),
) -> DocumentSummary:
    return service.attach_document(assessment_id, request.document_id, actor=actor)


@router.delete("/{assessment_id}/documents/{document_id}", status_code=204)
def detach_document(
    assessment_id: str,
    document_id: str,
    service: AssessmentService = Depends(get_assessment_service),
) -> Response:
    """Remove a document from this assessment. Refused while evidence
    links still cite it — see AssessmentService.detach_document."""
    service.detach_document(assessment_id, document_id)
    return Response(status_code=204)


@router.get("/{assessment_id}/status-history", response_model=list[AssessmentStatusChange])
def get_status_history(
    assessment_id: str,
    service: AssessmentService = Depends(get_assessment_service),
) -> list[AssessmentStatusChange]:
    return service.status_history(assessment_id)


@router.post("/{assessment_id}/evidence", response_model=EvidenceLink)
def link_evidence(
    assessment_id: str,
    request: LinkEvidenceRequest,
    service: AssessmentService = Depends(get_assessment_service),
    actor: str = Depends(get_actor),
) -> EvidenceLink:
    return service.link_evidence(
        actor=actor,
        assessment_id=assessment_id,
        document_id=request.document_id,
        practice_reference=request.practice_reference,
        chunk_id=request.chunk_id,
        note=request.note,
        source=request.source,
    )


@router.get("/{assessment_id}/evidence", response_model=list[EvidenceLink])
def list_evidence(
    assessment_id: str,
    review_status: EvidenceReviewStatus | None = Query(
        default=None, description="Only links in this review state."
    ),
    domain: str | None = Query(
        default=None,
        description=(
            "Only links whose practice belongs to this domain short code, resolved "
            "against the assessment's pinned framework version. An unknown code "
            "returns an empty list rather than everything."
        ),
    ),
    min_confidence: float | None = Query(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Only AI-proposed links at or above this retrieval similarity. NOT a "
            "calibrated probability (ADR-0011) -- see the confidence field. Manual "
            "links, which carry no confidence, are excluded rather than counted as 0."
        ),
    ),
    max_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    service: AssessmentService = Depends(get_assessment_service),
) -> list[EvidenceLink]:
    """This assessment's evidence links, optionally narrowed (ADR-0065).

    Every parameter is a view filter. None of them changes a record, and
    the response shape is unchanged from the unfiltered call, so an
    existing caller that passes nothing sees exactly what it saw before.
    """
    return service.evidence_for_assessment(
        assessment_id,
        review_status=review_status,
        domain=domain,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
    )


@router.get("/{assessment_id}/evidence/summary", response_model=EvidenceQueueSummary)
def get_evidence_summary(
    assessment_id: str,
    service: AssessmentService = Depends(get_assessment_service),
) -> EvidenceQueueSummary:
    """What the whole queue holds, so a filtered view can say what it is
    a subset of (ADR-0065). Deliberately takes no filter parameters --
    a total that moves with the filter answers nothing.
    """
    return service.evidence_queue_summary(assessment_id)


@router.get("/{assessment_id}/score", response_model=dict[str, float])
def get_scores(
    assessment_id: str,
    service: AssessmentService = Depends(get_assessment_service),
) -> dict[str, float]:
    """Per-domain score. Meaning depends on the assessment's framework —
    check GET /frameworks/{name}'s scoring_model field: "cumulative_mil"
    means a whole-number MIL 0-3 (C2M2); "coverage" means a 0.0-1.0
    fraction of subcategories with evidence (NIST CSF 2.0, which has no
    native maturity concept — see ADR-0010). A domain not yet
    transcribed into framework_mapping/ always reports 0/0.0, not an
    error — see Domain.practices_populated.
    """
    return service.compute_scores(assessment_id)


@router.get("/{assessment_id}/dashboard", response_model=DashboardReport)
def get_dashboard(
    assessment_id: str,
    service: AssessmentService = Depends(get_assessment_service),
) -> DashboardReport:
    """Executive dashboard (Sprint 6): situation/complication/resolution
    view of this assessment — see services/report_service.py and
    ADR-0012. No LLM narrative generation; every figure is computed
    directly from real evidence links and the framework's structured
    schema.
    """
    return service.build_dashboard(assessment_id)


_SLUG_INVALID_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _slugify_filename(name: str) -> str:
    slug = _SLUG_INVALID_CHARS.sub("-", name).strip("-")
    return slug or "assessment"


@router.get("/{assessment_id}/report/pdf")
def get_dashboard_pdf(
    assessment_id: str,
    sanitized: bool = False,
    service: AssessmentService = Depends(get_assessment_service),
) -> Response:
    """PDF rendering of the same dashboard GET /dashboard returns
    (Sprint 7) — see services/export_service.py and ADR-0013. Same
    error mapping as the dashboard endpoint, since both are built from
    the same DashboardReport. sanitized=true (ADR-0032) requires a
    current, matching PracticeFinding/evidence-state approval recorded
    via POST .../sanitization/approve first — see
    services/assessment_service.py.
    """
    assessment = service.get_assessment(assessment_id)
    pdf_bytes = service.generate_dashboard_pdf(assessment_id, sanitized=sanitized)
    suffix = "_sanitized" if sanitized else ""
    filename = f"{_slugify_filename(assessment.name)}_dashboard{suffix}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{assessment_id}/report/xlsx")
def get_dashboard_xlsx(
    assessment_id: str,
    sanitized: bool = False,
    service: AssessmentService = Depends(get_assessment_service),
) -> Response:
    """XLSX rendering of the same dashboard GET /dashboard returns
    (Sprint 7) — see services/export_service.py and ADR-0013. See
    get_dashboard_pdf's docstring for the sanitized=true behavior.
    """
    assessment = service.get_assessment(assessment_id)
    xlsx_bytes = service.generate_dashboard_xlsx(assessment_id, sanitized=sanitized)
    suffix = "_sanitized" if sanitized else ""
    filename = f"{_slugify_filename(assessment.name)}_dashboard{suffix}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class SanitizationPreviewRequest(BaseModel):
    custom_terms: list[str] = []


class ApproveSanitizationRequest(BaseModel):
    custom_terms: list[str] = []
    approved_by: str


@router.post("/{assessment_id}/sanitization/preview", response_model=SanitizationPreview)
def preview_sanitization(
    assessment_id: str,
    request: SanitizationPreviewRequest,
    service: AssessmentService = Depends(get_assessment_service),
) -> SanitizationPreview:
    """Read-only preview/diff of what a sanitized export would redact
    or pseudonymize (ADR-0032) — never persisted, never itself
    authorizes an export. custom_terms is the reviewer-supplied list of
    organization-specific identifiers (names, facility/vendor/customer/
    employee identifiers) to pseudonymize; see
    services/sanitization_service.py for why those categories can't be
    detected automatically without fabricating an NER capability this
    project hasn't evaluated.
    """
    return service.preview_sanitization(assessment_id, request.custom_terms)


@router.post("/{assessment_id}/sanitization/approve", response_model=SanitizationApproval)
def approve_sanitization(
    assessment_id: str,
    request: ApproveSanitizationRequest,
    service: AssessmentService = Depends(get_assessment_service),
) -> SanitizationApproval:
    """Records explicit human approval of one specific sanitized report
    (ADR-0032's "never silently publish an AI-sanitized report" rule).
    Required before GET .../report/pdf|xlsx?sanitized=true will
    succeed; a later change to the underlying report invalidates this
    approval automatically (see SanitizationApprovalStaleError).
    """
    return service.approve_sanitization(
        assessment_id, request.custom_terms, request.approved_by
    )


@router.post("/{assessment_id}/evidence/{evidence_link_id}/review", response_model=EvidenceLink)
def review_evidence(
    assessment_id: str,
    evidence_link_id: str,
    request: ReviewEvidenceRequest,
    service: AssessmentService = Depends(get_assessment_service),
    actor: str = Depends(get_actor),
) -> EvidenceLink:
    """Applies a human accept/edit/reject decision to a pending evidence
    link — see services/assessment_service.py.review_evidence and the
    assessment-generation skill's human-in-the-loop invariant. Only
    ValueError (a missing corrected_practice_reference on an "edited"
    decision) is caught here — every other exception this can raise is
    handled globally, see api/error_handlers.py.
    """
    try:
        return service.review_evidence(
            assessment_id=assessment_id,
            evidence_link_id=evidence_link_id,
            decision=request.decision,
            corrected_practice_reference=request.corrected_practice_reference,
            note=request.note,
            actor=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put(
    "/{assessment_id}/practice-findings/{practice_reference}", response_model=PracticeFinding
)
def set_practice_finding(
    assessment_id: str,
    practice_reference: str,
    request: SetPracticeFindingRequest,
    service: AssessmentService = Depends(get_assessment_service),
    actor: str = Depends(get_actor),
) -> PracticeFinding:
    """Records a reviewer's explicit compliance judgment for one
    practice — SATISFIED, PARTIALLY_SATISFIED, NOT_SATISFIED,
    INSUFFICIENT_EVIDENCE, or NOT_APPLICABLE (ADR-0030). PUT, not POST:
    idempotent upsert of the single current finding for this
    (assessment, practice) pair, not a growing list of independent
    records — see services/assessment_service.py.set_practice_finding
    and PracticeFindingChange for the append-only history this still
    preserves underneath.
    """
    return service.set_practice_finding(
        assessment_id=assessment_id,
        practice_reference=practice_reference,
        status=request.status,
        rationale=request.rationale,
        actor=actor,
    )


@router.get("/{assessment_id}/practice-findings", response_model=list[PracticeFinding])
def list_practice_findings(
    assessment_id: str,
    service: AssessmentService = Depends(get_assessment_service),
) -> list[PracticeFinding]:
    return service.practice_findings_for_assessment(assessment_id)


@router.get(
    "/{assessment_id}/practice-findings/{practice_reference}/history",
    response_model=list[PracticeFindingChange],
)
def get_practice_finding_history(
    assessment_id: str,
    practice_reference: str,
    service: AssessmentService = Depends(get_assessment_service),
) -> list[PracticeFindingChange]:
    return service.practice_finding_history(assessment_id, practice_reference)


@router.post(
    "/{assessment_id}/practice-findings/{practice_reference}/evidence-requests",
    response_model=EvidenceRequest,
)
def request_more_evidence(
    assessment_id: str,
    practice_reference: str,
    request: RequestMoreEvidenceRequest,
    service: AssessmentService = Depends(get_assessment_service),
    actor: str = Depends(get_actor),
) -> EvidenceRequest:
    """Records a reviewer's explicit request that someone go find and
    upload more evidence for this practice (ADR-0043) — a workflow
    action distinct from set_practice_finding's compliance judgment;
    the two can coexist for the same practice. POST, not PUT: each call
    creates a new request, not an idempotent upsert of a single current
    one — multiple open requests can exist for the same practice.
    """
    return service.request_more_evidence(
        assessment_id=assessment_id,
        practice_reference=practice_reference,
        note=request.note,
        requested_by=request.requested_by,
        actor=actor,
    )


@router.get("/{assessment_id}/evidence-requests", response_model=list[EvidenceRequest])
def list_evidence_requests(
    assessment_id: str,
    service: AssessmentService = Depends(get_assessment_service),
) -> list[EvidenceRequest]:
    return service.evidence_requests_for_assessment(assessment_id)


@router.post(
    "/{assessment_id}/evidence-requests/{request_id}/resolve", response_model=EvidenceRequest
)
def resolve_evidence_request(
    assessment_id: str,
    request_id: str,
    request: ResolveEvidenceRequestRequest,
    service: AssessmentService = Depends(get_assessment_service),
    actor: str = Depends(get_actor),
) -> EvidenceRequest:
    """Marks an evidence request resolved. Always explicit -- never
    inferred from a new evidence link being added, since linking
    evidence doesn't guarantee it actually addresses what was
    requested.
    """
    return service.resolve_evidence_request(
        assessment_id=assessment_id,
        request_id=request_id,
        resolved_by=request.resolved_by,
        actor=actor,
    )


@router.post("/{assessment_id}/propose-mappings", response_model=list[EvidenceLink])
def propose_mappings(
    assessment_id: str,
    service: AssessmentService = Depends(get_assessment_service),
    actor: str = Depends(get_actor),
) -> list[EvidenceLink]:
    """Runs the retrieval-based mapping engine (services/mapping_service.py,
    ADR-0011) and persists any resulting proposals as AI-proposed,
    pending-review evidence links — always over documents already
    associated with this assessment, never the whole vector store.
    """
    return service.propose_mappings(assessment_id, actor=actor)


@router.post("/{assessment_id}/chat", response_model=ChatResponse)
def chat_with_assessment(
    assessment_id: str,
    request: ChatQuestionRequest,
    service: AssessmentService = Depends(get_assessment_service),
) -> ChatResponse:
    """Retrieval-only Q&A over this assessment's reviewed evidence
    (Sprint 8) — see services/chat_service.py and ADR-0014. Returns
    ranked, cited evidence chunks; nothing here is model-generated, so
    an empty result list (no reviewed evidence, or nothing above the
    similarity threshold) is a valid 200 response, not an error.
    """
    return service.answer_question(assessment_id, request.question)
