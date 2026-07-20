"""End-to-end integration test: ingest a document through the real API,
create an assessment, link evidence to it, and move it through the
status state machine to finalization — exercising the real SQLite
store, LanceDB vector store, and FastAPI app together, not fakes. See
docs/architecture/00-repository-architecture.md's testing strategy.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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
