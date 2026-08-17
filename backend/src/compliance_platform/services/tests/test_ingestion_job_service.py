"""Unit tests for asynchronous ingestion.

The executor is injected as an inline one that runs the job on the
calling thread, so every assertion here is about a finished job rather
than about a race. Testing a thread pool by sleeping and hoping would
make the suite both slower and flaky, and would not test anything these
tests care about -- the mapping from ingestion outcomes to job state.

Real thread-safety of the underlying repository is verified separately
(and was verified directly before this feature was built, the same way
ADR-0037 verified the vector store's read path under concurrent load).
"""

from __future__ import annotations

from concurrent.futures import Future
from pathlib import Path
from typing import Any

import pytest

from compliance_platform.core.config import Settings
from compliance_platform.models.assessment import (
    IngestionJob,
    IngestionJobFailure,
    IngestionJobStatus,
)
from compliance_platform.models.schemas import IngestionResult, ParseStatus
from compliance_platform.repositories.assessment_repository import AssessmentRepository
from compliance_platform.services.ingestion_job_service import (
    IngestionJobService,
    IngestionQueueFullError,
)
from compliance_platform.services.ingestion_service import (
    UnknownSupersededDocumentError,
    UnsupportedDocumentError,
)


class _InlineExecutor:
    """Runs the submitted callable immediately, on this thread."""

    def submit(self, fn: Any, /, *args: Any, **kwargs: Any) -> Future:
        future: Future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as exc:  # pragma: no cover - the worker must not raise
            future.set_exception(exc)
        return future


class _NeverRunExecutor:
    """Accepts work and never runs it, so a job stays QUEUED."""

    def __init__(self) -> None:
        self.submitted: list[tuple] = []

    def submit(self, fn: Any, /, *args: Any, **kwargs: Any) -> Future:
        self.submitted.append((fn, args, kwargs))
        return Future()


class _StubIngestion:
    """Stands in for IngestionService, which this service only ever
    calls one method on. Using a stub rather than the real service keeps
    each test pinned to one outcome -- the point here is the mapping
    from that outcome to job state, not re-testing ingestion itself."""

    def __init__(self, result: IngestionResult | None = None, raises: Exception | None = None):
        self._result = result
        self._raises = raises
        self.calls: list[dict] = []

    def ingest(
        self,
        filename: str,
        content: bytes,
        submitter: str | None = None,
        supersedes_document_id: str | None = None,
    ) -> IngestionResult:
        self.calls.append(
            {
                "filename": filename,
                "content": content,
                "submitter": submitter,
                "supersedes_document_id": supersedes_document_id,
            }
        )
        if self._raises is not None:
            raise self._raises
        assert self._result is not None
        return self._result


def _result(**overrides: Any) -> IngestionResult:
    defaults: dict[str, Any] = {
        "document_id": "doc-1",
        "filename": "policy.pdf",
        "parse_status": ParseStatus.SUCCESS,
        "parse_warnings": [],
        "chunk_count": 7,
        "embedding_backend": "fake",
        "parser_version": "pypdf==1.2.3",
    }
    defaults.update(overrides)
    return IngestionResult(**defaults)


def _make(
    tmp_path: Path,
    ingestion: _StubIngestion | None = None,
    executor: Any = None,
    **settings_overrides: Any,
) -> tuple[IngestionJobService, AssessmentRepository]:
    settings = Settings(assessments_db_path=tmp_path / "a.db", **settings_overrides)  # type: ignore[arg-type]
    repo = AssessmentRepository(settings.assessments_db_path)
    service = IngestionJobService(
        settings=settings,
        ingestion_service=ingestion or _StubIngestion(result=_result()),  # type: ignore[arg-type]
        job_repository=repo,
        executor=executor or _InlineExecutor(),
    )
    return service, repo


