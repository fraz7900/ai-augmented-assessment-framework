"""Assessment endpoints. Thin HTTP boundary only, per api/README.md:
parse the request, call the service, translate service exceptions into
HTTP status codes. No state-machine or evidence-linking logic belongs
in this file — see services/assessment_service.py.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from compliance_platform.api.dependencies import get_assessment_service
from compliance_platform.models.assessment import (
    Assessment,
    AssessmentStatus,
    AssessmentStatusChange,
    EvidenceLink,
    EvidenceReviewStatus,
    EvidenceSource,
)
from compliance_platform.models.report import DashboardReport
from compliance_platform.services.assessment_service import (
    AssessmentFinalizedError,
    AssessmentNotFoundError,
    AssessmentService,
    EvidenceAlreadyReviewedError,
    EvidenceDocumentNotIngestedError,
    EvidenceLinkNotFoundError,
    FrameworkScoringUnavailableError,
    InvalidPracticeReferenceError,
    InvalidReviewDecisionError,
    InvalidStatusTransitionError,
    MappingEngineUnavailableError,
)

router = APIRouter(prefix="/assessments", tags=["assessments"])


class CreateAssessmentRequest(BaseModel):
    name: str
    framework_name: str


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


@router.post("", response_model=Assessment)
def create_assessment(
    request: CreateAssessmentRequest,
    service: AssessmentService = Depends(get_assessment_service),
) -> Assessment:
    return service.create_assessment(name=request.name, framework_name=request.framework_name)


@router.get("", response_model=list[Assessment])
def list_assessments(
    service: AssessmentService = Depends(get_assessment_service),
) -> list[Assessment]:
    return service.list_assessments()


@router.get("/{assessment_id}", response_model=Assessment)
def get_assessment(
    assessment_id: str,
    service: AssessmentService = Depends(get_assessment_service),
) -> Assessment:
    try:
        return service.get_assessment(assessment_id)
    except AssessmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{assessment_id}/status", response_model=Assessment)
def transition_status(
    assessment_id: str,
    request: StatusTransitionRequest,
    service: AssessmentService = Depends(get_assessment_service),
) -> Assessment:
    try:
        return service.transition_status(assessment_id, request.status, note=request.note)
    except AssessmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{assessment_id}/status-history", response_model=list[AssessmentStatusChange])
def get_status_history(
    assessment_id: str,
    service: AssessmentService = Depends(get_assessment_service),
) -> list[AssessmentStatusChange]:
    try:
        return service.status_history(assessment_id)
    except AssessmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{assessment_id}/evidence", response_model=EvidenceLink)
def link_evidence(
    assessment_id: str,
    request: LinkEvidenceRequest,
    service: AssessmentService = Depends(get_assessment_service),
) -> EvidenceLink:
    try:
        return service.link_evidence(
            assessment_id=assessment_id,
            document_id=request.document_id,
            practice_reference=request.practice_reference,
            chunk_id=request.chunk_id,
            note=request.note,
            source=request.source,
        )
    except AssessmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AssessmentFinalizedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except EvidenceDocumentNotIngestedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InvalidPracticeReferenceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{assessment_id}/evidence", response_model=list[EvidenceLink])
def list_evidence(
    assessment_id: str,
    service: AssessmentService = Depends(get_assessment_service),
) -> list[EvidenceLink]:
    try:
        return service.evidence_for_assessment(assessment_id)
    except AssessmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
    try:
        return service.compute_scores(assessment_id)
    except AssessmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FrameworkScoringUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
    try:
        return service.build_dashboard(assessment_id)
    except AssessmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FrameworkScoringUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


_SLUG_INVALID_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _slugify_filename(name: str) -> str:
    slug = _SLUG_INVALID_CHARS.sub("-", name).strip("-")
    return slug or "assessment"


@router.get("/{assessment_id}/report/pdf")
def get_dashboard_pdf(
    assessment_id: str,
    service: AssessmentService = Depends(get_assessment_service),
) -> Response:
    """PDF rendering of the same dashboard GET /dashboard returns
    (Sprint 7) — see services/export_service.py and ADR-0013. Same
    error mapping as the dashboard endpoint, since both are built from
    the same DashboardReport.
    """
    try:
        assessment = service.get_assessment(assessment_id)
        pdf_bytes = service.generate_dashboard_pdf(assessment_id)
    except AssessmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FrameworkScoringUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    filename = f"{_slugify_filename(assessment.name)}_dashboard.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{assessment_id}/report/xlsx")
def get_dashboard_xlsx(
    assessment_id: str,
    service: AssessmentService = Depends(get_assessment_service),
) -> Response:
    """XLSX rendering of the same dashboard GET /dashboard returns
    (Sprint 7) — see services/export_service.py and ADR-0013.
    """
    try:
        assessment = service.get_assessment(assessment_id)
        xlsx_bytes = service.generate_dashboard_xlsx(assessment_id)
    except AssessmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FrameworkScoringUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    filename = f"{_slugify_filename(assessment.name)}_dashboard.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{assessment_id}/evidence/{evidence_link_id}/review", response_model=EvidenceLink)
def review_evidence(
    assessment_id: str,
    evidence_link_id: str,
    request: ReviewEvidenceRequest,
    service: AssessmentService = Depends(get_assessment_service),
) -> EvidenceLink:
    """Applies a human accept/edit/reject decision to a pending evidence
    link — see services/assessment_service.py.review_evidence and the
    assessment-generation skill's human-in-the-loop invariant.
    """
    try:
        return service.review_evidence(
            assessment_id=assessment_id,
            evidence_link_id=evidence_link_id,
            decision=request.decision,
            corrected_practice_reference=request.corrected_practice_reference,
            note=request.note,
        )
    except AssessmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except EvidenceLinkNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AssessmentFinalizedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except EvidenceAlreadyReviewedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidReviewDecisionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except InvalidPracticeReferenceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{assessment_id}/propose-mappings", response_model=list[EvidenceLink])
def propose_mappings(
    assessment_id: str,
    service: AssessmentService = Depends(get_assessment_service),
) -> list[EvidenceLink]:
    """Runs the retrieval-based mapping engine (services/mapping_service.py,
    ADR-0011) and persists any resulting proposals as AI-proposed,
    pending-review evidence links — always over documents already
    associated with this assessment, never the whole vector store.
    """
    try:
        return service.propose_mappings(assessment_id)
    except AssessmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AssessmentFinalizedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FrameworkScoringUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except MappingEngineUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
