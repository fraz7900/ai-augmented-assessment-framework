"""Filtering the evidence review queue (ADR-0065).

A tester reported that going through evidence links one at a time is
unmanageable. The queue really is unfilterable today -- GET
/assessments/{id}/evidence returns every link with no parameters -- so
these tests cover the narrowing, against the real API, the real SQLite
database and the real C2M2 definition, because domain membership comes
from framework_mapping/*.yaml and a mocked framework would prove
nothing about it.

Two properties matter more than the filtering itself, and have tests of
their own below: the summary counts never move when a filter is applied
(a filtered total cannot tell a reviewer what they are not looking at),
and a link whose practice is not in the pinned framework is counted as
unmapped rather than disappearing.
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


def _ingest(client: TestClient, filename: str) -> str:
    body = (
        "Multi factor authentication is required for all remote access to critical systems, "
        "and access reviews are performed quarterly by the security team."
    )
    response = client.post("/ingest", files={"file": (filename, body.encode(), "text/plain")})
    assert response.status_code == 200
    return response.json()["document_id"]


def _assessment(client: TestClient) -> str:
    created = client.post("/assessments", json={"name": "Filter test", "framework_name": "C2M2"})
    assert created.status_code == 200
    return created.json()["id"]


def _link(client: TestClient, assessment_id: str, document_id: str, practice: str) -> str:
    response = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={
            "document_id": document_id,
            "practice_reference": practice,
            "source": "manual",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _review(client: TestClient, assessment_id: str, link_id: str, decision: str) -> None:
    response = client.post(
        f"/assessments/{assessment_id}/evidence/{link_id}/review",
        json={"decision": decision},
    )
    assert response.status_code == 200, response.text


def _plant_proposal(
    assessment_id: str,
    document_id: str,
    practice: str,
    confidence: float,
) -> None:
    """Insert an AI-proposed link awaiting review.

    Planted rather than produced by calling propose_mappings, which
    would run the real embedder against the real vector store and give
    these tests a different number of links on every run. What is under
    test here is the filtering of a queue, not how a proposal comes to
    be in it, so a deterministic queue is the honest fixture -- the
    mapping engine has its own tests.
    """
    repository = dependencies.get_cached_assessment_repository()
    repository.add_evidence_link(
        EvidenceLink(
            assessment_id=assessment_id,
            document_id=document_id,
            practice_reference=practice,
            source=EvidenceSource.AI_PROPOSED,
            review_status=EvidenceReviewStatus.PENDING,
            confidence=confidence,
        )
    )


def _plant_unmapped_link(assessment_id: str, document_id: str) -> None:
    """Insert a link whose practice the pinned framework does not know.

    Planted through the repository rather than the API on purpose: the
    API validates practice_reference against the framework and refuses
    this (422), so the case is unreachable for anything created today.
    It is still reachable in a real database -- rows predating that
    validation, and rows whose practice left the framework data under a
    pinned version. Those rows are exactly what the unmapped count
    exists to keep visible, so the test has to produce one the way
    reality does rather than the way the API would.
    """
    repository = dependencies.get_cached_assessment_repository()
    repository.add_evidence_link(
        EvidenceLink(
            assessment_id=assessment_id,
            document_id=document_id,
            practice_reference="LEGACY-99z",
            review_status=EvidenceReviewStatus.ACCEPTED,
        )
    )


@pytest.fixture
def populated(client: TestClient) -> tuple[TestClient, str]:
    """A queue with the shape a reviewer actually meets.

    Five accepted manual links across two C2M2 domains, three
    AI-proposed links still pending across three domains and spanning
    the confidence band R-16 measured, and one row whose practice the
    framework does not know. Nine links, four review states' worth of
    reasons to filter.
    """
    document_id = _ingest(client, "policy.txt")
    assessment_id = _assessment(client)
    # Manual links land ACCEPTED on creation -- a human chose them.
    for practice in ("ACCESS-1a", "ACCESS-1b", "ACCESS-1c"):
        _link(client, assessment_id, document_id, practice)
    for practice in ("ASSET-1a", "ASSET-1b"):
        _link(client, assessment_id, document_id, practice)
    # Confidences chosen from R-16's measured bands rather than at
    # random: 0.62 sits between the incorrect and correct ranges, 0.71
    # is the exact score of the confirmed ASSET-1a false positive, and
    # 0.88 is above anything ever observed to be correct.
    _plant_proposal(assessment_id, document_id, "ACCESS-2a", 0.62)
    _plant_proposal(assessment_id, document_id, "ASSET-1c", 0.71)
    _plant_proposal(assessment_id, document_id, "THREAT-1a", 0.88)
    _plant_unmapped_link(assessment_id, document_id)
    return client, assessment_id


def test_the_unfiltered_call_is_unchanged(populated: tuple[TestClient, str]) -> None:
    """The filters are additive. An existing caller passing nothing must
    see exactly what it saw before this feature existed."""
    client, assessment_id = populated

    links = client.get(f"/assessments/{assessment_id}/evidence").json()

    assert len(links) == 9
    assert isinstance(links, list)
    assert {"id", "practice_reference", "review_status"} <= links[0].keys()


def test_filters_by_domain_using_the_pinned_framework(
    populated: tuple[TestClient, str],
) -> None:
    client, assessment_id = populated

    access = client.get(f"/assessments/{assessment_id}/evidence?domain=ACCESS").json()

    assert {link["practice_reference"] for link in access} == {
        "ACCESS-1a",
        "ACCESS-1b",
        "ACCESS-1c",
        "ACCESS-2a",
    }


def test_filters_by_review_status(populated: tuple[TestClient, str]) -> None:
    client, assessment_id = populated

    pending = client.get(f"/assessments/{assessment_id}/evidence?review_status=pending").json()
    accepted = client.get(f"/assessments/{assessment_id}/evidence?review_status=accepted").json()

    assert len(pending) == 3
    assert all(link["source"] == "ai_proposed" for link in pending)
    assert len(accepted) == 6


def test_status_filter_follows_a_real_review_decision(
    populated: tuple[TestClient, str],
) -> None:
    """The filter has to reflect the queue after a person works it, not
    just at rest."""
    client, assessment_id = populated
    pending = client.get(f"/assessments/{assessment_id}/evidence?review_status=pending").json()

    _review(client, assessment_id, pending[0]["id"], "rejected")

    still_pending = client.get(
        f"/assessments/{assessment_id}/evidence?review_status=pending"
    ).json()
    assert len(still_pending) == 2
    rejected = client.get(f"/assessments/{assessment_id}/evidence?review_status=rejected").json()
    assert [link["id"] for link in rejected] == [pending[0]["id"]]


def test_domain_and_status_compose(populated: tuple[TestClient, str]) -> None:
    client, assessment_id = populated

    both = client.get(
        f"/assessments/{assessment_id}/evidence?domain=ACCESS&review_status=pending"
    ).json()

    assert [link["practice_reference"] for link in both] == ["ACCESS-2a"]


def test_an_unknown_domain_returns_nothing_rather_than_everything(
    populated: tuple[TestClient, str],
) -> None:
    """The failure mode that would matter. A filter that silently
    degrades to "no filter" looks like it worked and shows a reviewer
    another domain's queue."""
    client, assessment_id = populated

    assert client.get(f"/assessments/{assessment_id}/evidence?domain=NOPE").json() == []


