"""Asynchronous ingestion: queue an upload, run it off the request
thread, and let the client poll for the outcome.

Ingestion was synchronous until now. The HTTP request stayed open for
the whole parse/chunk/embed pass, so a large or scanned document could
exceed the proxy's 300s read ceiling
(deployment/frontend.nginx.conf) and surface as a gateway timeout --
with no record that the work had ever started, and no way to tell a
timeout from a rejection. That ceiling is reachable with ordinary real
evidence: a 505-page policy manual, or a deck needing OCR on most of
its pages.

This module does NOT reimplement ingestion. IngestionService.ingest()
keeps its exact failure ordering -- the compensating delete for
orphaned chunks (ADR-0046), and retaining the original only after the
registry write succeeds (ADR-0055) -- because that ordering is load
bearing and re-deriving it here would be a second place to get it
wrong. This is a job record wrapped around the same call.
"""

from __future__ import annotations

import logging
from concurrent.futures import Future
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from compliance_platform.core.config import Settings
from compliance_platform.models.assessment import (
    IngestionJob,
    IngestionJobFailure,
    IngestionJobStatus,
)
from compliance_platform.services.ingestion_service import (
    IngestionService,
    UnknownSupersededDocumentError,
    UnsupportedDocumentError,
)

_logger = logging.getLogger(__name__)


class IngestionQueueFullError(Exception):
    """Raised when too much work is already queued to accept more.

    A queued job holds its uploaded bytes in memory until a worker picks
    it up, so an unbounded queue is an unbounded memory commitment. The
    synchronous endpoint had natural backpressure -- one request, one
    upload, held only as long as the work took. Accepting uploads
    without waiting removes that, so the bound has to be reintroduced
    explicitly rather than assumed away.
    """

    def __init__(self, pending: int, limit: int) -> None:
        self.pending = pending
        self.limit = limit
        super().__init__(
            f"{pending} documents are already queued or in progress (limit {limit}). "
            "Wait for one to finish before uploading another."
        )


class JobExecutor(Protocol):
    """The bit of concurrent.futures.Executor this service uses.

    Declared as a Protocol so tests can inject an inline executor and
    assert on a finished job deterministically, rather than sleeping and
    hoping -- the same DI shape the rest of this package uses for
    embedders and repositories.
    """

    def submit(self, fn: Any, /, *args: Any, **kwargs: Any) -> Future: ...


class IngestionJobRepositoryProtocol(Protocol):
    def create_ingestion_job(self, job: IngestionJob) -> IngestionJob: ...
    def get_ingestion_job(self, job_id: str) -> IngestionJob | None: ...
    def list_ingestion_jobs(
        self, limit: int = 50, organization_id: str | None = None
    ) -> list[IngestionJob]: ...
    def mark_ingestion_job_running(self, job_id: str) -> IngestionJob | None: ...
    def complete_ingestion_job(
        self,
        job_id: str,
        *,
        document_id: str,
        chunk_count: int,
        parse_status: str,
        parser_version: str,
        embedding_backend: str,
        parse_warnings: list[str],
    ) -> IngestionJob | None: ...
    def fail_ingestion_job(
        self,
        job_id: str,
        *,
        category: IngestionJobFailure,
        message: str,
        parse_warnings: list[str] | None = None,
    ) -> IngestionJob | None: ...
    def fail_interrupted_ingestion_jobs(self) -> int: ...
    def delete_expired_ingestion_jobs(self, cutoff: datetime) -> int: ...


