"""Ingestion endpoint. Thin HTTP boundary only, per api/README.md: parse
the request, call the service, translate service exceptions into HTTP
status codes. No parsing/chunking/embedding logic belongs in this file.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from compliance_platform.api.dependencies import get_ingestion_service
from compliance_platform.models.schemas import IngestionResult
from compliance_platform.services.ingestion_service import (
    IngestionService,
    UnsupportedDocumentError,
)

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("", response_model=IngestionResult)
async def ingest_document(
    file: UploadFile = File(...),
    submitter: str | None = Form(default=None),
    service: IngestionService = Depends(get_ingestion_service),
) -> IngestionResult:
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Uploaded file has no filename.")

    content = await file.read()

    try:
        return service.ingest(filename=file.filename, content=content, submitter=submitter)
    except UnsupportedDocumentError as exc:
        # Expected outcome (scanned PDF, empty doc, encoding failure) —
        # a client error, not a server error. See document-parsing skill.
        raise HTTPException(
            status_code=422,
            detail={"status": exc.status.value, "warnings": exc.warnings},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
