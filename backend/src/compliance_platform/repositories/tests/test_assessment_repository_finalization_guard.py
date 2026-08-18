"""The finalized-assessment write lock, enforced at the repository layer.

R-12 has been open since Sprint 2: "nothing outside AssessmentService
prevents a direct-repository call from bypassing the finalized-assessment
evidence lock." Every test here is that sentence made executable — each
one calls a repository write method directly, with no service involved,
against a finalized assessment.

There is a second reason the check moved into the write's own
transaction, which these tests cover less directly: the service reads
the status in one session and writes in another, so an assessment
finalized between the two was written to anyway. See
AssessmentRepository._assert_writable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from compliance_platform.core.errors import AssessmentFinalizedError
from compliance_platform.models.assessment import (
    Assessment,
    AssessmentStatus,
    EvidenceLink,
    EvidenceRequest,
    EvidenceReviewStatus,
    EvidenceSource,
    PracticeFindingStatus,
    SanitizationApproval,
)
from compliance_platform.repositories.assessment_repository import AssessmentRepository


def _repo(tmp_path: Path) -> AssessmentRepository:
    return AssessmentRepository(tmp_path / "assessments.db")


def _draft(repo: AssessmentRepository) -> Assessment:
    return repo.create_assessment(name="Pilot", framework_name="C2M2")


def _finalize(repo: AssessmentRepository, assessment: Assessment) -> None:
    # Via the repository, deliberately: transition_status is the one
    # write that must still be allowed to reach FINALIZED, and doing it
    # here proves the guard does not block its own precondition.
    repo.update_status(assessment.id, AssessmentStatus.FINALIZED)


def _link(assessment_id: str) -> EvidenceLink:
    return EvidenceLink(
        assessment_id=assessment_id,
        document_id="doc-1",
        practice_reference="AM-1a",
        source=EvidenceSource.AI_PROPOSED,
        review_status=EvidenceReviewStatus.PENDING,
    )


def _request(assessment_id: str) -> EvidenceRequest:
    return EvidenceRequest(
        assessment_id=assessment_id,
        practice_reference="AM-1a",
        note="Please provide the current asset inventory spreadsheet.",
        requested_by="priya",
    )


# --- the bypass R-12 describes ---------------------------------------


def test_add_evidence_link_is_refused_on_a_finalized_assessment(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assessment = _draft(repo)
    _finalize(repo, assessment)

    with pytest.raises(AssessmentFinalizedError):
        repo.add_evidence_link(_link(assessment.id))

    assert repo.evidence_for_assessment(assessment.id) == []


def test_review_of_an_existing_link_is_refused_on_a_finalized_assessment(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    assessment = _draft(repo)
    link = repo.add_evidence_link(_link(assessment.id))
    _finalize(repo, assessment)

    with pytest.raises(AssessmentFinalizedError):
        repo.update_evidence_link_review(link.id, review_status=EvidenceReviewStatus.ACCEPTED)

    # The whole point of freezing the record: the stored decision is
    # still the one that was there when it was frozen.
    unchanged = repo.get_evidence_link(link.id)
    assert unchanged is not None
    assert unchanged.review_status == EvidenceReviewStatus.PENDING


def test_set_practice_finding_is_refused_on_a_finalized_assessment(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assessment = _draft(repo)
    _finalize(repo, assessment)

    with pytest.raises(AssessmentFinalizedError):
        repo.set_practice_finding(
            assessment_id=assessment.id,
            practice_reference="AM-1a",
            status=PracticeFindingStatus.SATISFIED,
            rationale="Confirmed with the CISO.",
        )

    assert repo.practice_findings_for_assessment(assessment.id) == []


def test_creating_an_evidence_request_is_refused_on_a_finalized_assessment(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    assessment = _draft(repo)
    _finalize(repo, assessment)

    with pytest.raises(AssessmentFinalizedError):
        repo.create_evidence_request(_request(assessment.id))

    assert repo.evidence_requests_for_assessment(assessment.id) == []


def test_resolving_an_evidence_request_is_refused_on_a_finalized_assessment(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    assessment = _draft(repo)
    request = repo.create_evidence_request(_request(assessment.id))
    _finalize(repo, assessment)

    with pytest.raises(AssessmentFinalizedError):
        repo.resolve_evidence_request(request.id, resolved_by="priya")

    still_open = repo.get_evidence_request(request.id)
    assert still_open is not None
    assert still_open.resolved_at is None


def test_the_status_is_read_at_write_time_not_when_the_row_was_built(
    tmp_path: Path,
) -> None:
    """The closest expression of the check-then-act window in a
    single-threaded test: the object is constructed while the assessment
    is still a draft, and finalized before the write is attempted. A
    guard that trusted state captured earlier would let this through —
    which is exactly what the service-layer check does across its two
    separate sessions.
    """
    repo = _repo(tmp_path)
    assessment = _draft(repo)
    pending_write = _link(assessment.id)

    _finalize(repo, assessment)

    with pytest.raises(AssessmentFinalizedError):
        repo.add_evidence_link(pending_write)


# --- the guard must not over-block ------------------------------------


def test_every_guarded_write_still_works_on_a_draft_assessment(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assessment = _draft(repo)

    link = repo.add_evidence_link(_link(assessment.id))
    reviewed = repo.update_evidence_link_review(
        link.id, review_status=EvidenceReviewStatus.ACCEPTED
    )
    finding = repo.set_practice_finding(
        assessment_id=assessment.id,
        practice_reference="AM-1a",
        status=PracticeFindingStatus.SATISFIED,
        rationale="Asset inventory policy accepted as evidence.",
    )
    request = repo.create_evidence_request(_request(assessment.id))
    resolved = repo.resolve_evidence_request(request.id, resolved_by="priya")

    assert reviewed is not None and reviewed.review_status == EvidenceReviewStatus.ACCEPTED
    assert finding.status == PracticeFindingStatus.SATISFIED
    assert resolved is not None and resolved.resolved_at is not None


def test_finalizing_is_still_allowed(tmp_path: Path) -> None:
    # update_status is deliberately unguarded: it has to be able to
    # reach FINALIZED, and the state machine already makes that state
    # terminal (services/assessment_service.py's _ALLOWED_TRANSITIONS).
    repo = _repo(tmp_path)
    assessment = _draft(repo)

    finalized = repo.update_status(assessment.id, AssessmentStatus.FINALIZED)

    assert finalized is not None
    assert finalized.status == AssessmentStatus.FINALIZED


def test_sanitization_approval_is_still_allowed_after_finalization(tmp_path: Path) -> None:
    # Deliberately outside the guard, matching AssessmentService, which
    # does not block it either: approving a sanitized export of a
    # finalized assessment adds no claim to the audit record — it
    # records permission to share what the record already says. Sharing
    # a finished assessment externally is a normal thing to do with one.
    repo = _repo(tmp_path)
    assessment = _draft(repo)
    _finalize(repo, assessment)

    approval = repo.create_sanitization_approval(
        SanitizationApproval(
            assessment_id=assessment.id,
            sanitized_content_hash="abc123",
            custom_terms_json="[]",
            approved_by="priya",
        )
    )

    assert repo.latest_sanitization_approval(assessment.id) is not None
    assert approval.approved_by == "priya"


def test_a_write_for_an_unknown_assessment_behaves_as_it_did_before(tmp_path: Path) -> None:
    # There is no lock to enforce on an assessment that does not exist,
    # and the service raises AssessmentNotFoundError long before this
    # point. The guard deliberately does not invent a second opinion.
    repo = _repo(tmp_path)

    created = repo.add_evidence_link(_link("no-such-assessment"))

    assert created.assessment_id == "no-such-assessment"
