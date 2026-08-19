"""Retention for the ingestion-job table, at the service layer
(ADR-0064).

The repository owns the predicate -- which rows are eligible -- and is
tested directly in
repositories/tests/test_assessment_repository_job_retention.py. This
file is about the two things the service adds on top: turning a
configured window into a cutoff, and running the sweep at the two
moments ADR-0064 chose (startup, and after each job finishes) without
ever letting housekeeping cost a user their upload.

The executor is inline, so "after each job finishes" is a fact these
tests can assert rather than wait for.
"""

from __future__ import annotations

from concurrent.futures import Future
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from compliance_platform.core.config import Settings
from compliance_platform.models.assessment import (
    DEFAULT_ORGANIZATION_ID,
    IngestionJob,
    IngestionJobStatus,
)
from compliance_platform.models.schemas import IngestionResult, ParseStatus
from compliance_platform.repositories.assessment_repository import AssessmentRepository
from compliance_platform.services.ingestion_job_service import IngestionJobService
from compliance_platform.services.ingestion_service import UnsupportedDocumentError


class _InlineExecutor:
    def submit(self, fn: Any, /, *args: Any, **kwargs: Any) -> Future:
        future: Future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as exc:  # pragma: no cover - the worker must not raise
            future.set_exception(exc)
        return future


class _StubIngestion:
    def __init__(self, raises: Exception | None = None) -> None:
        self._raises = raises

    def resolve_organization_id(self, organization_id: str | None = None) -> str:
        return organization_id or DEFAULT_ORGANIZATION_ID

    def ingest(self, **kwargs: Any) -> IngestionResult:
        if self._raises is not None:
            raise self._raises
        return IngestionResult(
            document_id="doc-1",
            filename="policy.pdf",
            parse_status=ParseStatus.SUCCESS,
            parse_warnings=[],
            chunk_count=7,
            embedding_backend="fake",
            parser_version="pypdf==1.2.3",
        )


class _ExplodingSweepRepository:
    """The real repository with one method sabotaged.

    Everything else has to keep working, because the assertion is that
    the *ingestion* still succeeds while retention is broken -- a stub
    that failed at everything would prove nothing about which of the two
    the failure came from.
    """

    def __init__(self, inner: AssessmentRepository) -> None:
        self._inner = inner
        self.attempts = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def delete_expired_ingestion_jobs(self, cutoff: datetime) -> int:
        self.attempts += 1
        raise RuntimeError("database is locked")


def _make(
    tmp_path: Path,
    ingestion: _StubIngestion | None = None,
    repository: Any = None,
    **settings_overrides: Any,
) -> tuple[IngestionJobService, AssessmentRepository]:
    settings = Settings(assessments_db_path=tmp_path / "a.db", **settings_overrides)  # type: ignore[arg-type]
    repo = AssessmentRepository(settings.assessments_db_path)
    service = IngestionJobService(
        settings=settings,
        ingestion_service=ingestion or _StubIngestion(),  # type: ignore[arg-type]
        job_repository=repository if repository is not None else repo,  # type: ignore[arg-type]
        executor=_InlineExecutor(),
    )
    return service, repo


def _terminal_job(
    repo: AssessmentRepository,
    *,
    finished_days_ago: float,
    status: IngestionJobStatus = IngestionJobStatus.SUCCEEDED,
) -> IngestionJob:
    now = datetime.now(UTC)
    return repo.create_ingestion_job(
        IngestionJob(
            filename="old.pdf",
            organization_id=DEFAULT_ORGANIZATION_ID,
            status=status,
            created_at=now - timedelta(days=finished_days_ago + 1),
            finished_at=now - timedelta(days=finished_days_ago),
        )
    )


def test_sweep_expired_deletes_past_the_configured_window(tmp_path: Path) -> None:
    service, repo = _make(tmp_path, ingestion_job_retention_days=30)
    stale = _terminal_job(repo, finished_days_ago=31)
    fresh = _terminal_job(repo, finished_days_ago=29)

    assert service.sweep_expired() == 1
    assert repo.get_ingestion_job(stale.id) is None
    assert repo.get_ingestion_job(fresh.id) is not None


