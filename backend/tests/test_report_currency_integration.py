"""A digest read off a real export, checked back against the record
(ADR-0077).

R-21 is about a document in someone's hands, so the only convincing
test generates a real one, reads the digest out of it the way a person
would, and asks the endpoint about it -- before and after the record
moves underneath them.
"""

from __future__ import annotations

import io
import re
from collections.abc import Iterator
from pathlib import Path

import openpyxl
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from compliance_platform.api import dependencies
from compliance_platform.core.config import Settings
from compliance_platform.main import app

_CACHED = (
    dependencies.get_cached_settings,
    dependencies.get_cached_vector_repository,
    dependencies.get_cached_assessment_repository,
    dependencies.get_cached_framework_registry,
)
_DIGEST = re.compile(r"Report digest \(SHA-256, v\d+\): ([0-9a-f]{64})")


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


def _assessment(client: TestClient) -> str:
    return client.post(
        "/assessments", json={"name": "Currency", "framework_name": "C2M2"}
    ).json()["id"]


def _ingest(client: TestClient) -> str:
    body = (
        b"Access control policy. Multi factor authentication is required for remote access "
        b"to critical systems, and access reviews are performed quarterly."
    )
    response = client.post("/ingest", files={"file": ("policy.txt", body, "text/plain")})
    assert response.status_code == 200
    return response.json()["document_id"]


def _digest_from_pdf(client: TestClient, assessment_id: str) -> str:
    pdf = client.get(f"/assessments/{assessment_id}/report/pdf")
    assert pdf.status_code == 200
    text = " ".join(
        " ".join(page.extract_text().split()) for page in PdfReader(io.BytesIO(pdf.content)).pages
    )
    match = _DIGEST.search(text)
    assert match, f"no report digest printed in the PDF: {text[:400]}"
    return match.group(1)


def _currency(client: TestClient, assessment_id: str, digest: str | None) -> dict:
    query = f"?digest={digest}" if digest else ""
    response = client.get(f"/assessments/{assessment_id}/report-currency{query}")
    assert response.status_code == 200, response.text
    return response.json()


def test_a_freshly_generated_report_is_current(client: TestClient) -> None:
    assessment_id = _assessment(client)

    digest = _digest_from_pdf(client, assessment_id)

    assert _currency(client, assessment_id, digest)["status"] == "current"


def test_a_report_goes_stale_when_the_record_moves(client: TestClient) -> None:
    """The whole point: a board pack printed on Monday, evidence
    reviewed on Tuesday."""
    assessment_id = _assessment(client)
    document_id = _ingest(client)
    monday = _digest_from_pdf(client, assessment_id)
    assert _currency(client, assessment_id, monday)["status"] == "current"

    client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1a"},
    )

    answer = _currency(client, assessment_id, monday)
    assert answer["status"] == "superseded"
    assert answer["current_digest"] != monday
    assert any("Current status" in line for line in answer["changes"])


def test_the_regenerated_report_is_current_again(client: TestClient) -> None:
    assessment_id = _assessment(client)
    document_id = _ingest(client)
    stale = _digest_from_pdf(client, assessment_id)
    client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1a"},
    )
    assert _currency(client, assessment_id, stale)["status"] == "superseded"

    reissued = _digest_from_pdf(client, assessment_id)

    assert _currency(client, assessment_id, reissued)["status"] == "current"


def test_no_digest_is_unverifiable(client: TestClient) -> None:
    """An export generated before ADR-0077 carries no digest, and must
    not be reported stale on that basis alone."""
    assessment_id = _assessment(client)

    assert _currency(client, assessment_id, None)["status"] == "unverifiable"


def test_the_xlsx_prints_the_same_digest_as_the_pdf(client: TestClient) -> None:
    """Both formats are rendered from one DashboardReport (ADR-0013), so
    a digest read off either must check out. If they diverged, a reader
    could be told their spreadsheet is stale and their PDF is not."""
    assessment_id = _assessment(client)
    pdf_digest = _digest_from_pdf(client, assessment_id)

    xlsx = client.get(f"/assessments/{assessment_id}/report/xlsx")
    assert xlsx.status_code == 200
    workbook = openpyxl.load_workbook(io.BytesIO(xlsx.content))
    rows = dict(
        (row[0], row[1]) for row in workbook["Situation"].values if row and row[0]
    )
    printed = next(value for key, value in rows.items() if "Report Digest" in str(key))

    assert printed == pdf_digest


def test_the_export_tells_the_reader_how_to_check_it(client: TestClient) -> None:
    """A digest nobody knows how to use is decoration. The instruction
    travels on the page, because the page is what leaves."""
    assessment_id = _assessment(client)
    pdf = client.get(f"/assessments/{assessment_id}/report/pdf")
    text = " ".join(
        " ".join(page.extract_text().split()) for page in PdfReader(io.BytesIO(pdf.content)).pages
    )

    assert "report-currency" in text


def test_an_unknown_assessment_is_a_404(client: TestClient) -> None:
    assert client.get("/assessments/nope/report-currency?digest=abc").status_code == 404
