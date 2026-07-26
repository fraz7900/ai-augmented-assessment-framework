"""Assessment-Quality Score (AQS) measurement (controlled-pilot readiness
audit §F.4). Scaffolding, not a finished statistically-significant
evaluation — see `scripts/measure_aqs.py`'s module docstring for what
that means in practice.

Two of the three AQS components the mission named are implemented here
as pure, framework-agnostic functions:

- Assessment Agreement: computable today from real production review
  data (any assessment with AI-proposed evidence links that a human has
  actually reviewed) — no labeled corpus required.
- Evidence Precision/Recall: requires an expert-labeled ground-truth
  corpus (a labeled set of "which practice references this evidence
  should have been proposed for"); `scripts/measure_aqs.py` supplies one.

The third, Unsupported Claim Rate, is not implemented — it requires a
reasoner producing free-text claims, and this project has none
(ADR-0020). `unsupported_claim_rate_status()` returns an explicit,
structural not-applicable result rather than omitting the metric
silently.
"""

from __future__ import annotations

from compliance_platform.models.aqs import (
    AssessmentAgreementResult,
    EvidencePrecisionRecallResult,
    UnsupportedClaimRateResult,
)
from compliance_platform.models.assessment import EvidenceLink, EvidenceReviewStatus, EvidenceSource


def compute_assessment_agreement(evidence_links: list[EvidenceLink]) -> AssessmentAgreementResult:
    ai_proposed = [link for link in evidence_links if link.source == EvidenceSource.AI_PROPOSED]
    pending = sum(1 for link in ai_proposed if link.review_status == EvidenceReviewStatus.PENDING)
    accepted = sum(1 for link in ai_proposed if link.review_status == EvidenceReviewStatus.ACCEPTED)
    edited = sum(1 for link in ai_proposed if link.review_status == EvidenceReviewStatus.EDITED)
    rejected = sum(1 for link in ai_proposed if link.review_status == EvidenceReviewStatus.REJECTED)
    reviewed = accepted + edited + rejected

    return AssessmentAgreementResult(
        total_ai_proposed=len(ai_proposed),
        pending=pending,
        accepted=accepted,
        edited=edited,
        rejected=rejected,
        agreement_rate=(accepted / reviewed) if reviewed > 0 else None,
    )


def compute_evidence_precision_recall(
    proposed_practice_references: set[str],
    correct_practice_references: set[str],
) -> EvidencePrecisionRecallResult:
    """`proposed_practice_references`: every practice reference the
    retrieval engine actually proposed evidence for, for one document
    (or one evidence corpus, at the caller's choice of granularity).
    `correct_practice_references`: the expert-labeled ground truth of
    which practice references that same evidence should have been
    proposed for. Pure set comparison — no I/O, no framework knowledge,
    so it works identically regardless of which framework the labeled
    corpus targets.
    """
    true_positives = len(proposed_practice_references & correct_practice_references)
    false_positives = len(proposed_practice_references - correct_practice_references)
    false_negatives = len(correct_practice_references - proposed_practice_references)

    precision_denominator = true_positives + false_positives
    recall_denominator = true_positives + false_negatives

    return EvidencePrecisionRecallResult(
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=(true_positives / precision_denominator) if precision_denominator > 0 else None,
        recall=(true_positives / recall_denominator) if recall_denominator > 0 else None,
    )


def unsupported_claim_rate_status() -> UnsupportedClaimRateResult:
    return UnsupportedClaimRateResult()
