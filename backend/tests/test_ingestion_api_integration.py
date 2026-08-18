"""End-to-end integration test: upload a document through the real
FastAPI app and confirm it comes out the other end ingested and
embedded, exercising the real parser, chunker, embedder, and LanceDB
vector store together rather than fakes. See
docs/architecture/00-repository-architecture.md's testing strategy and
tests/README.md.
"""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import Future
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from compliance_platform.api import dependencies
from compliance_platform.core.config import Settings
from compliance_platform.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    test_settings = Settings(
        vector_store_dir=tmp_path / "lancedb",
        # Document versioning (ADR-0039) wired IngestionService to
        # AssessmentRepository -- without also isolating
        # assessments_db_path/get_cached_assessment_repository here, an
        # uncleared cache would resolve to Settings' default path and
        # write real Document rows into the live project database this
        # test suite is never supposed to touch. Confirmed as a real,
        # not hypothetical, risk before this fix landed.
        assessments_db_path=tmp_path / "assessments.db",
        # The SAME failure mode recurred with a different path when
        # ADR-0056 made ingestion retain uploads: nothing redirected
        # data_raw_dir, because until then nothing wrote there, and a
        # full test run left 45 files in the real data/raw/. Both the
        # pattern and its fix are now enforced suite-wide by
        # conftest.py's isolate_retained_uploads, so a future writable
        # path cannot repeat this a third time by omission alone.
        data_raw_dir=tmp_path / "raw",
    )

    # get_cached_embedder is deliberately NOT cleared per-test (Sprint
    # 9, R-13) — see the matching comment in
    # tests/test_assessment_api_integration.py for why reusing it across
    # the whole test session is both safe and measurably faster.
    dependencies.get_cached_settings.cache_clear()
    dependencies.get_cached_vector_repository.cache_clear()
    dependencies.get_cached_assessment_repository.cache_clear()
    monkeypatch.setattr(dependencies, "get_settings", lambda: test_settings)

    with TestClient(app) as test_client:
        yield test_client

    dependencies.get_cached_settings.cache_clear()
    dependencies.get_cached_vector_repository.cache_clear()
    dependencies.get_cached_assessment_repository.cache_clear()


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ingest_text_document_end_to_end(client: TestClient) -> None:
    content = b"Multi factor authentication is required for all remote access to critical systems."
    response = client.post(
        "/ingest",
        files={"file": ("policy.txt", content, "text/plain")},
        data={"submitter": "test-suite"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["parse_status"] == "success"
    assert body["chunk_count"] >= 1
    # Default backend as of ADR-0008; hashing_local remains selectable
    # (see ai/tests/test_embeddings.py) but is no longer the default.
    assert body["embedding_backend"] == "semantic_local_onnx"


def test_ingest_markdown_document_uses_structure_aware_chunking(client: TestClient) -> None:
    # Each section body must clear the default chunk_min_chars (40) or the
    # ingestion service correctly rejects the document as EMPTY — this is
    # exercising that real threshold, not an arbitrary short string.
    content = (
        b"# Access Control\n"
        b"Multi factor authentication is required for all remote access to critical systems.\n"
        b"# Incident Response\n"
        b"Incidents are triaged within fifteen minutes during business hours by the SOC.\n"
    )
    response = client.post(
        "/ingest",
        files={"file": ("policy.md", content, "text/markdown")},
    )
    assert response.status_code == 200
    assert response.json()["chunk_count"] == 2


def test_ingest_xlsx_document_end_to_end(client: TestClient, sample_xlsx_bytes: bytes) -> None:
    response = client.post(
        "/ingest",
        files={
            "file": (
                "inventory.xlsx",
                sample_xlsx_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["parse_status"] == "success"
    assert body["chunk_count"] >= 1


def test_ingest_csv_document_end_to_end(client: TestClient, sample_csv_bytes: bytes) -> None:
    response = client.post(
        "/ingest",
        files={"file": ("inventory.csv", sample_csv_bytes, "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["parse_status"] == "success"
    assert body["chunk_count"] >= 1


def test_ingest_scanned_pdf_returns_422(client: TestClient, scanned_like_pdf_bytes: bytes) -> None:
    response = client.post(
        "/ingest",
        files={"file": ("scanned.pdf", scanned_like_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["status"] == "unsupported_scanned"


def test_ingest_unsupported_extension_returns_400(client: TestClient) -> None:
    response = client.post(
        "/ingest",
        files={"file": ("archive.zip", b"PK\x03\x04", "application/zip")},
    )
    assert response.status_code == 400


def test_two_independent_ingestions_are_retrievable_from_the_same_store(
    client: TestClient, tmp_path: Path
) -> None:
    """Regression guard for the exact failure mode ADR-0006 was written to
    avoid: two documents ingested via separate API calls must both land
    in the same, queryable vector store with comparable embeddings.
    """
    for name, text in [
        ("doc_a.txt", b"Access control requires multi factor authentication."),
        ("doc_b.txt", b"Incident response plans are tested twice annually."),
    ]:
        response = client.post("/ingest", files={"file": (name, text, "text/plain")})
        assert response.status_code == 200

    repo = dependencies.get_cached_vector_repository()
    assert repo.count() >= 2


# --- Document versioning (Sprint 18, ADR-0039) ---


def test_ingested_document_is_retrievable_via_documents_endpoint(client: TestClient) -> None:
    response = client.post(
        "/ingest",
        files={"file": ("policy.txt", b"Multi factor authentication is required.", "text/plain")},
        data={"submitter": "test-suite"},
    )
    document_id = response.json()["document_id"]

    detail = client.get(f"/documents/{document_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["filename"] == "policy.txt"
    assert body["submitter"] == "test-suite"
    assert body["supersedes_document_id"] is None
    assert body["superseded_by_document_id"] is None
    assert body["parser_version"].startswith("compliance_platform.document_parsers==")


def test_unknown_document_returns_404(client: TestClient) -> None:
    assert client.get("/documents/does-not-exist").status_code == 404


def test_supersedes_relationship_is_recorded_and_visible_both_directions(
    client: TestClient,
) -> None:
    v1 = client.post(
        "/ingest",
        files={
            "file": ("policy_v1.txt", b"Passwords must be at least eight characters.", "text/plain")
        },
    ).json()["document_id"]

    v2 = client.post(
        "/ingest",
        files={
            "file": (
                "policy_v2.txt",
                b"Passwords must be at least twelve characters.",
                "text/plain",
            )
        },
        data={"supersedes_document_id": v1},
    ).json()["document_id"]

    v1_detail = client.get(f"/documents/{v1}").json()
    assert v1_detail["superseded_by_document_id"] == v2

    v2_detail = client.get(f"/documents/{v2}").json()
    assert v2_detail["supersedes_document_id"] == v1


def test_ingest_rejects_supersedes_reference_to_unknown_document(client: TestClient) -> None:
    response = client.post(
        "/ingest",
        files={"file": ("policy.txt", b"Some real synthetic policy content here.", "text/plain")},
        data={"supersedes_document_id": "does-not-exist"},
    )
    assert response.status_code == 422


# --- page_number / parser_version provenance (Sprint 18, ADR-0042) ---


def test_ingest_reports_a_real_parser_version(client: TestClient) -> None:
    response = client.post(
        "/ingest",
        files={"file": ("policy.txt", b"Some real synthetic policy content here.", "text/plain")},
    )
    assert response.status_code == 200
    assert response.json()["parser_version"].startswith("compliance_platform.document_parsers==")


def test_multi_page_pdf_chunks_carry_a_real_page_number_end_to_end(client: TestClient) -> None:
    from fpdf import FPDF

    # Each page's own text must clear Settings.chunk_target_chars (1200
    # by default) on its own, or both pages could land in a single
    # chunk together (fixed-window chunking doesn't respect page
    # boundaries) and this test would only ever see page 1.
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 10, "Access control policy content, page one. " * 40)
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 10, "Incident response policy content, page two. " * 40)
    content = bytes(pdf.output())

    response = client.post("/ingest", files={"file": ("multi.pdf", content, "application/pdf")})
    assert response.status_code == 200
    body = response.json()
    assert body["parser_version"].startswith("pypdf==")

    repo = dependencies.get_cached_vector_repository()
    chunks = repo.chunks_for_document(body["document_id"])
    assert len(chunks) >= 2
    page_numbers = {c["page_number"] for c in chunks}
    assert page_numbers == {1, 2}  # real page provenance, not discarded before chunking


# ---- Asynchronous ingestion -----------------------------------------
#
# These use an inline executor so a poll immediately after the upload
# sees a finished job. The real deployment uses a single background
# worker; what is under test here is the endpoint contract and the job
# record, not the thread pool.


class _InlineExecutor:
    def submit(self, fn, /, *args, **kwargs):
        future: Future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as exc:  # pragma: no cover - the worker must not raise
            future.set_exception(exc)
        return future


@pytest.fixture
def async_client(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    monkeypatch.setattr(dependencies, "get_cached_ingestion_executor", _InlineExecutor)
    yield client


def test_async_ingest_returns_202_with_a_pollable_job(async_client: TestClient) -> None:
    content = b"Multi factor authentication is required for all remote access to critical systems."
    response = async_client.post(
        "/ingest/async",
        files={"file": ("policy.txt", content, "text/plain")},
        data={"submitter": "test-suite"},
    )

    assert response.status_code == 202
    job = response.json()
    assert job["filename"] == "policy.txt"
    assert job["submitter"] == "test-suite"

    polled = async_client.get(f"/ingest/jobs/{job['id']}")
    assert polled.status_code == 200
    body = polled.json()
    assert body["status"] == "succeeded"
    assert body["chunk_count"] >= 1
    assert body["parse_status"] == "success"
    assert body["embedding_backend"] == "semantic_local_onnx"
    assert body["document_id"]


def test_async_ingested_document_is_really_in_the_vector_store(
    async_client: TestClient,
) -> None:
    """A job that claims success has to mean the same thing the
    synchronous endpoint means -- chunks actually queryable, not just a
    row saying so."""
    content = b"Incidents are triaged within fifteen minutes during business hours by the SOC."
    response = async_client.post(
        "/ingest/async", files={"file": ("ir.txt", content, "text/plain")}
    )
    document_id = response.json()["id"]
    job = async_client.get(f"/ingest/jobs/{document_id}").json()

    chunks = dependencies.get_cached_vector_repository().chunks_for_document(job["document_id"])
    assert len(chunks) >= 1


def test_async_ingest_records_a_rejected_document_as_a_failed_job(
    async_client: TestClient,
) -> None:
    """The case the synchronous endpoint answers with 422. Asynchronously
    the upload itself succeeded, so the rejection has to survive on the
    job instead of in the response status."""
    response = async_client.post(
        "/ingest/async", files={"file": ("empty.txt", b"", "text/plain")}
    )
    assert response.status_code == 202

    job = async_client.get(f"/ingest/jobs/{response.json()['id']}").json()
    assert job["status"] == "failed"
    assert job["failure_category"] == "unsupported_document"
    assert job["document_id"] is None


def test_async_ingest_rejects_an_oversized_upload_immediately(
    async_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = dependencies.get_cached_settings()
    monkeypatch.setattr(settings, "max_upload_bytes", 10)

    response = async_client.post(
        "/ingest/async", files={"file": ("big.txt", b"x" * 50, "text/plain")}
    )

    assert response.status_code == 400
    assert "maximum upload size" in response.json()["detail"]
    assert async_client.get("/ingest/jobs").json() == []


def test_async_ingest_refuses_work_beyond_the_queue_limit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """429 rather than 503: the server is healthy, and waiting is the
    correct response."""

    class _NeverRunExecutor:
        def submit(self, fn, /, *args, **kwargs):
            return Future()

    monkeypatch.setattr(dependencies, "get_cached_ingestion_executor", _NeverRunExecutor)
    monkeypatch.setattr(dependencies.get_cached_settings(), "max_pending_ingestions", 1)

    first = client.post("/ingest/async", files={"file": ("a.txt", b"content here", "text/plain")})
    assert first.status_code == 202

    second = client.post("/ingest/async", files={"file": ("b.txt", b"content here", "text/plain")})
    assert second.status_code == 429


def test_polling_an_unknown_job_is_a_404(async_client: TestClient) -> None:
    assert async_client.get("/ingest/jobs/not-a-real-job").status_code == 404


def test_jobs_are_listed_newest_first(async_client: TestClient) -> None:
    for name in ("first.txt", "second.txt"):
        async_client.post(
            "/ingest/async",
            files={"file": (name, b"Access control policy content for the corpus.", "text/plain")},
        )

    listed = async_client.get("/ingest/jobs").json()
    assert [job["filename"] for job in listed] == ["second.txt", "first.txt"]


def test_the_synchronous_endpoint_still_works_unchanged(client: TestClient) -> None:
    """Async ingestion is additive. The existing endpoint is still
    correct for small documents and nothing about it was deprecated."""
    content = b"Access control policy content for the corpus."
    response = client.post(
        "/ingest",
        files={"file": ("policy.txt", content, "text/plain")},
    )
    assert response.status_code == 200
    assert response.json()["chunk_count"] >= 1
