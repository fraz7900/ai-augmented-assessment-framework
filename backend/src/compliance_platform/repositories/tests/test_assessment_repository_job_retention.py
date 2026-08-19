"""The ingestion-job retention sweep, at the layer that does the
deleting (ADR-0064).

ADR-0059 disclosed that `ingestionjob` rows accumulate with no bound
(R-35) rather than solving it. This is the sweep that closes that half,
and it is the only code in this repository that deletes a row nobody
asked to delete -- so the tests that matter are the ones proving what it
does *not* touch. A sweep that removes live work is worse than a table
that grows: growth is a disk-space problem with a visible cause, while a
deleted QUEUED row is an upload that silently never happens and cannot
be distinguished afterwards from one that was never submitted.

Every test here calls the repository directly. The service computes the
cutoff from settings and is tested separately; this file is about the
predicate.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from compliance_platform.models.assessment import (
    DEFAULT_ORGANIZATION_ID,
    IngestionJob,
    IngestionJobFailure,
    IngestionJobStatus,
)
from compliance_platform.repositories.assessment_repository import AssessmentRepository

_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)


def _repo(tmp_path: Path) -> AssessmentRepository:
    return AssessmentRepository(tmp_path / "assessments.db")


def _job(
    repo: AssessmentRepository,
    *,
    status: IngestionJobStatus,
    finished_ago_days: float | None,
    created_ago_days: float = 400.0,
    filename: str = "policy.pdf",
) -> IngestionJob:
    """Create one job row in a given terminal/live state and age.

    created_at is deliberately ancient by default so no test can pass by
    accident through the sweep reading the wrong column: a live job
    created a year ago must still survive, and a terminal job that
    finished this morning must survive despite being created a year ago.
    """
    job = repo.create_ingestion_job(
        IngestionJob(
            filename=filename,
            organization_id=DEFAULT_ORGANIZATION_ID,
            status=status,
            created_at=_NOW - timedelta(days=created_ago_days),
            finished_at=(
                None if finished_ago_days is None else _NOW - timedelta(days=finished_ago_days)
            ),
            failure_category=(
                IngestionJobFailure.INTERNAL_ERROR
                if status is IngestionJobStatus.FAILED
                else None
            ),
        )
    )
    return job


def _cutoff(days: int) -> datetime:
    return _NOW - timedelta(days=days)


def test_sweeps_terminal_jobs_older_than_the_cutoff(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    succeeded = _job(repo, status=IngestionJobStatus.SUCCEEDED, finished_ago_days=45)
    failed = _job(repo, status=IngestionJobStatus.FAILED, finished_ago_days=90)

    swept = repo.delete_expired_ingestion_jobs(_cutoff(30))

    assert swept == 2
    assert repo.get_ingestion_job(succeeded.id) is None
    assert repo.get_ingestion_job(failed.id) is None


def test_keeps_terminal_jobs_inside_the_window(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    recent = _job(repo, status=IngestionJobStatus.SUCCEEDED, finished_ago_days=29)

    assert repo.delete_expired_ingestion_jobs(_cutoff(30)) == 0
    assert repo.get_ingestion_job(recent.id) is not None


def test_never_sweeps_queued_or_running_however_old(tmp_path: Path) -> None:
    """The guarantee this sweep exists to not break.

    Both rows are a year old by created_at and carry no finished_at,
    which is exactly what a job stuck since last year looks like. A
    stuck row is a bug for `fail_interrupted_ingestion_jobs` to convert
    into a FAILED one at the next restart -- at which point retention
    starts applying to it honestly. It is not this sweep's to delete.
    """
    repo = _repo(tmp_path)
    queued = _job(repo, status=IngestionJobStatus.QUEUED, finished_ago_days=None)
    running = _job(repo, status=IngestionJobStatus.RUNNING, finished_ago_days=None)

    assert repo.delete_expired_ingestion_jobs(_cutoff(30)) == 0
    assert repo.get_ingestion_job(queued.id) is not None
    assert repo.get_ingestion_job(running.id) is not None


def test_never_sweeps_a_terminal_job_that_carries_no_finished_at(tmp_path: Path) -> None:
    """A row we cannot date is kept, not guessed at.

    Nothing in the current code produces a terminal job with a null
    finished_at -- every transition sets it. Falling back to created_at
    would make the sweep delete on a timestamp that means something
    else, so an undateable row survives instead. Keeping a row too long
    is recoverable; deleting one early is not.
    """
    repo = _repo(tmp_path)
    undateable = _job(repo, status=IngestionJobStatus.SUCCEEDED, finished_ago_days=None)

    assert repo.delete_expired_ingestion_jobs(_cutoff(30)) == 0
    assert repo.get_ingestion_job(undateable.id) is not None


def test_sweeps_across_organizations(tmp_path: Path) -> None:
    """Retention is an instance-wide storage policy, not a per-client
    view, and so is deliberately unscoped -- the same reasoning
    ADR-0063 used to leave the backpressure count instance-wide. Scoping
    a sweep to one organisation would leave every other organisation's
    rows accumulating exactly as before.
    """
    repo = _repo(tmp_path)
    other = repo.create_organization("Second Client")
    mine = _job(repo, status=IngestionJobStatus.SUCCEEDED, finished_ago_days=60)
    theirs = repo.create_ingestion_job(
        IngestionJob(
            filename="theirs.pdf",
            organization_id=other.id,
            status=IngestionJobStatus.SUCCEEDED,
            created_at=_NOW - timedelta(days=400),
            finished_at=_NOW - timedelta(days=60),
        )
    )

    assert repo.delete_expired_ingestion_jobs(_cutoff(30)) == 2
    assert repo.get_ingestion_job(mine.id) is None
    assert repo.get_ingestion_job(theirs.id) is None


def test_returns_zero_and_changes_nothing_on_an_empty_table(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert repo.delete_expired_ingestion_jobs(_cutoff(30)) == 0


def test_sweep_leaves_the_document_the_job_produced(tmp_path: Path) -> None:
    """Deleting the job must not touch what it ingested.

    The job row records that an upload happened; the Document is the
    upload. Sweeping the first is a retention decision about
    operational noise, and losing the second would be data loss --
    there is no foreign key from document to job precisely so that this
    stays true, and this test is what stops a future cascade from being
    added without noticing.
    """
    from compliance_platform.models.assessment import Document

    repo = _repo(tmp_path)
    document = repo.create_document(
        Document(
            id="doc-1",
            organization_id=DEFAULT_ORGANIZATION_ID,
            filename="policy.pdf",
            file_type="pdf",
            content_hash="hash-1",
        )
    )
    job = repo.create_ingestion_job(
        IngestionJob(
            filename="policy.pdf",
            organization_id=DEFAULT_ORGANIZATION_ID,
            status=IngestionJobStatus.SUCCEEDED,
            created_at=_NOW - timedelta(days=400),
            finished_at=_NOW - timedelta(days=60),
            document_id=document.id,
        )
    )

    assert repo.delete_expired_ingestion_jobs(_cutoff(30)) == 1
    assert repo.get_ingestion_job(job.id) is None
    assert repo.get_document(document.id) is not None
