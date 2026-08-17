"""End-to-end integration test: ingest a document through the real API,
create an assessment, link evidence to it, and move it through the
status state machine to finalization — exercising the real SQLite
store, LanceDB vector store, and FastAPI app together, not fakes. See
docs/architecture/00-repository-architecture.md's testing strategy.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from compliance_platform.api import dependencies
from compliance_platform.core.config import Settings
from compliance_platform.main import app

# get_cached_embedder is deliberately NOT cleared per-test (Sprint 9,
# R-13): its config (backend, dimensions, model_name,
# embedding_model_cache_dir) never varies between tests — only
# vector_store_dir/assessments_db_path do, via test_settings below — so
# clearing it forced every single test to pay a real, measured ~0.4s
# ONNX-session reload cost for no correctness benefit. Reusing one
# embedder instance across the whole test session is safe (embeddings
# are a pure function of input text, no per-test state) and is exactly
# the fix R-13 already named but never implemented.
_CACHED_DEPENDENCIES = (
    dependencies.get_cached_settings,
    dependencies.get_cached_vector_repository,
    dependencies.get_cached_assessment_repository,
    dependencies.get_cached_framework_registry,
)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    test_settings = Settings(
        vector_store_dir=tmp_path / "lancedb",
        assessments_db_path=tmp_path / "assessments.db",
        # Retained uploads (ADR-0056). conftest.py's session-wide
        # isolate_retained_uploads fixture already covers this; named
        # here too so every writable path this app has appears in one
        # list rather than one of them being invisible.
        data_raw_dir=tmp_path / "raw",
    )

    for cached in _CACHED_DEPENDENCIES:
        cached.cache_clear()
    monkeypatch.setattr(dependencies, "get_settings", lambda: test_settings)

    with TestClient(app) as test_client:
        yield test_client

    for cached in _CACHED_DEPENDENCIES:
        cached.cache_clear()


def _ingest_sample_document(client: TestClient) -> str:
    content = b"Multi factor authentication is required for all remote access to critical systems."
    response = client.post("/ingest", files={"file": ("policy.txt", content, "text/plain")})
    assert response.status_code == 200
    return response.json()["document_id"]


def test_full_assessment_lifecycle(client: TestClient) -> None:
    document_id = _ingest_sample_document(client)

    create_response = client.post(
        "/assessments", json={"name": "Q3 C2M2 Self Assessment", "framework_name": "C2M2"}
    )
    assert create_response.status_code == 200
    assessment = create_response.json()
    assessment_id = assessment["id"]
    assert assessment["status"] == "draft"

    # ACCESS-1a is a real C2M2 practice ID (see framework_mapping/c2m2_v2_1.yaml,
    # ADR-0009); as of Sprint 3 this is validated against the loaded schema,
    # not accepted as arbitrary free text.
    evidence_response = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1a"},
    )
    assert evidence_response.status_code == 200
    assert evidence_response.json()["review_status"] == "accepted"

    to_review = client.post(f"/assessments/{assessment_id}/status", json={"status": "in_review"})
    assert to_review.status_code == 200
    assert to_review.json()["status"] == "in_review"

    finalize = client.post(f"/assessments/{assessment_id}/status", json={"status": "finalized"})
    assert finalize.status_code == 200
    assert finalize.json()["status"] == "finalized"

    history = client.get(f"/assessments/{assessment_id}/status-history")
    assert history.status_code == 200
    statuses = [entry["to_status"] for entry in history.json()]
    assert statuses == ["draft", "in_review", "finalized"]

    evidence_list = client.get(f"/assessments/{assessment_id}/evidence")
    assert evidence_list.status_code == 200
    assert len(evidence_list.json()) == 1

    blocked = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1b"},
    )
    assert blocked.status_code == 409


def test_evidence_rejected_for_document_never_ingested(client: TestClient) -> None:
    create_response = client.post(
        "/assessments", json={"name": "Test", "framework_name": "NIST CSF 2.0"}
    )
    assessment_id = create_response.json()["id"]
    response = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": "never-ingested", "practice_reference": "GV.OC-01"},
    )
    assert response.status_code == 422


def test_invalid_status_transition_returns_409(client: TestClient) -> None:
    create_response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create_response.json()["id"]
    response = client.post(f"/assessments/{assessment_id}/status", json={"status": "finalized"})
    assert response.status_code == 409


def test_get_unknown_assessment_returns_404(client: TestClient) -> None:
    response = client.get("/assessments/does-not-exist")
    assert response.status_code == 404


def test_handled_domain_exceptions_are_logged(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    # Security hardening (controlled-pilot readiness audit §A.12): every
    # handled domain exception used to vanish into a JSON response with
    # zero server-side record.
    with caplog.at_level("WARNING", logger="compliance_platform.api.error_handlers"):
        response = client.get("/assessments/does-not-exist")
    assert response.status_code == 404
    assert any("does-not-exist" in record.message for record in caplog.records)


def test_list_assessments_returns_created_assessments(client: TestClient) -> None:
    client.post("/assessments", json={"name": "One", "framework_name": "C2M2"})
    client.post("/assessments", json={"name": "Two", "framework_name": "NIST CSF 2.0"})
    response = client.get("/assessments")
    assert response.status_code == 200
    names = {a["name"] for a in response.json()}
    assert {"One", "Two"} <= names


# --- Framework browsing and scoring (Sprint 3) ---


def test_get_c2m2_framework_returns_real_structure(client: TestClient) -> None:
    response = client.get("/frameworks/C2M2")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "2.1"
    assert len(body["domains"]) == 10
    access = next(d for d in body["domains"] if d["short_code"] == "ACCESS")
    assert access["practices_populated"] is True


def test_get_unknown_framework_returns_404(client: TestClient) -> None:
    response = client.get("/frameworks/Not A Real Framework")
    assert response.status_code == 404


def test_link_evidence_rejects_invalid_c2m2_practice_reference(client: TestClient) -> None:
    document_id = _ingest_sample_document(client)
    create_response = client.post(
        "/assessments", json={"name": "Test", "framework_name": "C2M2"}
    )
    assessment_id = create_response.json()["id"]
    response = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "NOT-A-REAL-PRACTICE"},
    )
    assert response.status_code == 422


def test_score_endpoint_computes_real_mil1_for_access_domain(client: TestClient) -> None:
    """End-to-end proof of the cumulative MIL scoring rule against real
    C2M2 data: link evidence for every MIL1 practice in the ACCESS
    domain (across all its objectives, not just one) and confirm the
    domain scores MIL1 — while an untouched, unpopulated domain (RISK)
    correctly reports 0, not an error.
    """
    document_id = _ingest_sample_document(client)
    create_response = client.post(
        "/assessments", json={"name": "Scoring Test", "framework_name": "C2M2"}
    )
    assessment_id = create_response.json()["id"]

    framework = client.get("/frameworks/C2M2").json()
    access = next(d for d in framework["domains"] if d["short_code"] == "ACCESS")
    mil1_practice_ids = [
        practice["id"]
        for objective in access["objectives"]
        for practice in objective["practices"]
        if practice["mil"] == 1
    ]
    assert mil1_practice_ids  # sanity check the fixture data itself isn't empty

    for practice_id in mil1_practice_ids:
        response = client.post(
            f"/assessments/{assessment_id}/evidence",
            json={"document_id": document_id, "practice_reference": practice_id},
        )
        assert response.status_code == 200

    scores = client.get(f"/assessments/{assessment_id}/score")
    assert scores.status_code == 200
    body = scores.json()
    assert body["ACCESS"] == 1
    assert body["RISK"] == 0  # unpopulated domain, never an error


def test_score_endpoint_returns_422_for_framework_with_no_schema(client: TestClient) -> None:
    create_response = client.post(
        "/assessments", json={"name": "Test", "framework_name": "Not A Real Framework"}
    )
    assessment_id = create_response.json()["id"]
    response = client.get(f"/assessments/{assessment_id}/score")
    assert response.status_code == 422


def _sample_evidence_path(filename: str) -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "sample_evidence" / filename


def test_propose_mappings_and_review_workflow_end_to_end(client: TestClient) -> None:
    """Real end-to-end proof of the retrieval-based mapping engine
    (ADR-0011) against real embeddings and real C2M2 data: ingest the
    real synthetic access control policy, manually link one practice to
    associate the document with the assessment, ask the engine to
    propose additional mappings, then accept one — confirming
    compute_scores reflects the newly accepted evidence.
    """
    policy_path = _sample_evidence_path("synthetic_access_control_policy.md")
    with policy_path.open("rb") as f:
        response = client.post(
            "/ingest",
            files={"file": ("synthetic_access_control_policy.md", f, "text/markdown")},
        )
    assert response.status_code == 200
    document_id = response.json()["document_id"]

    create_response = client.post(
        "/assessments", json={"name": "Mapping Engine Test", "framework_name": "C2M2"}
    )
    assessment_id = create_response.json()["id"]

    # Manually link one practice to associate the document with the
    # assessment — propose_mappings only searches documents already
    # connected to the assessment this way, never the whole store.
    manual_link = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1i"},
    )
    assert manual_link.status_code == 200

    proposals_response = client.post(f"/assessments/{assessment_id}/propose-mappings")
    assert proposals_response.status_code == 200
    proposals = proposals_response.json()
    assert len(proposals) > 0  # the real ONNX embedder should find at least one real match
    assert all(p["source"] == "ai_proposed" for p in proposals)
    assert all(p["review_status"] == "pending" for p in proposals)
    assert all(p["confidence"] is not None and p["confidence"] > 0 for p in proposals)
    # ACCESS-1i was already manually covered, so the engine must not re-propose it.
    assert all(p["practice_reference"] != "ACCESS-1i" for p in proposals)

    # Calling propose-mappings again must not create duplicate pending
    # proposals for the same practices.
    second_call = client.post(f"/assessments/{assessment_id}/propose-mappings")
    assert second_call.status_code == 200
    assert second_call.json() == []

    evidence_list = client.get(f"/assessments/{assessment_id}/evidence").json()
    pending_links = [e for e in evidence_list if e["review_status"] == "pending"]
    assert len(pending_links) == len(proposals)

    accepted = client.post(
        f"/assessments/{assessment_id}/evidence/{pending_links[0]['id']}/review",
        json={"decision": "accepted"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["review_status"] == "accepted"

    # Not asserting scores["ACCESS"] > 0 here: C2M2 is cumulative_mil
    # (ADR-0009), meaning ACCESS only advances past MIL0 once ALL 8 of
    # its MIL1 practices are covered (Sprint 3's tests exercise that
    # rule directly against synthetic and real data). Two accepted
    # links are not expected to be enough on their own, and asserting
    # otherwise here would just be re-testing scoring semantics this
    # test isn't about. What this test actually verifies is that the
    # score endpoint still resolves correctly with mixed accepted/
    # pending evidence present, and that only the accepted link counts.
    scores = client.get(f"/assessments/{assessment_id}/score").json()
    assert isinstance(scores["ACCESS"], float)

    still_pending = [
        e
        for e in client.get(f"/assessments/{assessment_id}/evidence").json()
        if e["review_status"] == "pending"
    ]
    assert len(still_pending) == len(pending_links) - 1


def test_review_evidence_rejects_reviewing_an_already_accepted_manual_link(
    client: TestClient,
) -> None:
    document_id = _ingest_sample_document(client)
    create_response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create_response.json()["id"]
    link_response = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1a"},
    )
    link_id = link_response.json()["id"]
    # Manual links default to ACCEPTED, not PENDING — reviewing one
    # should be rejected outright, not silently allowed to re-review.
    response = client.post(
        f"/assessments/{assessment_id}/evidence/{link_id}/review",
        json={"decision": "accepted"},
    )
    assert response.status_code == 409


def test_review_evidence_edit_updates_practice_reference(client: TestClient) -> None:
    document_id = _ingest_sample_document(client)
    create_response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create_response.json()["id"]

    client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1a"},
    )
    proposals = client.post(f"/assessments/{assessment_id}/propose-mappings").json()
    if not proposals:
        pytest.skip("no AI-proposed mapping crossed the confidence threshold for this fixture")
    link_id = proposals[0]["id"]

    response = client.post(
        f"/assessments/{assessment_id}/evidence/{link_id}/review",
        json={"decision": "edited", "corrected_practice_reference": "ACCESS-2a"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["review_status"] == "edited"
    assert body["practice_reference"] == "ACCESS-2a"


def test_propose_mappings_returns_empty_with_no_associated_documents(client: TestClient) -> None:
    create_response = client.post(
        "/assessments", json={"name": "Empty Test", "framework_name": "C2M2"}
    )
    assessment_id = create_response.json()["id"]
    response = client.post(f"/assessments/{assessment_id}/propose-mappings")
    assert response.status_code == 200
    assert response.json() == []


def test_propose_mappings_returns_404_for_unknown_assessment(client: TestClient) -> None:
    response = client.post("/assessments/does-not-exist/propose-mappings")
    assert response.status_code == 404


# --- NIST CSF 2.0 coverage scoring (Sprint 4) ---


def test_get_nist_csf_framework_returns_real_structure(client: TestClient) -> None:
    response = client.get("/frameworks/NIST CSF 2.0")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "2.0"
    assert body["scoring_model"] == "coverage"
    assert len(body["domains"]) == 6
    govern = next(d for d in body["domains"] if d["short_code"] == "GV")
    assert govern["practices_populated"] is True


def test_link_evidence_rejects_invalid_nist_subcategory(client: TestClient) -> None:
    document_id = _ingest_sample_document(client)
    create_response = client.post(
        "/assessments", json={"name": "Test", "framework_name": "NIST CSF 2.0"}
    )
    assessment_id = create_response.json()["id"]
    response = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "NOT-A-REAL-SUBCATEGORY"},
    )
    assert response.status_code == 422


def test_nist_score_endpoint_computes_real_coverage_for_protect_function(
    client: TestClient,
) -> None:
    """End-to-end proof of coverage scoring against real NIST CSF 2.0
    data: link evidence for one PR.AA subcategory (Identity Management,
    Authentication, and Access Control — the same thematic pairing as
    the C2M2 ACCESS demo in Sprint 3) and confirm the PR function's
    coverage score reflects it as a fraction, not a MIL level.
    """
    document_id = _ingest_sample_document(client)
    create_response = client.post(
        "/assessments", json={"name": "NIST Scoring Test", "framework_name": "NIST CSF 2.0"}
    )
    assessment_id = create_response.json()["id"]

    framework = client.get("/frameworks/NIST CSF 2.0").json()
    protect = next(d for d in framework["domains"] if d["short_code"] == "PR")
    total_pr_subcategories = sum(len(o["practices"]) for o in protect["objectives"])

    response = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "PR.AA-01"},
    )
    assert response.status_code == 200

    scores = client.get(f"/assessments/{assessment_id}/score")
    assert scores.status_code == 200
    body = scores.json()
    assert body["PR"] == pytest.approx(1 / total_pr_subcategories)
    assert body["GV"] == 0.0  # untouched function, honest zero not an error


def test_dashboard_endpoint_computes_real_gap_analysis_for_access_domain(
    client: TestClient,
) -> None:
    """End-to-end proof of Sprint 6's dashboard against real C2M2 data:
    link evidence for all but one MIL1 ACCESS practice, and confirm the
    dashboard's complication section correctly names the one remaining
    gap and the resolution section prioritizes it. Since Sprint 10's
    full C2M2 transcription (US-3.1a), every domain is populated, so
    situation.unpopulated_domains is asserted empty here rather than
    containing a domain like the pre-Sprint-10 RISK example this test
    used to check — the "unpopulated domain excluded from complication"
    mechanic itself is still covered by services/tests/test_report_service.py's
    synthetic-fixture tests, which can construct an unpopulated domain
    on demand regardless of C2M2's real transcription state.
    """
    document_id = _ingest_sample_document(client)
    create_response = client.post(
        "/assessments", json={"name": "Dashboard Test", "framework_name": "C2M2"}
    )
    assessment_id = create_response.json()["id"]

    framework = client.get("/frameworks/C2M2").json()
    access = next(d for d in framework["domains"] if d["short_code"] == "ACCESS")
    mil1_practice_ids = [
        practice["id"]
        for objective in access["objectives"]
        for practice in objective["practices"]
        if practice["mil"] == 1
    ]
    assert len(mil1_practice_ids) > 1  # sanity check the fixture data isn't degenerate

    held_back = mil1_practice_ids[0]
    for practice_id in mil1_practice_ids[1:]:
        response = client.post(
            f"/assessments/{assessment_id}/evidence",
            json={"document_id": document_id, "practice_reference": practice_id},
        )
        assert response.status_code == 200

    dashboard = client.get(f"/assessments/{assessment_id}/dashboard")
    assert dashboard.status_code == 200
    body = dashboard.json()

    assert body["situation"]["accepted_count"] == len(mil1_practice_ids) - 1
    # Sprint 10 (US-3.1a): all 10 C2M2 domains are now transcribed and
    # populated, so this is correctly empty rather than naming a
    # not-yet-transcribed domain the way it would have before this sprint.
    assert body["situation"]["unpopulated_domains"] == []

    access_group = next(g for g in body["complication"] if g["domain_short_code"] == "ACCESS")
    gap_ids = {g["practice_id"] for g in access_group["gaps"]}
    assert held_back in gap_ids
    assert access_group["so_what"]  # non-empty, business-consequence sentence

    assert body["overall"]["scoring_model"] == "cumulative_mil"
    assert body["overall"]["domains_at_mil1_or_above"] == 0  # ACCESS not yet fully at MIL1
    assert body["overall"]["overall_coverage_fraction"] is None

    resolution_codes = [r["domain_short_code"] for r in body["resolution"]]
    assert "ACCESS" in resolution_codes


def test_dashboard_endpoint_computes_real_coverage_fraction_for_nist(client: TestClient) -> None:
    """Same proof as above but for NIST CSF 2.0's coverage scoring
    model: confirms overall.overall_coverage_fraction is populated (not
    domains_at_mil1_or_above, which only applies to cumulative_mil
    frameworks) and is a real weighted fraction across all 6 fully
    transcribed functions, not just the touched one.
    """
    document_id = _ingest_sample_document(client)
    create_response = client.post(
        "/assessments", json={"name": "NIST Dashboard Test", "framework_name": "NIST CSF 2.0"}
    )
    assessment_id = create_response.json()["id"]

    framework = client.get("/frameworks/NIST CSF 2.0").json()
    total_subcategories = sum(
        len(o["practices"]) for d in framework["domains"] for o in d["objectives"]
    )

    response = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "PR.AA-01"},
    )
    assert response.status_code == 200

    dashboard = client.get(f"/assessments/{assessment_id}/dashboard")
    assert dashboard.status_code == 200
    body = dashboard.json()

    assert body["situation"]["unpopulated_domains"] == []  # NIST CSF 2.0 has full coverage
    assert body["overall"]["scoring_model"] == "coverage"
    assert body["overall"]["domains_at_mil1_or_above"] is None
    assert body["overall"]["overall_coverage_fraction"] == pytest.approx(1 / total_subcategories)

    pr_group = next(g for g in body["complication"] if g["domain_short_code"] == "PR")
    assert not any(g["practice_id"] == "PR.AA-01" for g in pr_group["gaps"])


def test_report_pdf_and_xlsx_endpoints_render_real_dashboard_data(client: TestClient) -> None:
    """End-to-end proof of Sprint 7: the exported PDF and XLSX are
    generated from the same real assessment data the dashboard endpoint
    already proved correct above, not a second, independently-computed
    path (see ADR-0013).
    """
    document_id = _ingest_sample_document(client)
    create_response = client.post(
        "/assessments", json={"name": "Report Export Test", "framework_name": "C2M2"}
    )
    assessment_id = create_response.json()["id"]

    response = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1a"},
    )
    assert response.status_code == 200

    pdf_response = client.get(f"/assessments/{assessment_id}/report/pdf")
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"] == "application/pdf"
    assert "attachment" in pdf_response.headers["content-disposition"]
    assert pdf_response.content.startswith(b"%PDF")

    xlsx_response = client.get(f"/assessments/{assessment_id}/report/xlsx")
    assert xlsx_response.status_code == 200
    assert xlsx_response.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "attachment" in xlsx_response.headers["content-disposition"]
    assert xlsx_response.content[:2] == b"PK"  # xlsx is a zip container


def test_report_endpoints_return_404_for_unknown_assessment(client: TestClient) -> None:
    assert client.get("/assessments/does-not-exist/report/pdf").status_code == 404
    assert client.get("/assessments/does-not-exist/report/xlsx").status_code == 404


def test_chat_answers_only_from_reviewed_chunk_scoped_evidence(client: TestClient) -> None:
    """End-to-end proof of Sprint 8's retrieval-only chat (ADR-0014)
    against real embeddings and real C2M2 data: a manually-linked
    practice with no chunk_id (ACCESS-1i) must never appear in chat
    results even though it is accepted, real evidence — chat can only
    answer from evidence that has an actual cited chunk of text. An
    AI-proposed pending link must not appear until accepted. Once
    accepted, it becomes answerable and is returned ranked by
    similarity to the question, with its real cited text attached.
    """
    policy_path = _sample_evidence_path("synthetic_access_control_policy.md")
    with policy_path.open("rb") as f:
        response = client.post(
            "/ingest",
            files={"file": ("synthetic_access_control_policy.md", f, "text/markdown")},
        )
    assert response.status_code == 200
    document_id = response.json()["document_id"]

    create_response = client.post(
        "/assessments", json={"name": "Chat Test", "framework_name": "C2M2"}
    )
    assessment_id = create_response.json()["id"]

    # Manual link, no chunk_id — real accepted evidence, but not
    # chunk-scoped, so it must never be answerable via chat.
    manual_link = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1i"},
    )
    assert manual_link.status_code == 200
    assert manual_link.json()["chunk_id"] is None

    proposals = client.post(f"/assessments/{assessment_id}/propose-mappings").json()
    assert len(proposals) > 0

    # Before accepting anything: chat must not surface any pending
    # AI-proposed link, and must not surface the chunk_id-less manual
    # link either.
    unreviewed_answer = client.post(
        f"/assessments/{assessment_id}/chat",
        json={"question": "Which practices are covered by multi-factor authentication?"},
    )
    assert unreviewed_answer.status_code == 200
    assert unreviewed_answer.json()["results"] == []

    accepted = client.post(
        f"/assessments/{assessment_id}/evidence/{proposals[0]['id']}/review",
        json={"decision": "accepted"},
    )
    assert accepted.status_code == 200
    accepted_practice = accepted.json()["practice_reference"]
    accepted_chunk_id = accepted.json()["chunk_id"]
    assert accepted_chunk_id is not None

    chat_response = client.post(
        f"/assessments/{assessment_id}/chat",
        json={"question": "Which practices are covered by multi-factor authentication?"},
    )
    assert chat_response.status_code == 200
    body = chat_response.json()
    assert body["question"] == "Which practices are covered by multi-factor authentication?"
    assert len(body["results"]) >= 1
    result = body["results"][0]
    assert result["practice_reference"] == accepted_practice
    assert result["chunk_id"] == accepted_chunk_id
    assert result["document_id"] == document_id
    assert result["chunk_text"]  # real cited text, not empty
    assert 0.0 <= result["similarity"] <= 1.0
    assert "ACCESS-1i" not in {r["practice_reference"] for r in body["results"]}


def test_chat_returns_empty_results_with_no_reviewed_evidence(client: TestClient) -> None:
    create_response = client.post(
        "/assessments", json={"name": "Empty Chat Test", "framework_name": "C2M2"}
    )
    assessment_id = create_response.json()["id"]
    response = client.post(
        f"/assessments/{assessment_id}/chat", json={"question": "Anything at all?"}
    )
    assert response.status_code == 200
    assert response.json() == {"question": "Anything at all?", "results": []}


def test_chat_returns_404_for_unknown_assessment(client: TestClient) -> None:
    response = client.post(
        "/assessments/does-not-exist/chat", json={"question": "Anything?"}
    )
    assert response.status_code == 404


# --- Sprint 9: closing real, measured error-path coverage gaps. Every
# endpoint below had at least one exception-handling branch (a real,
# reachable HTTP error response) with zero test coverage — found via
# `pytest --cov-report=term-missing`, not guessed. See
# docs/adr/ADR-0015-sprint-9-testing-refactoring-pass.md. ---


def test_unknown_assessment_returns_404_across_remaining_endpoints(client: TestClient) -> None:
    """Every endpoint below already returns 404 correctly in production
    (they share AssessmentService.get_assessment's exception), but none
    of them had a direct test confirming it — see the coverage note
    above.
    """
    assessment_id = "does-not-exist"
    status_response = client.post(
        f"/assessments/{assessment_id}/status", json={"status": "in_review"}
    )
    assert status_response.status_code == 404
    assert client.get(f"/assessments/{assessment_id}/status-history").status_code == 404
    assert (
        client.post(
            f"/assessments/{assessment_id}/evidence",
            json={"document_id": "doc-1", "practice_reference": "ACCESS-1a"},
        ).status_code
        == 404
    )
    assert client.get(f"/assessments/{assessment_id}/evidence").status_code == 404
    assert client.get(f"/assessments/{assessment_id}/score").status_code == 404
    assert client.get(f"/assessments/{assessment_id}/dashboard").status_code == 404
    assert (
        client.post(
            f"/assessments/{assessment_id}/evidence/some-link-id/review",
            json={"decision": "accepted"},
        ).status_code
        == 404
    )


def test_dashboard_and_export_endpoints_return_422_for_framework_with_no_schema(
    client: TestClient,
) -> None:
    """Same bogus-framework setup as
    test_score_endpoint_returns_422_for_framework_with_no_schema,
    extended to the three other endpoints that share
    FrameworkScoringUnavailableError but had no direct test of their
    own: the dashboard and both export formats are built from
    build_dashboard, which raises the identical error compute_scores
    does.
    """
    create_response = client.post(
        "/assessments", json={"name": "Test", "framework_name": "Not A Real Framework"}
    )
    assessment_id = create_response.json()["id"]
    assert client.get(f"/assessments/{assessment_id}/dashboard").status_code == 422
    assert client.get(f"/assessments/{assessment_id}/report/pdf").status_code == 422
    assert client.get(f"/assessments/{assessment_id}/report/xlsx").status_code == 422
    assert (
        client.post(f"/assessments/{assessment_id}/propose-mappings").status_code == 422
    )


def test_review_evidence_rejects_unknown_evidence_link(client: TestClient) -> None:
    create_response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create_response.json()["id"]
    response = client.post(
        f"/assessments/{assessment_id}/evidence/does-not-exist/review",
        json={"decision": "accepted"},
    )
    assert response.status_code == 404


def test_review_evidence_blocked_on_finalized_assessment(client: TestClient) -> None:
    document_id = _ingest_sample_document(client)
    create_response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create_response.json()["id"]
    link_response = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={
            "document_id": document_id,
            "practice_reference": "ACCESS-1a",
            "source": "ai_proposed",
        },
    )
    link_id = link_response.json()["id"]
    client.post(f"/assessments/{assessment_id}/status", json={"status": "in_review"})
    # A pending AI proposal blocks finalization (ADR-0058), and this test
    # is about immutability AFTER finalization, so the proposal is
    # reviewed first. The gate itself has dedicated tests below.
    client.post(
        f"/assessments/{assessment_id}/evidence/{link_id}/review",
        json={"decision": "accepted"},
    )
    client.post(f"/assessments/{assessment_id}/status", json={"status": "finalized"})

    response = client.post(
        f"/assessments/{assessment_id}/evidence/{link_id}/review",
        json={"decision": "accepted"},
    )
    assert response.status_code == 409


def test_review_evidence_rejects_invalid_decision(client: TestClient) -> None:
    """EvidenceReviewStatus includes PENDING as a valid enum member (so
    Pydantic accepts it as a well-formed request body), but PENDING is
    not a valid *decision* — only accepted/edited/rejected are.
    """
    document_id = _ingest_sample_document(client)
    create_response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create_response.json()["id"]
    link_response = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={
            "document_id": document_id,
            "practice_reference": "ACCESS-1a",
            "source": "ai_proposed",
        },
    )
    link_id = link_response.json()["id"]

    response = client.post(
        f"/assessments/{assessment_id}/evidence/{link_id}/review",
        json={"decision": "pending"},
    )
    assert response.status_code == 400


def test_review_evidence_edit_rejects_invalid_practice_reference(client: TestClient) -> None:
    document_id = _ingest_sample_document(client)
    create_response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create_response.json()["id"]
    link_response = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={
            "document_id": document_id,
            "practice_reference": "ACCESS-1a",
            "source": "ai_proposed",
        },
    )
    link_id = link_response.json()["id"]

    response = client.post(
        f"/assessments/{assessment_id}/evidence/{link_id}/review",
        json={"decision": "edited", "corrected_practice_reference": "NOT-A-REAL-PRACTICE"},
    )
    assert response.status_code == 422


def test_review_evidence_edit_requires_corrected_practice_reference(client: TestClient) -> None:
    document_id = _ingest_sample_document(client)
    create_response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create_response.json()["id"]
    link_response = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={
            "document_id": document_id,
            "practice_reference": "ACCESS-1a",
            "source": "ai_proposed",
        },
    )
    link_id = link_response.json()["id"]

    response = client.post(
        f"/assessments/{assessment_id}/evidence/{link_id}/review",
        json={"decision": "edited"},
    )
    assert response.status_code == 400


def test_propose_mappings_blocked_on_finalized_assessment(client: TestClient) -> None:
    document_id = _ingest_sample_document(client)
    create_response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create_response.json()["id"]
    client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1a"},
    )
    client.post(f"/assessments/{assessment_id}/status", json={"status": "in_review"})
    client.post(f"/assessments/{assessment_id}/status", json={"status": "finalized"})

    response = client.post(f"/assessments/{assessment_id}/propose-mappings")
    assert response.status_code == 409


# --- Framework version pinning (ADR-0031) ---


def test_create_assessment_pins_real_framework_version(client: TestClient) -> None:
    response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assert response.status_code == 200
    body = response.json()
    # Real framework_mapping/c2m2_v2_1.yaml version -- confirms this is
    # captured from the actual loaded schema, not a placeholder.
    assert body["framework_version"] not in (None, "")


def test_create_assessment_framework_version_none_for_unrecognized_framework(
    client: TestClient,
) -> None:
    response = client.post(
        "/assessments", json={"name": "Test", "framework_name": "Not A Real Framework"}
    )
    assert response.status_code == 200
    assert response.json()["framework_version"] is None


# --- Multi-version registry support (Sprint 18, ADR-0053) ---


def test_get_framework_versions_lists_the_real_currently_loaded_c2m2_version(
    client: TestClient,
) -> None:
    response = client.get("/frameworks/C2M2/versions")
    assert response.status_code == 200
    versions = response.json()
    assert isinstance(versions, list) and len(versions) == 1
    assert versions[0]  # a real, non-empty version string


def test_get_framework_versions_is_empty_for_an_unrecognized_name(client: TestClient) -> None:
    response = client.get("/frameworks/Not A Real Framework/versions")
    assert response.status_code == 200
    assert response.json() == []


def test_get_framework_with_the_real_current_version_succeeds(client: TestClient) -> None:
    current_version = client.get("/frameworks/C2M2/versions").json()[0]
    response = client.get(f"/frameworks/C2M2?version={current_version}")
    assert response.status_code == 200
    assert response.json()["version"] == current_version


def test_get_framework_with_an_unknown_version_404s(client: TestClient) -> None:
    response = client.get("/frameworks/C2M2?version=not-a-real-version")
    assert response.status_code == 404
    assert "not-a-real-version" in response.json()["detail"]


def test_create_assessment_pins_the_explicitly_requested_real_version(
    client: TestClient,
) -> None:
    current_version = client.get("/frameworks/C2M2/versions").json()[0]
    response = client.post(
        "/assessments",
        json={"name": "Test", "framework_name": "C2M2", "framework_version": current_version},
    )
    assert response.status_code == 200
    assert response.json()["framework_version"] == current_version


def test_create_assessment_with_an_unknown_version_of_a_real_framework_422s(
    client: TestClient,
) -> None:
    response = client.post(
        "/assessments",
        json={"name": "Test", "framework_name": "C2M2", "framework_version": "not-a-real-version"},
    )
    assert response.status_code == 422


# --- Practice findings (ADR-0030) ---


def test_set_practice_finding_and_it_appears_in_dashboard_gap_status(client: TestClient) -> None:
    create_response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create_response.json()["id"]

    put_response = client.put(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1a",
        json={
            "status": "not_satisfied",
            "rationale": "Reviewed the access policy directly; provisioning is not role-based.",
        },
    )
    assert put_response.status_code == 200
    body = put_response.json()
    assert body["status"] == "not_satisfied"
    assert body["assessment_id"] == assessment_id
    assert body["practice_reference"] == "ACCESS-1a"

    list_response = client.get(f"/assessments/{assessment_id}/practice-findings")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    dashboard_response = client.get(f"/assessments/{assessment_id}/dashboard")
    assert dashboard_response.status_code == 200
    gaps = [g for group in dashboard_response.json()["complication"] for g in group["gaps"]]
    access_1a = next(g for g in gaps if g["practice_id"] == "ACCESS-1a")
    assert access_1a["status"] == "not_satisfied"
    assert "role-based" in access_1a["finding_rationale"]


def test_practice_finding_history_records_every_transition(client: TestClient) -> None:
    create_response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create_response.json()["id"]

    client.put(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1a",
        json={"status": "insufficient_evidence", "rationale": "Nothing reviewed yet."},
    )
    client.put(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1a",
        json={"status": "satisfied", "rationale": "Policy doc reviewed and confirmed."},
    )

    history_response = client.get(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1a/history"
    )
    assert history_response.status_code == 200
    history = history_response.json()
    assert [h["to_status"] for h in history] == ["insufficient_evidence", "satisfied"]
    assert history[0]["from_status"] is None
    assert history[1]["from_status"] == "insufficient_evidence"


def test_set_practice_finding_rejects_missing_rationale(client: TestClient) -> None:
    create_response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create_response.json()["id"]

    response = client.put(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1a",
        json={"status": "not_applicable", "rationale": ""},
    )
    assert response.status_code == 400


def test_set_practice_finding_rejects_unknown_practice_reference(client: TestClient) -> None:
    create_response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create_response.json()["id"]

    response = client.put(
        f"/assessments/{assessment_id}/practice-findings/NOT-A-REAL-PRACTICE",
        json={"status": "satisfied", "rationale": "n/a"},
    )
    assert response.status_code == 422


def test_set_practice_finding_blocked_on_finalized_assessment(client: TestClient) -> None:
    create_response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create_response.json()["id"]
    client.post(f"/assessments/{assessment_id}/status", json={"status": "in_review"})
    client.post(f"/assessments/{assessment_id}/status", json={"status": "finalized"})

    response = client.put(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1a",
        json={"status": "satisfied", "rationale": "n/a"},
    )
    assert response.status_code == 409


def test_not_applicable_finding_excludes_practice_from_score_denominator(
    client: TestClient,
) -> None:
    """Live confirmation, over the real API + real C2M2 data, that a
    NOT_APPLICABLE practice does not block its domain's MIL forever.

    Updated for ADR-0057: the exclusion now requires a supporting
    accepted/edited evidence link, because changing the denominator moves
    the score just as changing the numerator does. The original assertion
    (exclusion can only hold or raise a score) is unchanged and still
    holds — only the precondition is stricter.
    """
    document_id = _ingest_sample_document(client)
    create_response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create_response.json()["id"]

    before = client.get(f"/assessments/{assessment_id}/score").json()

    client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1a"},
    )
    client.put(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1a",
        json={"status": "not_applicable", "rationale": "No remote access exists in this org."},
    )
    after = client.get(f"/assessments/{assessment_id}/score").json()

    # Excluding a practice can only ever hold or raise a domain's score,
    # never lower it as a side effect of removing it from the denominator.
    assert after["ACCESS"] >= before["ACCESS"]

    dashboard = client.get(f"/assessments/{assessment_id}/dashboard").json()
    gap_ids = {g["practice_id"] for group in dashboard["complication"] for g in group["gaps"]}
    assert "ACCESS-1a" not in gap_ids


# --- Evidence requests (Sprint 18, ADR-0043) ---


def test_request_more_evidence_and_list_it(client: TestClient) -> None:
    create_response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create_response.json()["id"]

    request_response = client.post(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1a/evidence-requests",
        json={
            "note": "Please upload the current access provisioning policy.",
            "requested_by": "priya",
        },
    )
    assert request_response.status_code == 200
    body = request_response.json()
    assert body["practice_reference"] == "ACCESS-1a"
    assert body["requested_by"] == "priya"
    assert body["resolved_at"] is None

    list_response = client.get(f"/assessments/{assessment_id}/evidence-requests")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["id"] == body["id"]


def test_resolve_evidence_request(client: TestClient) -> None:
    create_response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create_response.json()["id"]
    request_id = client.post(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1a/evidence-requests",
        json={"note": "need something", "requested_by": "priya"},
    ).json()["id"]

    resolve_response = client.post(
        f"/assessments/{assessment_id}/evidence-requests/{request_id}/resolve",
        json={"resolved_by": "sam"},
    )
    assert resolve_response.status_code == 200
    body = resolve_response.json()
    assert body["resolved_by"] == "sam"
    assert body["resolved_at"] is not None


def test_request_more_evidence_rejects_missing_note(client: TestClient) -> None:
    create_response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create_response.json()["id"]

    response = client.post(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1a/evidence-requests",
        json={"note": "", "requested_by": "priya"},
    )
    assert response.status_code == 400


def test_request_more_evidence_rejects_unknown_practice_reference(client: TestClient) -> None:
    create_response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create_response.json()["id"]

    response = client.post(
        f"/assessments/{assessment_id}/practice-findings/NOT-A-REAL-PRACTICE/evidence-requests",
        json={"note": "need something", "requested_by": "priya"},
    )
    assert response.status_code == 422


def test_request_more_evidence_blocked_on_finalized_assessment(client: TestClient) -> None:
    create_response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create_response.json()["id"]
    client.post(f"/assessments/{assessment_id}/status", json={"status": "in_review"})
    client.post(f"/assessments/{assessment_id}/status", json={"status": "finalized"})

    response = client.post(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1a/evidence-requests",
        json={"note": "need something", "requested_by": "priya"},
    )
    assert response.status_code == 409


def test_resolve_evidence_request_returns_404_for_unknown_request(client: TestClient) -> None:
    create_response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create_response.json()["id"]

    response = client.post(
        f"/assessments/{assessment_id}/evidence-requests/does-not-exist/resolve",
        json={"resolved_by": "sam"},
    )
    assert response.status_code == 404


# --- Sanitization (ADR-0032) ---


def test_sanitization_preview_does_not_require_approval_first(client: TestClient) -> None:
    create_response = client.post(
        "/assessments",
        json={"name": "Contact security@example-utility.com", "framework_name": "C2M2"},
    )
    assessment_id = create_response.json()["id"]

    preview_response = client.post(
        f"/assessments/{assessment_id}/sanitization/preview", json={"custom_terms": []}
    )
    assert preview_response.status_code == 200
    body = preview_response.json()
    sanitized_name = body["sanitized_report"]["situation"]["assessment_name"]
    assert "security@example-utility.com" not in sanitized_name
    assert any(m["category"] == "email" for m in body["matches"])


def test_sanitized_export_blocked_until_approved_then_succeeds(client: TestClient) -> None:
    create_response = client.post(
        "/assessments",
        json={"name": "Assessment for Example Utility Co.", "framework_name": "C2M2"},
    )
    assessment_id = create_response.json()["id"]

    blocked = client.get(f"/assessments/{assessment_id}/report/pdf?sanitized=true")
    assert blocked.status_code == 412

    approve_response = client.post(
        f"/assessments/{assessment_id}/sanitization/approve",
        json={"custom_terms": ["Example Utility Co."], "approved_by": "compliance-lead"},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["approved_by"] == "compliance-lead"

    pdf_response = client.get(f"/assessments/{assessment_id}/report/pdf?sanitized=true")
    assert pdf_response.status_code == 200
    reader = PdfReader(io.BytesIO(pdf_response.content))
    pdf_text = "\n".join(page.extract_text() for page in reader.pages)
    assert "Example Utility Co." not in pdf_text
    assert "ORG-TERM" in pdf_text

    xlsx_response = client.get(f"/assessments/{assessment_id}/report/xlsx?sanitized=true")
    assert xlsx_response.status_code == 200


def test_sanitized_export_becomes_stale_after_a_new_finding_is_recorded(client: TestClient) -> None:
    create_response = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create_response.json()["id"]
    client.post(
        f"/assessments/{assessment_id}/sanitization/approve",
        json={"custom_terms": [], "approved_by": "compliance-lead"},
    )
    assert client.get(f"/assessments/{assessment_id}/report/pdf?sanitized=true").status_code == 200

    client.put(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1a",
        json={"status": "not_satisfied", "rationale": "Changed after approval."},
    )

    stale_response = client.get(f"/assessments/{assessment_id}/report/pdf?sanitized=true")
    assert stale_response.status_code == 409

    # Re-approving against the now-current content resolves it.
    client.post(
        f"/assessments/{assessment_id}/sanitization/approve",
        json={"custom_terms": [], "approved_by": "compliance-lead"},
    )
    assert client.get(f"/assessments/{assessment_id}/report/pdf?sanitized=true").status_code == 200


def test_unsanitized_export_unaffected_by_sanitization_feature(client: TestClient) -> None:
    create_response = client.post(
        "/assessments",
        json={"name": "Contact security@example-utility.com", "framework_name": "C2M2"},
    )
    assessment_id = create_response.json()["id"]
    # No approval ever created -- default (sanitized=false / omitted) must still work.
    response = client.get(f"/assessments/{assessment_id}/report/pdf")
    assert response.status_code == 200


# --- ADR-0057: positive scoring credit requires evidence ---
# Against the real FastAPI app, real SQLite and real C2M2 data, so these
# exercise the same code path a pilot would.


def test_satisfied_finding_without_evidence_earns_no_score_via_the_api(client: TestClient) -> None:
    create = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create.json()["id"]

    put = client.put(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1a",
        json={"status": "satisfied", "rationale": "Owner confirmed verbally during interview."},
    )
    assert put.status_code == 200

    # The finding is recorded...
    assert len(client.get(f"/assessments/{assessment_id}/practice-findings").json()) == 1
    # ...but confers no credit, and the score endpoint and dashboard agree.
    scores = client.get(f"/assessments/{assessment_id}/score").json()
    assert scores["ACCESS"] == 0
    dashboard = client.get(f"/assessments/{assessment_id}/dashboard").json()
    assert dashboard["situation"]["unsupported_satisfied_practices"] == ["ACCESS-1a"]
    assert any("no accepted or edited" in line for line in dashboard["situation"]["so_what"])


def test_satisfied_finding_with_accepted_evidence_earns_score_via_the_api(
    client: TestClient,
) -> None:
    document_id = _ingest_sample_document(client)
    create = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create.json()["id"]

    linked = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1a"},
    )
    assert linked.json()["review_status"] == "accepted"  # a manual link is accepted on creation
    client.put(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1a",
        json={"status": "satisfied", "rationale": "Verified against the uploaded access policy."},
    )

    dashboard = client.get(f"/assessments/{assessment_id}/dashboard").json()
    assert dashboard["situation"]["unsupported_satisfied_practices"] == []
    gaps = [g["practice_id"] for group in dashboard["complication"] for g in group["gaps"]]
    assert "ACCESS-1a" not in gaps  # performed, so not a gap


def test_not_applicable_without_evidence_is_not_silently_excluded_via_the_api(
    client: TestClient,
) -> None:
    create = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create.json()["id"]

    client.put(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1a",
        json={"status": "not_applicable", "rationale": "No assets of this type in scope."},
    )

    dashboard = client.get(f"/assessments/{assessment_id}/dashboard").json()
    assert dashboard["situation"]["unsupported_not_applicable_practices"] == ["ACCESS-1a"]
    # Still in the denominator, so still reported as a gap rather than vanishing.
    gaps = [g["practice_id"] for group in dashboard["complication"] for g in group["gaps"]]
    assert "ACCESS-1a" in gaps


def test_not_applicable_with_accepted_evidence_is_excluded_via_the_api(client: TestClient) -> None:
    document_id = _ingest_sample_document(client)
    create = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create.json()["id"]

    client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1a"},
    )
    client.put(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1a",
        json={"status": "not_applicable", "rationale": "Scope memo excludes these assets."},
    )

    dashboard = client.get(f"/assessments/{assessment_id}/dashboard").json()
    assert dashboard["situation"]["unsupported_not_applicable_practices"] == []
    gaps = [g["practice_id"] for group in dashboard["complication"] for g in group["gaps"]]
    assert "ACCESS-1a" not in gaps  # excluded from the denominator entirely


def test_pending_and_rejected_ai_evidence_confer_no_credit_via_the_api(
    client: TestClient,
) -> None:
    """The human-in-the-loop invariant over the real API.

    propose-mappings only returns proposals once the assessment already
    has an associated document, so a manual link to ACCESS-1a comes
    first — that link is accepted on creation and is deliberately NOT
    the practice under test here.
    """
    document_id = _ingest_sample_document(client)
    create = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create.json()["id"]

    client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1a"},
    )
    proposed = client.post(f"/assessments/{assessment_id}/propose-mappings")
    assert proposed.status_code == 200
    pending = [link for link in proposed.json() if link["review_status"] == "pending"]
    assert pending, "expected AI-proposed pending links once a document is associated"

    # A SATISFIED finding on a practice whose only evidence is PENDING
    # earns nothing: accepting it is the reviewer's job, not the finding's.
    pending_reference = pending[0]["practice_reference"]
    client.put(
        f"/assessments/{assessment_id}/practice-findings/{pending_reference}",
        json={"status": "satisfied", "rationale": "Looks right to me from the proposal alone."},
    )
    dashboard = client.get(f"/assessments/{assessment_id}/dashboard").json()
    assert pending_reference in dashboard["situation"]["unsupported_satisfied_practices"]

    # Rejecting that proposal must not change the answer either.
    rejected = client.post(
        f"/assessments/{assessment_id}/evidence/{pending[0]['id']}/review",
        json={"decision": "rejected", "note": "This passage does not show the control."},
    )
    assert rejected.status_code == 200
    dashboard = client.get(f"/assessments/{assessment_id}/dashboard").json()
    assert pending_reference in dashboard["situation"]["unsupported_satisfied_practices"]


# --- Finalization readiness gate (ADR-0058) ---


def test_finalization_readiness_reports_ready_for_a_clean_assessment(client: TestClient) -> None:
    create = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create.json()["id"]

    readiness = client.get(f"/assessments/{assessment_id}/finalization-readiness")
    assert readiness.status_code == 200
    body = readiness.json()
    assert body["is_ready"] is True
    assert body["blockers"] == []


def test_finalization_readiness_reports_each_blocker_category(client: TestClient) -> None:
    document_id = _ingest_sample_document(client)
    create = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create.json()["id"]

    client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1a"},
    )
    client.post(f"/assessments/{assessment_id}/propose-mappings")  # creates pending proposals
    client.post(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1b/evidence-requests",
        json={"note": "Need the quarterly access review export.", "requested_by": "Priya"},
    )
    client.put(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1c",
        json={"status": "satisfied", "rationale": "Believed satisfied without evidence."},
    )
    client.put(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1d",
        json={"status": "not_applicable", "rationale": "Believed out of scope."},
    )

    body = client.get(f"/assessments/{assessment_id}/finalization-readiness").json()
    assert body["is_ready"] is False
    categories = {blocker["category"] for blocker in body["blockers"]}
    assert categories == {
        "pending_ai_review",
        "unresolved_evidence_request",
        "unsupported_satisfied_finding",
        "unsupported_not_applicable_finding",
    }
    satisfied = next(
        b for b in body["blockers"] if b["category"] == "unsupported_satisfied_finding"
    )
    assert satisfied["affected_ids"] == ["ACCESS-1c"]
    assert satisfied["count"] == 1


def test_finalizing_with_blockers_returns_409_with_machine_readable_blockers(
    client: TestClient,
) -> None:
    """The gate is enforced server-side, and the refusal says what to fix
    without the caller parsing English."""
    document_id = _ingest_sample_document(client)
    create = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create.json()["id"]
    client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1a"},
    )
    client.put(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1b",
        json={"status": "satisfied", "rationale": "No evidence linked for this one."},
    )
    client.post(f"/assessments/{assessment_id}/status", json={"status": "in_review"})

    refused = client.post(f"/assessments/{assessment_id}/status", json={"status": "finalized"})
    assert refused.status_code == 409
    body = refused.json()
    assert [b["category"] for b in body["blockers"]] == ["unsupported_satisfied_finding"]
    assert body["blockers"][0]["affected_ids"] == ["ACCESS-1b"]

    # The assessment did not move.
    assert client.get(f"/assessments/{assessment_id}").json()["status"] == "in_review"


def test_finalization_succeeds_once_blockers_are_cleared(client: TestClient) -> None:
    document_id = _ingest_sample_document(client)
    create = client.post("/assessments", json={"name": "Test", "framework_name": "C2M2"})
    assessment_id = create.json()["id"]
    client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1a"},
    )
    client.put(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1b",
        json={"status": "satisfied", "rationale": "No evidence linked for this one."},
    )
    client.post(f"/assessments/{assessment_id}/status", json={"status": "in_review"})
    assert client.post(
        f"/assessments/{assessment_id}/status", json={"status": "finalized"}
    ).status_code == 409

    # Correct the unsupported finding to one the evidence actually supports.
    client.put(
        f"/assessments/{assessment_id}/practice-findings/ACCESS-1b",
        json={"status": "not_satisfied", "rationale": "Evidence does not show this control."},
    )
    assert client.get(f"/assessments/{assessment_id}/finalization-readiness").json()["is_ready"]

    finalized = client.post(f"/assessments/{assessment_id}/status", json={"status": "finalized"})
    assert finalized.status_code == 200
    assert finalized.json()["status"] == "finalized"

    # Immutability of a finalized assessment is preserved.
    blocked = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": document_id, "practice_reference": "ACCESS-1c"},
    )
    assert blocked.status_code == 409
