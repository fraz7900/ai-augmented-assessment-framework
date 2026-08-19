"""Bulk reject over a reviewer-selected set (ADR-0067).

A tester asked for bulk actions on the evidence queue. ADR-0065 refused
"accept all with confidence > 0.85" and, in doing so, refused the whole
category -- which was too broad. Accept and reject are not the same
operation: accepting an AI proposal creates a compliance claim that is
scored, sealed and exported, while rejecting withholds one and leaves the
practice visible as a gap. AGENTS.md rule 2 forbids auto-ACCEPTING; it
says nothing about declining.

The tests here are mostly about the boundaries that keep that true: that
no bulk accept exists anywhere, that the endpoint cannot be handed a
predicate, that a decision stays one-shot, and that a batch leaves the
same per-link audit trail as the same decisions made one at a time.
"""

from __future__ import annotations

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


def _ingest(client: TestClient) -> str:
    body = (
        "Multi factor authentication is required for all remote access to critical systems, "
        "and access reviews are performed quarterly by the security team."
    )
    response = client.post("/ingest", files={"file": ("policy.txt", body.encode(), "text/plain")})
    assert response.status_code == 200
    return response.json()["document_id"]


def _assessment(client: TestClient, name: str = "Bulk test") -> str:
    created = client.post("/assessments", json={"name": name, "framework_name": "C2M2"})
    assert created.status_code == 200
    return created.json()["id"]


def _plant_pending(assessment_id: str, document_id: str, practice: str, confidence: float) -> str:
    """An AI proposal awaiting review.

    Planted rather than produced by propose_mappings, which would run the
    real embedder and give a different queue on every run. What is under
    test is the review transition over many rows, not how a proposal
    comes to exist.
    """
    repository = dependencies.get_cached_assessment_repository()
    link = repository.add_evidence_link(
        EvidenceLink(
            assessment_id=assessment_id,
            document_id=document_id,
            practice_reference=practice,
            source=EvidenceSource.AI_PROPOSED,
            review_status=EvidenceReviewStatus.PENDING,
            confidence=confidence,
        )
    )
    return link.id


@pytest.fixture
def queue(client: TestClient) -> tuple[TestClient, str, list[str]]:
    document_id = _ingest(client)
    assessment_id = _assessment(client)
    ids = [
        _plant_pending(assessment_id, document_id, "ACCESS-1a", 0.58),
        _plant_pending(assessment_id, document_id, "ACCESS-1b", 0.62),
        _plant_pending(assessment_id, document_id, "ASSET-1a", 0.71),
        _plant_pending(assessment_id, document_id, "THREAT-1a", 0.88),
    ]
    return client, assessment_id, ids


def _bulk_reject(client: TestClient, assessment_id: str, ids: list[str], **body: object):
    return client.post(
        f"/assessments/{assessment_id}/evidence/bulk-reject",
        json={"evidence_link_ids": ids, **body},
    )


def test_rejects_every_selected_pending_link(queue) -> None:
    client, assessment_id, ids = queue

    response = _bulk_reject(client, assessment_id, ids[:3])

    assert response.status_code == 200
    assert response.json() == {"rejected_count": 3, "skipped": []}
    links = {
        link["id"]: link
        for link in client.get(f"/assessments/{assessment_id}/evidence").json()
    }
    assert [links[i]["review_status"] for i in ids[:3]] == ["rejected"] * 3
    # The one not selected is untouched. A bulk action acts on the
    # selection, never on "everything that looked similar".
    assert links[ids[3]]["review_status"] == "pending"


def test_there_is_no_bulk_accept_anywhere(queue) -> None:
    """The invariant, asserted against the live app rather than trusted.

    AGENTS.md rule 2 forbids auto-accepting an AI-proposed mapping. This
    feature exists because rejecting is a different act -- so the thing
    that must stay true is that no batch path can accept, and no
    decision field can be widened into one.
    """
    client, assessment_id, _ = queue
    paths = app.openapi()["paths"]

    bulk_paths = [path for path in paths if "bulk" in path]
    assert bulk_paths == ["/assessments/{assessment_id}/evidence/bulk-reject"]

    body_ref = paths[bulk_paths[0]]["post"]["requestBody"]["content"]["application/json"]["schema"]
    schema_name = body_ref["$ref"].rsplit("/", 1)[-1]
    fields = set(app.openapi()["components"]["schemas"][schema_name]["properties"])
    # No decision, and nothing that could select rows on the server's
    # own initiative.
    assert fields == {"evidence_link_ids", "note"}


def test_the_endpoint_cannot_be_handed_a_predicate(queue) -> None:
    """A threshold or filter here would be the number deciding, which is
    what ADR-0065 refused. Extra fields are ignored rather than honoured,
    so a caller cannot smuggle one in."""
    client, assessment_id, ids = queue

    response = client.post(
        f"/assessments/{assessment_id}/evidence/bulk-reject",
        json={"evidence_link_ids": [ids[0]], "min_confidence": 0.0, "all_matching": True},
    )

    assert response.status_code == 200
    assert response.json()["rejected_count"] == 1
    statuses = [
        link["review_status"]
        for link in client.get(f"/assessments/{assessment_id}/evidence").json()
    ]
    assert sorted(statuses) == ["pending", "pending", "pending", "rejected"]