def test_a_practice_outside_the_framework_matches_no_domain_filter(
    populated: tuple[TestClient, str],
) -> None:
    client, assessment_id = populated

    for domain in ("ACCESS", "ASSET", "THREAT"):
        returned = client.get(f"/assessments/{assessment_id}/evidence?domain={domain}").json()
        assert "LEGACY-99z" not in {link["practice_reference"] for link in returned}


def test_confidence_filter_excludes_manual_links_rather_than_zeroing_them(
    populated: tuple[TestClient, str],
) -> None:
    """A manual link has no confidence because a human chose it, not
    because retrieval scored it badly. Treating None as 0.0 would file
    every human decision at the bottom of a quality filter."""
    client, assessment_id = populated

    at_or_above_zero = client.get(
        f"/assessments/{assessment_id}/evidence?min_confidence=0.0"
    ).json()

    assert len(at_or_above_zero) == 3
    assert all(link["source"] == "ai_proposed" for link in at_or_above_zero)


def test_confidence_band_narrows_to_the_requested_range(
    populated: tuple[TestClient, str],
) -> None:
    client, assessment_id = populated

    band = client.get(
        f"/assessments/{assessment_id}/evidence?min_confidence=0.65&max_confidence=0.8"
    ).json()

    assert [link["practice_reference"] for link in band] == ["ASSET-1c"]


def test_the_band_above_every_measured_correct_match_is_nearly_empty(
    populated: tuple[TestClient, str],
) -> None:
    """Not a filtering edge case -- the reason the bulk-accept request
    this filter shipped instead of was declined.

    R-16 records correct practice/evidence pairs at 0.65-0.78 and a
    confirmed false positive at 0.71. A 0.85 cutoff therefore sits above
    everything ever observed to be correct, and this fixture shows what
    that selects: one link, whose score says nothing about whether it is
    right, because nobody has measured that band.
    """
    client, assessment_id = populated

    above = client.get(f"/assessments/{assessment_id}/evidence?min_confidence=0.85").json()

    assert [link["practice_reference"] for link in above] == ["THREAT-1a"]
    assert above[0]["review_status"] == "pending"