def test_the_window_is_configurable_rather_than_baked_in(tmp_path: Path) -> None:
    """The number is a default with reasoning behind it (ADR-0064), not
    a constant. A deployment that keeps uploads for a quarter should get
    that by configuration."""
    service, repo = _make(tmp_path, ingestion_job_retention_days=90)
    sixty_days_old = _terminal_job(repo, finished_days_ago=60)

    assert service.sweep_expired() == 0
    assert repo.get_ingestion_job(sixty_days_old.id) is not None


def test_zero_disables_the_sweep_entirely(tmp_path: Path) -> None:
    """The escape hatch. An operator reconstructing a full upload
    history should not have to patch code to stop rows disappearing."""
    service, repo = _make(tmp_path, ingestion_job_retention_days=0)
    ancient = _terminal_job(repo, finished_days_ago=3650)

    assert service.sweep_expired() == 0
    assert repo.get_ingestion_job(ancient.id) is not None


def test_a_finished_job_triggers_the_sweep(tmp_path: Path) -> None:
    """Without this, a process that never restarts never sweeps, and the
    table grows exactly as R-35 describes on the deployment most likely
    to have the problem."""
    service, repo = _make(tmp_path, ingestion_job_retention_days=30)
    stale = _terminal_job(repo, finished_days_ago=45)

    service.submit(filename="new.pdf", content=b"data")

    assert repo.get_ingestion_job(stale.id) is None


def test_a_failed_job_triggers_the_sweep_too(tmp_path: Path) -> None:
    """Retention follows the job ending, not the job succeeding. An
    instance failing every upload is one that still accumulates rows."""
    service, repo = _make(
        tmp_path,
        ingestion=_StubIngestion(
            raises=UnsupportedDocumentError(status=ParseStatus.EMPTY, warnings=[])
        ),
        ingestion_job_retention_days=30,
    )
    stale = _terminal_job(repo, finished_days_ago=45)

    job = service.submit(filename="broken.pdf", content=b"data")

    assert service.get(job.id).status == IngestionJobStatus.FAILED  # type: ignore[union-attr]
    assert repo.get_ingestion_job(stale.id) is None


def test_the_job_that_triggers_a_sweep_is_never_swept_by_it(tmp_path: Path) -> None:
    """It finished a millisecond ago, so it cannot be past any window --
    but the sweep runs inside the same call, and an off-by-one on the
    comparison would delete the row the caller is about to poll."""
    service, repo = _make(tmp_path, ingestion_job_retention_days=30)

    job = service.submit(filename="new.pdf", content=b"data")

    survivor = repo.get_ingestion_job(job.id)
    assert survivor is not None
    assert survivor.status == IngestionJobStatus.SUCCEEDED


def test_a_broken_sweep_does_not_cost_the_upload(tmp_path: Path) -> None:
    """Housekeeping fails closed, not loudly. The user was waiting on an
    ingestion; failing it to report that a cleanup did not run would be
    the wrong trade, and the job row is already persisted by then."""
    _, repo = _make(tmp_path)
    sabotaged = _ExplodingSweepRepository(repo)
    service, _ = _make(tmp_path, repository=sabotaged, ingestion_job_retention_days=30)

    job = service.submit(filename="new.pdf", content=b"data")

    finished = repo.get_ingestion_job(job.id)
    assert finished is not None
    assert finished.status == IngestionJobStatus.SUCCEEDED
    assert finished.document_id == "doc-1"
    assert sabotaged.attempts == 1


def test_a_job_interrupted_long_ago_survives_its_first_startup(tmp_path: Path) -> None:
    """The ordering guarantee in main.py's lifespan, asserted rather
    than left to the comment explaining it.

    A job stranded on RUNNING a year ago is converted to FAILED by
    sweep_interrupted, which stamps finished_at with now. Running
    retention afterwards must therefore leave it alone: an operator
    coming back to a crashed instance gets to read what happened,
    instead of the two sweeps combining to delete the evidence in the
    same second.
    """
    service, repo = _make(tmp_path, ingestion_job_retention_days=30)
    stranded = repo.create_ingestion_job(
        IngestionJob(
            filename="stranded.pdf",
            organization_id=DEFAULT_ORGANIZATION_ID,
            status=IngestionJobStatus.RUNNING,
            created_at=datetime.now(UTC) - timedelta(days=365),
        )
    )

    assert service.sweep_interrupted() == 1
    assert service.sweep_expired() == 0

    survivor = repo.get_ingestion_job(stranded.id)
    assert survivor is not None
    assert survivor.status == IngestionJobStatus.FAILED
