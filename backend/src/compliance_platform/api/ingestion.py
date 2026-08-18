"""Ingestion endpoint. Thin HTTP boundary only, per api/README.md: parse
the request, call the service, translate service exceptions into HTTP
status codes. No parsing/chunking/embedding logic belongs in this file.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from compliance_platform.api.dependencies import (
    get_ingestion_job_service,
    get_ingestion_service,
)
from compliance_platform.models.schemas import IngestionJobView, IngestionResult
from compliance_platform.services.ingestion_job_service import (
    IngestionJobService,
    IngestionQueueFullError,
)
from compliance_platform.services.ingestion_service import (
    IngestionService,
    UnknownSupersededDocumentError,
    UnsupportedDocumentError,
)

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("", response_model=IngestionResult)
async def ingest_document(
    file: UploadFile = File(...),
    submitter: str | None = Form(default=None),
    # Document versioning (ADR-0039): explicit, human-declared only —
    # never inferred from filename/content similarity.
    supersedes_document_id: str | None = Form(default=None),
    service: IngestionService = Depends(get_ingestion_service),
) -> IngestionResult:
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Uploaded file has no filename.")

    content = await file.read()

    try:
        return service.ingest(
            filename=file.filename,
            content=content,
            submitter=submitter,
            supersedes_document_id=supersedes_document_id,
        )
    except UnsupportedDocumentError as exc:
        # Expected outcome (scanned PDF, empty doc, encoding failure) —
        # a client error, not a server error. See document-parsing skill.
        raise HTTPException(
            status_code=422,
            detail={"status": exc.status.value, "warnings": exc.warnings},
        ) from exc
    except UnknownSupersededDocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/async", response_model=IngestionJobView, status_code=202)
async def ingest_document_async(
    file: UploadFile = File(...),
    submitter: str | None = Form(default=None),
    supersedes_document_id: str | None = Form(default=None),
    service: IngestionJobService = Depends(get_ingestion_job_service),
) -> IngestionJobView:
    """Queue a document and return immediately with a job to poll.

    The synchronous POST /ingest above is unchanged and still correct
    for small documents. This exists because that one holds the request
    open for the whole parse/chunk/embed pass, which a large or scanned
    document can push past the proxy's read ceiling -- returning a
    gateway timeout that is indistinguishable from a rejection and
    leaves no record the work ever started.

    202 rather than 201: nothing has been created yet at this point
    except the intent to try.
    """
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Uploaded file has no filename.")

    content = await file.read()

    try:
        job = service.submit(
            filename=file.filename,
            content=content,
            submitter=submitter,
            supersedes_document_id=supersedes_document_id,
        )
    except IngestionQueueFullError as exc:
        # 429, not 503: the server is fine, the caller is asking for more
        # than the queue will hold, and waiting is the correct response.
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return IngestionJobView.from_job(job)


@router.get("/jobs", response_model=list[IngestionJobView])
async def list_ingestion_jobs(
    limit: int = 50,
    service: IngestionJobService = Depends(get_ingestion_job_service),
) -> list[IngestionJobView]:
    return [IngestionJobView.from_job(job) for job in service.list(limit=limit)]


@router.get("/jobs/{job_id}", response_model=IngestionJobView)
async def get_ingestion_job(
    job_id: str,
    service: IngestionJobService = Depends(get_ingestion_job_service),
) -> IngestionJobView:
    job = service.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Ingestion job {job_id} not found.")
    return IngestionJobView.from_job(job)
