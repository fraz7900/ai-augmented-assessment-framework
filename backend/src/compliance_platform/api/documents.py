"""Document detail endpoint (Sprint 18, ADR-0039). Thin HTTP boundary
only, per api/README.md — see services/assessment_service.py.get_document_detail.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from compliance_platform.api.dependencies import get_assessment_service
from compliance_platform.models.schemas import DocumentDetail
from compliance_platform.services.assessment_service import AssessmentService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(
    document_id: str,
    service: AssessmentService = Depends(get_assessment_service),
) -> DocumentDetail:
    return service.get_document_detail(document_id)
