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
    registry: FrameworkRegistry = Depends(get_cached_framework_registry),
) -> FrameworkDefinition:
    framework = registry.get(name)
    if framework is None:
        raise HTTPException(
            status_code=404, detail=f"No framework definition loaded for '{name}'."
        )
    return framework