def test_submit_records_a_queued_job_before_any_work_happens(tmp_path: Path) -> None:
    """The whole point of the endpoint: the caller gets an id back
    without waiting for the parse."""
    executor = _NeverRunExecutor()
    service, _ = _make(tmp_path, executor=executor)

    job = service.submit(filename="policy.pdf", content=b"x" * 100, submitter="assessor")

    assert job.status == IngestionJobStatus.QUEUED
    assert job.filename == "policy.pdf"
    assert job.submitter == "assessor"
    assert job.document_id is None
    assert len(executor.submitted) == 1


def test_successful_ingestion_records_the_result_on_the_job(tmp_path: Path) -> None:
    ingestion = _StubIngestion(
        result=_result(document_id="doc-42", chunk_count=31, parse_warnings=["ocr approximate"])
    )
    service, _ = _make(tmp_path, ingestion=ingestion)

    job = service.submit(filename="scan.pdf", content=b"data")
    finished = service.get(job.id)

    assert finished is not None
    assert finished.status == IngestionJobStatus.SUCCEEDED
    assert finished.document_id == "doc-42"
    assert finished.chunk_count == 31
    assert finished.parser_version == "pypdf==1.2.3"
    assert finished.embedding_backend == "fake"
    assert finished.started_at is not None
    assert finished.finished_at is not None
    assert finished.failure_category is None


def test_parse_warnings_survive_the_round_trip_through_storage(tmp_path: Path) -> None:
    """Warnings are stored as JSON text (no JSON column convention in
    this schema), so the encode/decode is worth pinning -- an OCR
    warning that silently vanished would remove the one signal telling a
    reviewer the text is approximate."""
    ingestion = _StubIngestion(
        result=_result(parse_warnings=["text recovered by local OCR", "page 3 was blank"])
    )
    service, _ = _make(tmp_path, ingestion=ingestion)

    job = service.submit(filename="scan.pdf", content=b"data")

    from compliance_platform.models.schemas import IngestionJobView

    view = IngestionJobView.from_job(service.get(job.id))  # type: ignore[arg-type]
    assert view.parse_warnings == ["text recovered by local OCR", "page 3 was blank"]


def test_unsupported_document_is_a_categorised_failure_not_a_crash(tmp_path: Path) -> None:
    ingestion = _StubIngestion(
        raises=UnsupportedDocumentError(ParseStatus.EMPTY, ["no extractable text"])
    )
    service, _ = _make(tmp_path, ingestion=ingestion)

    job = service.submit(filename="blank.pdf", content=b"data")
    finished = service.get(job.id)

    assert finished is not None
    assert finished.status == IngestionJobStatus.FAILED
    assert finished.failure_category == IngestionJobFailure.UNSUPPORTED_DOCUMENT
    assert finished.document_id is None


def test_unsupported_document_keeps_the_parser_warnings(tmp_path: Path) -> None:
    """Why it was rejected is the actionable part -- without the
    warnings, "unsupported" tells an uploader nothing they can act on."""
    ingestion = _StubIngestion(
        raises=UnsupportedDocumentError(ParseStatus.FAILED, ["encrypted PDF, no password supplied"])
    )
    service, _ = _make(tmp_path, ingestion=ingestion)

    job = service.submit(filename="locked.pdf", content=b"data")

    from compliance_platform.models.schemas import IngestionJobView

    view = IngestionJobView.from_job(service.get(job.id))  # type: ignore[arg-type]
    assert view.parse_warnings == ["encrypted PDF, no password supplied"]


def test_unknown_superseded_document_has_its_own_category(tmp_path: Path) -> None:
    ingestion = _StubIngestion(raises=UnknownSupersededDocumentError("ghost-id"))
    service, _ = _make(tmp_path, ingestion=ingestion)

    job = service.submit(
        filename="v2.pdf", content=b"data", supersedes_document_id="ghost-id"
    )
    finished = service.get(job.id)

    assert finished is not None
    assert finished.failure_category == IngestionJobFailure.UNKNOWN_SUPERSEDED_DOCUMENT


