"""OCR provenance survives the whole pipeline (ADR-0074).

The unit tests cover the resolution rule. This covers the part that was
actually broken: the information existed at parse time and was thrown
away before anything downstream could use it, so the only convincing
test runs a real scanned PDF through the real parser, chunker, vector
store and chat endpoint and reads the answer off a quotation.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from compliance_platform.api import dependencies
from compliance_platform.core.config import Settings
from compliance_platform.main import app
from compliance_platform.models.assessment import (
    EvidenceLink,
    EvidenceReviewStatus,
    EvidenceSource,
)

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _write_scanned_pdf(path: Path) -> None:
    """Build an image-only PDF at test time.

    Generated rather than committed or skipped, which is
    backend/conftest.py's own stated position: binary fixtures are
    opaque in a diff, and anything decision-relevant should be
    reproducible. Skipping was worse still -- the OCR path is the whole
    point of these tests, and a test that silently does not run in CI
    protects nothing.
    """
    spec = importlib.util.spec_from_file_location(
        "generate_sample_evidence", _SCRIPTS / "generate_sample_evidence.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module._write_scanned_pdf(path)

_CACHED = (
    dependencies.get_cached_settings,
    dependencies.get_cached_vector_repository,
    dependencies.get_cached_assessment_repository,
    dependencies.get_cached_framework_registry,
)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    settings = Settings(
        vector_store_dir=tmp_path / "lancedb",
        assessments_db_path=tmp_path / "assessments.db",
        data_raw_dir=tmp_path / "raw",
    )
    for cached in _CACHED:
        cached.cache_clear()
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)
    with TestClient(app) as test_client:
        yield test_client
    for cached in _CACHED:
        cached.cache_clear()


def _ingest_text(client: TestClient, name: str = "policy.txt") -> str:
    body = (
        b"Access Control Policy. Multi factor authentication is required for all remote "
        b"access to critical systems, and access reviews are performed quarterly by the "
        b"security team to confirm that entitlements remain appropriate."
    )
    response = client.post("/ingest", files={"file": (name, body, "text/plain")})
    assert response.status_code == 200
    return response.json()["document_id"]


def _chat(client: TestClient, assessment_id: str, question: str) -> list[dict]:
    response = client.post(f"/assessments/{assessment_id}/chat", json={"question": question})
    assert response.status_code == 200, response.text
    return response.json()["results"]


def _reviewed_assessment(client: TestClient, document_id: str) -> str:
    assessment_id = client.post(
        "/assessments", json={"name": "OCR provenance", "framework_name": "C2M2"}
    ).json()["id"]
    link = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={
            "document_id": document_id,
            "practice_reference": "ACCESS-1a",
            "chunk_id": _first_chunk_id(client, document_id),
        },
    )
    assert link.status_code == 200, link.text
    return assessment_id


def _chunks(document_id: str) -> list[dict]:
    """Straight from the vector store. Chunks are not exposed on any
    endpoint, and this test is specifically about what the store
    persisted rather than about what an API chooses to reveal."""
    return dependencies.get_cached_vector_repository().chunks_for_document(document_id)


def _first_chunk_id(client: TestClient, document_id: str) -> str:
    rows = _chunks(document_id)
    assert rows, f"no chunks stored for {document_id}"
    return rows[0]["chunk_id"]


def test_a_quotation_from_a_text_layer_is_reported_exact(client: TestClient) -> None:
    """The control case. A document that never involved OCR must not
    carry an approximation warning on its quotations."""
    document_id = _ingest_text(client)
    assessment_id = _reviewed_assessment(client, document_id)

    results = _chat(client, assessment_id, "How is remote access controlled?")

    assert results, "expected the reviewed evidence to be quoted back"
    assert {r["text_provenance"] for r in results} == {"exact"}


def test_a_quotation_recovered_by_ocr_says_so(client: TestClient, tmp_path: Path) -> None:
    """The case R-33 is about, through the real OCR path: a scanned PDF
    with no text layer at all, quoted back in chat."""
    scanned = tmp_path / "synthetic_scanned_policy.pdf"
    _write_scanned_pdf(scanned)
    with scanned.open("rb") as handle:
        response = client.post(
            "/ingest", files={"file": (scanned.name, handle, "application/pdf")}
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["parse_status"] == "success_ocr", body

    assessment_id = _reviewed_assessment(client, body["document_id"])
    results = _chat(client, assessment_id, "What does the policy require?")

    assert results, "expected the reviewed OCR evidence to be quoted back"
    assert {r["text_provenance"] for r in results} == {"ocr"}


def test_the_flag_is_stored_on_the_chunk_not_recomputed(client: TestClient) -> None:
    """Provenance has to survive the vector store, because that is where
    it was being lost. A chunk read back must carry its own answer
    rather than depending on the document being consulted again."""
    document_id = _ingest_text(client)

    rows = _chunks(document_id)

    assert rows
    # A plain text file has no pages, so per-chunk provenance genuinely
    # cannot be determined -- and the store says so rather than guessing.
    # The column exists on every row either way, which is the point: the
    # answer survives the round trip instead of being recomputed.
    assert all("is_ocr_derived" in row for row in rows)
    assert all(row["is_ocr_derived"] in (None, False) for row in rows)


def test_the_pdf_export_carries_what_the_screen_showed(client: TestClient, tmp_path: Path) -> None:
    """The gap ADR-0074 disclosed and ADR-0076 closes, end to end.

    A reviewer who reads "OCR — approximate" on screen and then sends
    the PDF must not be sending a document that omits it. Everything
    here is real: the OCR path, the review decision, the dashboard
    build, and the generated PDF read back with pypdf.
    """
    from pypdf import PdfReader

    scanned = tmp_path / "synthetic_scanned_policy.pdf"
    _write_scanned_pdf(scanned)
    with scanned.open("rb") as handle:
        ingested = client.post(
            "/ingest", files={"file": (scanned.name, handle, "application/pdf")}
        )
    assert ingested.status_code == 200, ingested.text
    document_id = ingested.json()["document_id"]

    assessment_id = client.post(
        "/assessments", json={"name": "Export provenance", "framework_name": "C2M2"}
    ).json()["id"]

    # A citation only reaches the export if its practice is still a GAP,
    # and a manual link is created ACCEPTED -- which makes the practice
    # met, so it would never appear. A pending AI proposal is both the
    # state that produces a citation and the realistic one: evidence the
    # engine offered from an OCR'd page and nobody has decided on yet.
    dependencies.get_cached_assessment_repository().add_evidence_link(
        EvidenceLink(
            assessment_id=assessment_id,
            document_id=document_id,
            practice_reference="ACCESS-1a",
            chunk_id=_first_chunk_id(client, document_id),
            source=EvidenceSource.AI_PROPOSED,
            review_status=EvidenceReviewStatus.PENDING,
            confidence=0.71,
        )
    )

    dashboard = client.get(f"/assessments/{assessment_id}/dashboard").json()
    cited = [
        citation
        for group in dashboard["complication"]
        for gap in group["gaps"]
        for citation in gap["cited_evidence"]
    ]
    assert cited, "expected the rejected OCR evidence to be cited against its gap"
    assert {c["text_provenance"] for c in cited} == {"ocr"}

    pdf = client.get(f"/assessments/{assessment_id}/report/pdf")
    assert pdf.status_code == 200
    import io as _io

    text = " ".join(
        " ".join(page.extract_text().split())
        for page in PdfReader(_io.BytesIO(pdf.content)).pages
    )
    assert "OCR - approximate" in text
