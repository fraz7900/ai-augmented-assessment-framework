"""Document detail endpoint (Sprint 18, ADR-0039). Thin HTTP boundary
only, per api/README.md — see services/assessment_service.py.get_document_detail.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from compliance_platform.api.dependencies import get_assessment_service
from compliance_platform.models.schemas import DocumentDetail, DocumentSummary
from compliance_platform.services.assessment_service import AssessmentService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentSummary])
def list_documents(
    service: AssessmentService = Depends(get_assessment_service),
) -> list[DocumentSummary]:
    """Every ingested document, newest first.

    Declared BEFORE /{document_id} because FastAPI matches routes in
    declaration order; an empty path is unambiguous here, but keeping
    the literal route above the parameterised one is the habit that
    stops a future literal route (e.g. /recent) being swallowed as a
    document id.
    """
    return service.list_document_summaries()


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(
    document_id: str,
    service: AssessmentService = Depends(get_assessment_service),
) -> DocumentDetail:
    return service.get_document_detail(document_id)
