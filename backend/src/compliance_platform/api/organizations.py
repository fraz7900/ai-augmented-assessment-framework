"""Organization endpoints (Sprint 22, ADR-0063). Thin HTTP boundary only,
per api/README.md — the rules live in services/assessment_service.py.

Create, list and rename. There is deliberately no delete: an
organisation owns assessments, documents and seals, and what should
happen to those when it goes away is a data-loss decision that deserves
its own ADR rather than a default. There is also no endpoint that moves
an assessment or a document between organisations, for the same reason —
whose record it is is set once, and the finalization seal covers it.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from compliance_platform.api.dependencies import get_assessment_service
from compliance_platform.models.assessment import Organization
from compliance_platform.services.assessment_service import AssessmentService

router = APIRouter(prefix="/organizations", tags=["organizations"])


class CreateOrganizationRequest(BaseModel):
    name: str


class RenameOrganizationRequest(BaseModel):
    name: str


@router.get("", response_model=list[Organization])
def list_organizations(
    service: AssessmentService = Depends(get_assessment_service),
) -> list[Organization]:
    """Every organisation on this instance, oldest first.

    Unscoped on purpose, and the only endpoint that is: a chooser has to
    be able to name what it is choosing between. It exposes names and
    ids, never any client's evidence.
    """
    return service.list_organizations()


@router.post("", response_model=Organization, status_code=201)
def create_organization(
    request: CreateOrganizationRequest,
    service: AssessmentService = Depends(get_assessment_service),
) -> Organization:
    return service.create_organization(name=request.name)


@router.patch("/{organization_id}", response_model=Organization)
def rename_organization(
    organization_id: str,
    request: RenameOrganizationRequest,
    service: AssessmentService = Depends(get_assessment_service),
) -> Organization:
    """A label change only. It moves no record and invalidates no seal,
    because the seal payload covers the organisation's id rather than
    its name — which is why a fresh install can start as "Unassigned"
    and be given its real name later without consequence.
    """
    return service.rename_organization(organization_id, request.name)