def test_confidence_bounds_are_validated(populated: tuple[TestClient, str]) -> None:
    client, assessment_id = populated

    too_high = client.get(f"/assessments/{assessment_id}/evidence?min_confidence=1.5")
    assert too_high.status_code == 422
    assert (
        client.get(f"/assessments/{assessment_id}/evidence?min_confidence=-0.1").status_code == 422
    )


def test_summary_counts_the_whole_queue(populated: tuple[TestClient, str]) -> None:
    client, assessment_id = populated

    summary = client.get(f"/assessments/{assessment_id}/evidence/summary").json()

    assert summary["total"] == 9
    assert summary["by_status"]["accepted"] == 6
    assert summary["by_status"]["pending"] == 3
    assert summary["by_status"]["rejected"] == 0
    by_domain = {entry["short_code"]: entry for entry in summary["by_domain"]}
    assert by_domain["ACCESS"]["total"] == 4
    assert by_domain["ASSET"]["total"] == 3
    assert by_domain["THREAT"]["total"] == 1
    assert by_domain["ACCESS"]["full_name"] == "Identity and Access Management"


def test_summary_reports_links_no_domain_filter_can_reach(
    populated: tuple[TestClient, str],
) -> None:
    """The disclosure that makes the domain filter honest. LEGACY-99z is
    in the queue and in no domain, so a reviewer working domain by
    domain would never see it -- the count says so out loud."""
    client, assessment_id = populated

    summary = client.get(f"/assessments/{assessment_id}/evidence/summary").json()

    assert summary["unmapped"] == 1
    assert sum(entry["total"] for entry in summary["by_domain"]) == summary["total"] - 1


def test_summary_does_not_move_when_a_filter_is_applied(
    populated: tuple[TestClient, str],
) -> None:
    """A filtered total cannot tell a reviewer what they are not looking
    at, so the summary deliberately accepts no filter parameters and
    ignores any that are passed."""
    client, assessment_id = populated

    before = client.get(f"/assessments/{assessment_id}/evidence/summary").json()
    client.get(f"/assessments/{assessment_id}/evidence?domain=ACCESS").json()
    after = client.get(
        f"/assessments/{assessment_id}/evidence/summary?domain=ACCESS&review_status=pending"
    ).json()

    assert before == after
    assert after["total"] == 9


def test_summary_omits_domains_with_nothing_in_the_queue(
    populated: tuple[TestClient, str],
) -> None:
    """C2M2 has ten domains and this queue touches three. A chooser
    offering seven empty ones is a worse chooser."""
    client, assessment_id = populated

    summary = client.get(f"/assessments/{assessment_id}/evidence/summary").json()

    assert {entry["short_code"] for entry in summary["by_domain"]} == {
        "ACCESS",
        "ASSET",
        "THREAT",
    }


def test_pending_counts_per_domain_track_review_progress(
    populated: tuple[TestClient, str],
) -> None:
    """What the filter control is actually for: seeing where the
    unreviewed work is before deciding where to spend an hour."""
    client, assessment_id = populated
    access_pending = client.get(
        f"/assessments/{assessment_id}/evidence?domain=ACCESS&review_status=pending"
    ).json()
    _review(client, assessment_id, access_pending[0]["id"], "accepted")

    summary = client.get(f"/assessments/{assessment_id}/evidence/summary").json()
    by_domain = {entry["short_code"]: entry for entry in summary["by_domain"]}

    assert by_domain["ACCESS"]["total"] == 4
    assert by_domain["ACCESS"]["pending"] == 0
    assert by_domain["THREAT"]["pending"] == 1
    assert summary["by_status"]["pending"] == 2


def test_filtering_never_changes_a_record(populated: tuple[TestClient, str]) -> None:
    """The property that makes filters safe to ship without the bulk
    actions that were requested alongside them (ADR-0065)."""
    client, assessment_id = populated
    before = client.get(f"/assessments/{assessment_id}/evidence").json()

    for query in (
        "?domain=ACCESS",
        "?review_status=pending",
        "?domain=ASSET&review_status=accepted",
        "?min_confidence=0.9",
    ):
        client.get(f"/assessments/{assessment_id}/evidence{query}")

    after = client.get(f"/assessments/{assessment_id}/evidence").json()
    assert before == after