def test_an_unexpected_error_fails_the_job_instead_of_escaping_the_worker(
    tmp_path: Path,
) -> None:
    """The failure mode async ingestion exists to remove. An exception
    escaping into a Future nobody reads would leave the row on RUNNING
    forever -- invisible, and indistinguishable from slow."""
    ingestion = _StubIngestion(raises=RuntimeError("lancedb exploded"))
    service, _ = _make(tmp_path, ingestion=ingestion)

    job = service.submit(filename="policy.pdf", content=b"data")
    finished = service.get(job.id)

    assert finished is not None
    assert finished.status == IngestionJobStatus.FAILED
    assert finished.failure_category == IngestionJobFailure.INTERNAL_ERROR
    assert finished.finished_at is not None
    # The message names the type without leaking the raw exception text
    # into an API response.
    assert "RuntimeError" in (finished.failure_message or "")
    assert "lancedb exploded" not in (finished.failure_message or "")


def test_oversized_upload_is_refused_immediately_and_creates_no_job(tmp_path: Path) -> None:
    """An immediate error beats a job row here: there is nothing to poll
    for and nothing a retry would change."""
    service, _ = _make(tmp_path, max_upload_bytes=10)

    with pytest.raises(ValueError, match="maximum upload size"):
        service.submit(filename="big.pdf", content=b"x" * 11)

    assert service.list() == []


def test_queue_depth_is_bounded(tmp_path: Path) -> None:
    """A queued job holds its bytes in memory until a worker frees up.
    The synchronous endpoint bounded that by making the caller wait;
    accepting uploads immediately removes that bound unless it is put
    back deliberately."""
    executor = _NeverRunExecutor()
    service, _ = _make(tmp_path, executor=executor, max_pending_ingestions=2)

    service.submit(filename="a.pdf", content=b"a")
    service.submit(filename="b.pdf", content=b"b")

    with pytest.raises(IngestionQueueFullError) as excinfo:
        service.submit(filename="c.pdf", content=b"c")

    assert excinfo.value.limit == 2
    assert len(service.list()) == 2


def test_finished_jobs_do_not_count_against_the_queue_limit(tmp_path: Path) -> None:
    service, _ = _make(tmp_path, max_pending_ingestions=1)

    service.submit(filename="a.pdf", content=b"a")  # runs inline, succeeds
    # Would raise if a SUCCEEDED job still occupied the queue.
    second = service.submit(filename="b.pdf", content=b"b")

    assert second.status == IngestionJobStatus.QUEUED


def test_sweep_fails_jobs_a_restart_stranded(tmp_path: Path) -> None:
    executor = _NeverRunExecutor()
    service, repo = _make(tmp_path, executor=executor)
    queued = service.submit(filename="a.pdf", content=b"a")
    running = repo.create_ingestion_job(IngestionJob(filename="b.pdf"))
    repo.mark_ingestion_job_running(running.id)

    swept = service.sweep_interrupted()

    assert swept == 2
    for job_id in (queued.id, running.id):
        job = service.get(job_id)
        assert job is not None
        assert job.status == IngestionJobStatus.FAILED
        assert job.failure_category == IngestionJobFailure.INTERRUPTED


def test_sweep_leaves_already_finished_jobs_alone(tmp_path: Path) -> None:
    """A sweep that rewrote finished history would destroy the record it
    exists to protect."""
    service, _ = _make(tmp_path)
    done = service.submit(filename="a.pdf", content=b"a")  # succeeds inline

    assert service.sweep_interrupted() == 0

    job = service.get(done.id)
    assert job is not None
    assert job.status == IngestionJobStatus.SUCCEEDED
    assert job.failure_category is None


def test_submitted_arguments_reach_ingestion_unchanged(tmp_path: Path) -> None:
    """The job layer must not quietly drop supersedes_document_id --
    ADR-0039's versioning link is human-declared and unrecoverable if
    lost in transit."""
    ingestion = _StubIngestion(result=_result())
    service, _ = _make(tmp_path, ingestion=ingestion)

    service.submit(
        filename="v2.pdf",
        content=b"bytes",
        submitter="assessor",
        supersedes_document_id="doc-old",
    )

    assert ingestion.calls == [
        {
            "filename": "v2.pdf",
            "content": b"bytes",
            "submitter": "assessor",
            "supersedes_document_id": "doc-old",
        }
    ]