class IngestionJobService:
    def __init__(
        self,
        settings: Settings,
        ingestion_service: IngestionService,
        job_repository: IngestionJobRepositoryProtocol,
        executor: JobExecutor,
    ) -> None:
        self._settings = settings
        self._ingestion = ingestion_service
        self._jobs = job_repository
        self._executor = executor

    # ---- Command side --------------------------------------------------

    def submit(
        self,
        filename: str,
        content: bytes,
        submitter: str | None = None,
        supersedes_document_id: str | None = None,
        organization_id: str | None = None,
    ) -> IngestionJob:
        """Record a QUEUED job and hand the work to the executor.

        Size is checked here rather than in the worker so an oversized
        upload is refused while the client is still on the call, the way
        it was before this endpoint existed. A job row for it would be a
        worse answer than an immediate error: there is nothing to poll
        for and nothing to retry.

        The organisation is resolved here for exactly the same reason
        (ADR-0063): an unknown or ambiguous organisation is a bad
        request, and finding that out from a job row that failed two
        minutes later would be a worse answer than a 400 the client is
        still waiting for.
        """
        resolved_organization_id = self._ingestion.resolve_organization_id(organization_id)
        if len(content) > self._settings.max_upload_bytes:
            raise ValueError(
                f"File exceeds maximum upload size of {self._settings.max_upload_bytes} bytes."
            )

        pending = sum(
            1
            for job in self._jobs.list_ingestion_jobs(limit=self._settings.max_pending_ingestions)
            if job.status in (IngestionJobStatus.QUEUED, IngestionJobStatus.RUNNING)
        )
        if pending >= self._settings.max_pending_ingestions:
            raise IngestionQueueFullError(pending, self._settings.max_pending_ingestions)

        job = self._jobs.create_ingestion_job(
            IngestionJob(
                filename=filename,
                organization_id=resolved_organization_id,
                submitter=submitter,
                supersedes_document_id=supersedes_document_id,
            )
        )
        _logger.info("ingestion job queued id=%s filename=%s", job.id, filename)
        self._executor.submit(
            self._run,
            job.id,
            filename,
            content,
            submitter,
            supersedes_document_id,
            resolved_organization_id,
        )
        return job

    def _run(
        self,
        job_id: str,
        filename: str,
        content: bytes,
        submitter: str | None,
        supersedes_document_id: str | None,
        organization_id: str,
    ) -> None:
        """Execute one job. Never raises.

        This runs on a worker thread, where an escaping exception would
        be swallowed into a Future nobody reads -- leaving the job row
        stuck on RUNNING forever, which is exactly the invisible-failure
        mode async ingestion is meant to remove. Every outcome therefore
        has to land in the database before this returns.
        """
        self._jobs.mark_ingestion_job_running(job_id)
        try:
            result = self._ingestion.ingest(
                filename=filename,
                content=content,
                submitter=submitter,
                supersedes_document_id=supersedes_document_id,
                organization_id=organization_id,
            )
        except UnsupportedDocumentError as exc:
            # Expected outcome (scanned-and-unreadable, empty, encoding
            # failure), not a server fault -- the same distinction the
            # synchronous endpoint draws by returning 422 rather than 500.
            self._fail(
                job_id,
                IngestionJobFailure.UNSUPPORTED_DOCUMENT,
                f"The document could not be used ({exc.status.value}).",
                warnings=exc.warnings,
            )
        except UnknownSupersededDocumentError as exc:
            self._fail(job_id, IngestionJobFailure.UNKNOWN_SUPERSEDED_DOCUMENT, str(exc))
        except ValueError as exc:
            # ingest() raises ValueError for exactly one thing: the
            # upload size ceiling. submit() already checked that, so
            # reaching here means the limit changed between queueing and
            # running. Categorised accurately rather than as an internal
            # error, which would misdirect whoever reads the job.
            self._fail(job_id, IngestionJobFailure.TOO_LARGE, str(exc))
        except Exception as exc:  # noqa: BLE001 - the worker must not leak
            _logger.exception("ingestion job failed unexpectedly id=%s", job_id)
            self._fail(
                job_id,
                IngestionJobFailure.INTERNAL_ERROR,
                f"Ingestion failed unexpectedly: {type(exc).__name__}.",
            )
        else:
            self._jobs.complete_ingestion_job(
                job_id,
                document_id=result.document_id,
                chunk_count=result.chunk_count,
                parse_status=result.parse_status.value,
                parser_version=result.parser_version,
                embedding_backend=result.embedding_backend,
                parse_warnings=list(result.parse_warnings),
            )
            _logger.info(
                "ingestion job succeeded id=%s document_id=%s chunk_count=%d",
                job_id,
                result.document_id,
                result.chunk_count,
            )
        finally:
            # Retention runs here rather than on a timer because this
            # process has no scheduler and adding one for a table this
            # small would be the larger change (ADR-0064). Every branch
            # above has already persisted its outcome, so a sweep that
            # throws cannot cost this job its result -- and it is
            # swallowed anyway, because failing an ingestion the user
            # was waiting on to report a housekeeping problem would be
            # the wrong trade.
            self._sweep_expired_quietly()

    def _sweep_expired_quietly(self) -> None:
        try:
            self.sweep_expired()
        except Exception:  # noqa: BLE001 - housekeeping must not fail a job
            _logger.exception("ingestion job retention sweep failed")

    def _fail(
        self,
        job_id: str,
        category: IngestionJobFailure,
        message: str,
        warnings: list[str] | None = None,
    ) -> None:
        _logger.warning("ingestion job failed id=%s category=%s", job_id, category.value)
        self._jobs.fail_ingestion_job(
            job_id, category=category, message=message, parse_warnings=warnings
        )

    # ---- Query side ----------------------------------------------------

    def resolve_organization_id(self, organization_id: str | None = None) -> str:
        return self._ingestion.resolve_organization_id(organization_id)

    def get(self, job_id: str) -> IngestionJob | None:
        return self._jobs.get_ingestion_job(job_id)

    def list(self, organization_id: str, limit: int = 50) -> list[IngestionJob]:
        """Scoped: "Recent uploads" is a list a person reads, and one
        client's filenames are not another's to see (ADR-0063)."""
        return self._jobs.list_ingestion_jobs(limit=limit, organization_id=organization_id)

    def sweep_expired(self) -> int:
        """Delete terminal jobs past the retention window (ADR-0064).

        ADR-0059 left `ingestionjob` growing without bound and said so
        (R-35) rather than inventing a rule for it. The rule this
        implements is argued in ADR-0064 rather than picked: a job row
        is needed while the browser polls it, and afterwards only to
        answer "what happened to that upload?" -- a question whose
        horizon is weeks, because the outcome is visible in the document
        list either way.

        A retention window of 0 disables the sweep entirely. An operator
        reconstructing a full upload history should not have to patch
        code to stop rows being deleted, and a policy with no way to
        turn it off is a worse default than one with an escape hatch.
        """
        retention_days = self._settings.ingestion_job_retention_days
        if retention_days <= 0:
            return 0
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        swept = self._jobs.delete_expired_ingestion_jobs(cutoff)
        if swept:
            _logger.info(
                "swept %d terminal ingestion job(s) finished before %s (retention %d days)",
                swept,
                cutoff.isoformat(),
                retention_days,
            )
        return swept

    def sweep_interrupted(self) -> int:
        """Fail anything a previous process left mid-flight. See
        AssessmentRepository.fail_interrupted_ingestion_jobs."""
        swept = self._jobs.fail_interrupted_ingestion_jobs()
        if swept:
            _logger.warning("failed %d ingestion job(s) interrupted by a restart", swept)
        return swept
