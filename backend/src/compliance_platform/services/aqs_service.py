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
    AgreementByBand,
    AssessmentAgreementReport,
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


# The bands R-16 measured, not round numbers. Correct practice/evidence
# pairs were observed at 0.65-0.78 and incorrect ones at 0.43-0.53, with
# the live mapping threshold at 0.55 -- so these boundaries are where the
# evidence actually is, and the top band is deliberately open-ended
# because nothing correct has ever been observed above 0.78.
_CONFIDENCE_BANDS: list[tuple[str, float | None, float | None]] = [
    ("Below the live threshold (< 0.55)", None, 0.55),
    ("Borderline (0.55-0.65)", 0.55, 0.65),
    ("Measured-correct band (0.65-0.78)", 0.65, 0.78),
    ("Above any measured correct match (> 0.78)", 0.78, None),
]

_INTERPRETATION = (
    "Agreement measures how often a human accepted an AI proposal as-is. It is a "
    "measurement of the mapping engine's proposals, not a quality score for this "
    "assessment and not a rating of the reviewer -- a low rate on a corpus where "
    "most proposals are wrong is the reviewer working correctly. Confidence is a "
    "retrieval similarity, not a calibrated probability (ADR-0011, R-16)."
)


def _in_band(confidence: float | None, low: float | None, high: float | None) -> bool:
    """Half-open on the upper bound so the bands partition without
    double-counting a link sitting exactly on a boundary."""
    if confidence is None:
        return False
    if low is not None and confidence < low:
        return False
    return not (high is not None and confidence >= high)


def compute_agreement_by_confidence_band(
    evidence_links: list[EvidenceLink],
) -> list[AgreementByBand]:
    """Agreement bucketed by the confidence the engine proposed at
    (ADR-0070).

    This is the measurement that a bulk-accept decision would need and
    that nothing in this project has ever had: whether a human actually
    accepts more of what scored higher. ADR-0065 declined a
    threshold-selected bulk accept partly because no such data existed;
    this is how it stops not existing.

    Every band is returned, including empty ones. A band nobody has
    reviewed yet is a real and useful answer -- "no evidence about the
    top band" is exactly the state R-16 describes, and omitting it would
    make an unmeasured band look like a band that does not occur.
    """
    return [
        AgreementByBand(
            label=label,
            min_confidence=low,
            max_confidence=high,
            agreement=compute_assessment_agreement(
                [link for link in evidence_links if _in_band(link.confidence, low, high)]
            ),
        )
        for label, low, high in _CONFIDENCE_BANDS
    ]


def build_agreement_report(evidence_links: list[EvidenceLink]) -> AssessmentAgreementReport:
    return AssessmentAgreementReport(
        overall=compute_assessment_agreement(evidence_links),
        by_confidence_band=compute_agreement_by_confidence_band(evidence_links),
        interpretation=_INTERPRETATION,
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
