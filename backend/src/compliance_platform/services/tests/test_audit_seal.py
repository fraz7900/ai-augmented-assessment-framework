"""Unit tests for the finalization seal's canonical form.

The seal's only job is to answer "has this record changed since it was
finalized" — so these tests come in two halves, and the second half
matters at least as much as the first. A digest that misses a real
change is useless; a digest that reports a change nobody made is worse
than useless, because the one time it matters, nobody will believe it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from compliance_platform.models.assessment import (
    Assessment,
    AssessmentStatus,
    AssessmentStatusChange,
    EvidenceLink,
    EvidenceRequest,
    EvidenceReviewStatus,
    EvidenceSource,
    PracticeFinding,
    PracticeFindingChange,
    PracticeFindingStatus,
)
from compliance_platform.services import audit_seal

_WHEN = datetime(2026, 8, 18, 12, 0, 0, tzinfo=UTC)


def _assessment() -> Assessment:
    return Assessment(
        id="a-1",
        name="Q3 C2M2 Self Assessment",
        framework_name="C2M2",
        framework_version="2.1",
        status=AssessmentStatus.FINALIZED,
        created_at=_WHEN,
        updated_at=_WHEN,
    )


def _link(link_id: str = "l-1", **overrides: object) -> EvidenceLink:
    defaults = {
        "id": link_id,
        "assessment_id": "a-1",
        "document_id": "d-1",
        "practice_reference": "ASSET-1a",
        "source": EvidenceSource.MANUAL,
        "review_status": EvidenceReviewStatus.ACCEPTED,
        "created_at": _WHEN,
    }
    return EvidenceLink(**{**defaults, **overrides})  # type: ignore[arg-type]


def _finding(**overrides: object) -> PracticeFinding:
    defaults = {
        "id": "f-1",
        "assessment_id": "a-1",
        "practice_reference": "ASSET-1a",
        "status": PracticeFindingStatus.SATISFIED,
        "rationale": "Asset inventory policy accepted as evidence.",
        "created_at": _WHEN,
        "updated_at": _WHEN,
    }
    return PracticeFinding(**{**defaults, **overrides})  # type: ignore[arg-type]


def _seal(**overrides: object) -> str:
    record = {
        "assessment": _assessment(),
        "status_history": [
            AssessmentStatusChange(
                assessment_id="a-1",
                from_status=AssessmentStatus.IN_REVIEW,
                to_status=AssessmentStatus.FINALIZED,
                changed_at=_WHEN,
            )
        ],
        "evidence_links": [_link()],
        "practice_findings": [_finding()],
        "practice_finding_history": [
            PracticeFindingChange(
                assessment_id="a-1",
                practice_reference="ASSET-1a",
                from_status=None,
                to_status=PracticeFindingStatus.SATISFIED,
                rationale="Asset inventory policy accepted as evidence.",
                changed_at=_WHEN,
            )
        ],
        "evidence_requests": [],
    }
    record.update(overrides)
    return audit_seal.compute_seal(**record)  # type: ignore[arg-type]


# --- it must notice a real change -------------------------------------


def test_the_same_record_always_produces_the_same_digest() -> None:
    assert _seal() == _seal()


def test_an_edited_rationale_changes_the_digest() -> None:
    # The single most likely thing someone would quietly rewrite.
    altered = _seal(
        practice_findings=[_finding(rationale="Confirmed verbally with the CISO.")]
    )
    assert altered != _seal()


def test_a_changed_review_decision_changes_the_digest() -> None:
    altered = _seal(evidence_links=[_link(review_status=EvidenceReviewStatus.REJECTED)])
    assert altered != _seal()


def test_a_removed_evidence_link_changes_the_digest() -> None:
    assert _seal(evidence_links=[]) != _seal()


def test_an_inserted_history_row_changes_the_digest() -> None:
    extra = PracticeFindingChange(
        assessment_id="a-1",
        practice_reference="ACCESS-2b",
        to_status=PracticeFindingStatus.SATISFIED,
        rationale="Backdated.",
        changed_at=_WHEN,
    )
    assert _seal(practice_finding_history=[extra]) != _seal()


def test_an_added_evidence_request_changes_the_digest() -> None:
    # An open request is part of the record: it is what shows a reviewer
    # asked for something and what came of it, and ADR-0058 blocks
    # finalization while any remain unresolved.
    request = EvidenceRequest(
        assessment_id="a-1",
        practice_reference="ACCESS-2b",
        note="Please provide the current access review export.",
        requested_by="priya",
        requested_at=_WHEN,
    )
    assert _seal(evidence_requests=[request]) != _seal()


def test_a_shifted_timestamp_changes_the_digest() -> None:
    assert _seal(evidence_links=[_link(created_at=_WHEN + timedelta(seconds=1))]) != _seal()


def test_reordered_history_changes_the_digest() -> None:
    # Order is part of what an append-only trail attests to: "we thought
    # X, then Y" and "we thought Y, then X" are different claims.
    first = PracticeFindingChange(
        assessment_id="a-1",
        practice_reference="ASSET-1a",
        to_status=PracticeFindingStatus.NOT_SATISFIED,
        rationale="No inventory found.",
        changed_at=_WHEN,
    )
    second = PracticeFindingChange(
        assessment_id="a-1",
        practice_reference="ASSET-1a",
        from_status=PracticeFindingStatus.NOT_SATISFIED,
        to_status=PracticeFindingStatus.SATISFIED,
        rationale="Inventory provided.",
        changed_at=_WHEN + timedelta(hours=1),
    )
    assert _seal(practice_finding_history=[first, second]) != _seal(
        practice_finding_history=[second, first]
    )


# --- it must not cry wolf ---------------------------------------------


def test_an_aware_and_a_naive_timestamp_seal_identically() -> None:
    """The failure this feature would most plausibly have shipped with.

    The models default to timezone-aware UTC, SQLite stores no offset,
    so the same row read back is naive. Sealing from memory and
    verifying from the database would then disagree about a record
    nobody touched.
    """
    naive = _WHEN.replace(tzinfo=None)
    assert _seal(evidence_links=[_link(created_at=naive)]) == _seal()


def test_the_same_instant_in_another_zone_seals_identically() -> None:
    elsewhere = _WHEN.astimezone(timezone(timedelta(hours=5, minutes=30)))
    assert _seal(evidence_links=[_link(created_at=elsewhere)]) == _seal()


def test_link_order_does_not_change_the_digest() -> None:
    # Unlike history, a set of links has no inherent order — only
    # whatever the query happened to return, which must not be able to
    # make an untouched record look altered.
    a, b = _link("l-1"), _link("l-2", practice_reference="ACCESS-2b")
    assert _seal(evidence_links=[a, b]) == _seal(evidence_links=[b, a])


def test_the_assessments_updated_at_is_not_sealed() -> None:
    # Storing the seal updates the row. If updated_at were covered, no
    # seal could ever verify against the record it sealed.
    later = _assessment()
    later.updated_at = _WHEN + timedelta(days=30)
    assert _seal(assessment=later) == _seal()


def test_the_seal_fields_themselves_are_not_sealed() -> None:
    already_sealed = _assessment()
    already_sealed.sealed_digest = "deadbeef"
    already_sealed.sealed_at = _WHEN
    already_sealed.seal_version = "1"
    assert _seal(assessment=already_sealed) == _seal()


# --- attribution is sealed too (v2) -----------------------------------


def test_a_reassigned_reviewer_changes_the_digest() -> None:
    # Attribution has to be sealed or it is not worth much: a record
    # whose reviewer can be silently swapped answers "who decided this"
    # no better than one that never recorded it (ADR-0061).
    assert _seal(evidence_links=[_link(reviewed_by="someone.else")]) != _seal(
        evidence_links=[_link(reviewed_by="priya")]
    )


def test_a_rewritten_finalizer_changes_the_digest() -> None:
    frozen_by_priya = AssessmentStatusChange(
        assessment_id="a-1",
        from_status=AssessmentStatus.IN_REVIEW,
        to_status=AssessmentStatus.FINALIZED,
        changed_at=_WHEN,
        actor="priya",
    )
    frozen_by_someone_else = AssessmentStatusChange(
        assessment_id="a-1",
        from_status=AssessmentStatus.IN_REVIEW,
        to_status=AssessmentStatus.FINALIZED,
        changed_at=_WHEN,
        actor="marcus",
    )
    assert _seal(status_history=[frozen_by_priya]) != _seal(
        status_history=[frozen_by_someone_else]
    )


def test_version_1_ignores_the_actor_fields_it_predates() -> None:
    # An old seal must keep verifying. Version 1 was written before
    # these columns existed, so its payload cannot depend on them --
    # otherwise every pre-ADR-0061 seal would start reporting a record
    # nobody touched as altered.
    with_actor = _seal(evidence_links=[_link(reviewed_by="priya")], version="1")
    without = _seal(evidence_links=[_link()], version="1")
    assert with_actor == without


def test_version_2_is_the_one_written_today() -> None:
    assert audit_seal.CURRENT_SEAL_VERSION == "2"
    assert _seal() == _seal(version="2")


# --- version handling -------------------------------------------------


def test_an_unknown_seal_version_is_refused_rather_than_guessed() -> None:
    # A build that cannot rebuild the payload the way a newer one did
    # must say so, not compute a different digest and call the record
    # altered.
    with pytest.raises(audit_seal.UnknownSealVersionError):
        _seal(version="99")
