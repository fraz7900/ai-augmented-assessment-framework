"""Unit tests for services/aqs_service.py's pure measurement functions
(controlled-pilot readiness audit §F.4). No repository/API dependency —
compute_assessment_agreement takes a plain list of EvidenceLink objects,
compute_evidence_precision_recall takes plain sets.
"""

from __future__ import annotations

from compliance_platform.models.assessment import EvidenceLink, EvidenceReviewStatus, EvidenceSource
from compliance_platform.services.aqs_service import (
    compute_assessment_agreement,
    compute_evidence_precision_recall,
    unsupported_claim_rate_status,
)


def _link(source: EvidenceSource, review_status: EvidenceReviewStatus) -> EvidenceLink:
    return EvidenceLink(
        assessment_id="a1",
        document_id="d1",
        practice_reference="ACCESS-1a",
        source=source,
        review_status=review_status,
    )


class TestComputeAssessmentAgreement:
    def test_no_ai_proposed_links_returns_none_rate_not_zero(self) -> None:
        result = compute_assessment_agreement(
            [_link(EvidenceSource.MANUAL, EvidenceReviewStatus.ACCEPTED)]
        )
        assert result.total_ai_proposed == 0
        assert result.agreement_rate is None

    def test_only_pending_ai_proposals_returns_none_rate(self) -> None:
        result = compute_assessment_agreement(
            [_link(EvidenceSource.AI_PROPOSED, EvidenceReviewStatus.PENDING)]
        )
        assert result.total_ai_proposed == 1
        assert result.pending == 1
        assert result.agreement_rate is None

    def test_perfect_agreement(self) -> None:
        links = [_link(EvidenceSource.AI_PROPOSED, EvidenceReviewStatus.ACCEPTED) for _ in range(3)]
        result = compute_assessment_agreement(links)
        assert result.agreement_rate == 1.0

    def test_zero_agreement(self) -> None:
        links = [_link(EvidenceSource.AI_PROPOSED, EvidenceReviewStatus.REJECTED) for _ in range(3)]
        result = compute_assessment_agreement(links)
        assert result.agreement_rate == 0.0

    def test_edited_counts_as_disagreement_not_accepted(self) -> None:
        links = [
            _link(EvidenceSource.AI_PROPOSED, EvidenceReviewStatus.ACCEPTED),
            _link(EvidenceSource.AI_PROPOSED, EvidenceReviewStatus.EDITED),
        ]
        result = compute_assessment_agreement(links)
        assert result.accepted == 1
        assert result.edited == 1
        assert result.agreement_rate == 0.5

    def test_manual_links_excluded_from_denominator(self) -> None:
        links = [
            _link(EvidenceSource.AI_PROPOSED, EvidenceReviewStatus.ACCEPTED),
            _link(EvidenceSource.MANUAL, EvidenceReviewStatus.ACCEPTED),
            _link(EvidenceSource.MANUAL, EvidenceReviewStatus.ACCEPTED),
        ]
        result = compute_assessment_agreement(links)
        assert result.total_ai_proposed == 1
        assert result.agreement_rate == 1.0


class TestComputeEvidencePrecisionRecall:
    def test_perfect_match(self) -> None:
        result = compute_evidence_precision_recall(
            {"ACCESS-1a", "ACCESS-1b"}, {"ACCESS-1a", "ACCESS-1b"}
        )
        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.false_positives == 0
        assert result.false_negatives == 0

    def test_false_positive_lowers_precision_not_recall(self) -> None:
        result = compute_evidence_precision_recall(
            proposed_practice_references={"ACCESS-1a", "ACCESS-9z"},
            correct_practice_references={"ACCESS-1a"},
        )
        assert result.true_positives == 1
        assert result.false_positives == 1
        assert result.precision == 0.5
        assert result.recall == 1.0

    def test_false_negative_lowers_recall_not_precision(self) -> None:
        result = compute_evidence_precision_recall(
            proposed_practice_references={"ACCESS-1a"},
            correct_practice_references={"ACCESS-1a", "ACCESS-1b"},
        )
        assert result.true_positives == 1
        assert result.false_negatives == 1
        assert result.precision == 1.0
        assert result.recall == 0.5

    def test_no_proposals_returns_none_precision_not_zero(self) -> None:
        result = compute_evidence_precision_recall(set(), {"ACCESS-1a"})
        assert result.precision is None
        assert result.recall == 0.0

    def test_no_correct_answers_returns_none_recall_not_zero(self) -> None:
        result = compute_evidence_precision_recall({"ACCESS-1a"}, set())
        assert result.recall is None
        assert result.precision == 0.0

    def test_nothing_proposed_and_nothing_correct_returns_none_for_both(self) -> None:
        result = compute_evidence_precision_recall(set(), set())
        assert result.precision is None
        assert result.recall is None


def test_unsupported_claim_rate_is_explicitly_not_applicable() -> None:
    result = unsupported_claim_rate_status()
    assert result.applicable is False
    assert "ADR-0020" in result.reason
