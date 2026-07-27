"""Framework browsing endpoint. Thin HTTP boundary only, per
api/README.md: no YAML parsing or framework-structure logic belongs
here — see services/framework_loader.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from compliance_platform.api.dependencies import get_cached_framework_registry
from compliance_platform.models.framework import FrameworkDefinition
from compliance_platform.services.framework_loader import FrameworkRegistry

router = APIRouter(prefix="/frameworks", tags=["frameworks"])


@router.get("/{name}", response_model=FrameworkDefinition)
def get_framework(
    name: str,
    version: str | None = None,
    registry: FrameworkRegistry = Depends(get_cached_framework_registry),
) -> FrameworkDefinition:
    """version (Sprint 18, ADR-0053): browse a SPECIFIC loaded version of
    this framework, if the registry has more than one — omit for
    whatever's currently latest, matching this endpoint's pre-ADR-0053
    behavior exactly.
    """
    framework = registry.get(name, version)
    if framework is None:
        detail = (
            f"No framework definition loaded for '{name}'."
            if version is None
            else f"No framework definition loaded for '{name}' version '{version}'."
        )
        raise HTTPException(status_code=404, detail=detail)
    return framework


@router.get("/{name}/versions", response_model=list[str])
def get_framework_versions(
    name: str,
    registry: FrameworkRegistry = Depends(get_cached_framework_registry),
) -> list[str]:
    """Every version this registry knows about for `name` (Sprint 18,
    ADR-0053), so a caller can discover what's actually available to
    pass to ?version= above (or to CreateAssessmentRequest.framework_version)
    without guessing. [] for an unrecognized name, never a 404 — an
    empty list of versions is itself the honest, correct answer.
    """
    return registry.available_versions(name)