def test_an_already_reviewed_link_is_skipped_and_reported(queue) -> None:
    """A decision is one-shot. A batch must not become a way around
    that, and a reviewer who selected 4 and moved 3 needs to know
    which one did not move."""
    client, assessment_id, ids = queue
    client.post(
        f"/assessments/{assessment_id}/evidence/{ids[0]}/review",
        json={"decision": "accepted"},
    )

    result = _bulk_reject(client, assessment_id, ids).json()

    assert result["rejected_count"] == 3
    assert result["skipped"] == [{"evidence_link_id": ids[0], "review_status": "accepted"}]
    links = {
        link["id"]: link
        for link in client.get(f"/assessments/{assessment_id}/evidence").json()
    }
    assert links[ids[0]]["review_status"] == "accepted"


def test_an_unknown_id_rejects_nothing_at_all(queue) -> None:
    """All-or-nothing for a client defect. Rejection is irreversible, so
    partially applying a batch the caller got wrong is worse than
    refusing it -- and a caller told "3 rejected" would believe it acted
    on rows it never named."""
    client, assessment_id, ids = queue

    response = _bulk_reject(client, assessment_id, [ids[0], ids[1], "not-a-real-id"])

    assert response.status_code == 404
    statuses = [
        link["review_status"]
        for link in client.get(f"/assessments/{assessment_id}/evidence").json()
    ]
    assert statuses == ["pending"] * 4


def test_another_assessments_link_cannot_be_rejected_through_this_one(client: TestClient) -> None:
    """The same boundary ADR-0063 drew for reading, applied to a write
    that takes ids from the client."""
    document_id = _ingest(client)
    mine = _assessment(client, "Mine")
    theirs = _assessment(client, "Theirs")
    their_link = _plant_pending(theirs, document_id, "ACCESS-1a", 0.6)

    response = _bulk_reject(client, mine, [their_link])

    assert response.status_code == 404
    theirs_links = client.get(f"/assessments/{theirs}/evidence").json()
    assert theirs_links[0]["review_status"] == "pending"


def test_each_rejection_records_the_actor_on_its_own_row(queue) -> None:
    """A batch leaves the same audit trail as the same decisions made one
    at a time (ADR-0061). If it did not, bulk would be a way to launder
    attribution."""
    client, assessment_id, ids = queue

    _bulk_reject(client, assessment_id, ids[:2], note="Not relevant to this practice.")

    links = {
        link["id"]: link
        for link in client.get(f"/assessments/{assessment_id}/evidence").json()
    }
    for link_id in ids[:2]:
        assert links[link_id]["reviewed_by"] is not None
        assert links[link_id]["reviewed_at"] is not None
        assert links[link_id]["note"] == "Not relevant to this practice."


def test_a_finalized_assessment_refuses_the_whole_batch(queue) -> None:
    """The finalized guard fires before anything else the batch would do.

    Reaching a finalized assessment takes clearing the queue first --
    pending AI review is itself a finalization blocker (ADR-0058) -- so
    this rejects everything, finalizes, and then tries again. The second
    call would otherwise have been an all-skipped no-op, and the point is
    that it does not get that far: a finalized record refuses the write
    rather than quietly reporting nothing happened.
    """
    client, assessment_id, ids = queue
    assert _bulk_reject(client, assessment_id, ids).json()["rejected_count"] == 4
    in_review = client.post(
        f"/assessments/{assessment_id}/status", json={"status": "in_review"}
    )
    assert in_review.status_code == 200
    finalized = client.post(f"/assessments/{assessment_id}/status", json={"status": "finalized"})
    assert finalized.status_code == 200, finalized.text

    response = _bulk_reject(client, assessment_id, ids)

    assert response.status_code == 409


def test_an_empty_selection_is_a_no_op(queue) -> None:
    client, assessment_id, _ = queue

    result = _bulk_reject(client, assessment_id, []).json()

    assert result == {"rejected_count": 0, "skipped": []}


def test_a_repeated_id_is_counted_once(queue) -> None:
    """A UI that sends the same id twice must not read back "2 rejected"
    for one row."""
    client, assessment_id, ids = queue

    result = _bulk_reject(client, assessment_id, [ids[0], ids[0]]).json()

    assert result["rejected_count"] == 1


def test_rejecting_leaves_the_practice_visible_as_a_gap(queue) -> None:
    """Why rejecting in bulk is a different risk from accepting in bulk.

    An erroneous accept fabricates a compliance claim that scores and
    gets sealed into the record. An erroneous reject withholds one, and
    the practice stays in the dashboard's gap list where the next
    reviewer will meet it again.
    """
    client, assessment_id, ids = queue

    _bulk_reject(client, assessment_id, ids)

    dashboard = client.get(f"/assessments/{assessment_id}/dashboard").json()
    gapped = {
        gap["practice_id"]
        for group in dashboard["complication"]
        for gap in group["gaps"]
    }
    assert {"ACCESS-1a", "ACCESS-1b", "ASSET-1a", "THREAT-1a"} <= gapped
    assert dashboard["situation"]["rejected_count"] == 4
