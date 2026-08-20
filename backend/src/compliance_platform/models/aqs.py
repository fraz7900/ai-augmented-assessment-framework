"""Assessment-Quality Score (AQS) measurement shapes (controlled-pilot
readiness audit §F.4).

Evaluation-only, and never persisted. These are the computed outputs of
`services/aqs_service.py`'s pure measurement functions, consumed by
`scripts/measure_aqs.py`, by `services/tests/test_aqs_service.py`, and
since ADR-0070 by one read-only endpoint under `/aqs/`.

That endpoint is a deliberate, bounded change to this module's original
"never surfaced in the product itself" rule, and the rule's intent is
preserved rather than dropped. What it was protecting against is a
quality number being read as a verdict on the ASSESSMENT: an "agreement
rate" of 4% on a dashboard invites "this assessment is 4% good", which
is the same fabricated precision ADR-0012 refused for business impact.
So the measurement is namespaced under `/aqs/` as evaluation rather than
product, it is not rendered anywhere in the assessment UI, and every
result carries a sentence saying what it measures — the mapping engine's
proposals, not the reviewer and not the assessment. Deliberately three separate
result shapes rather than one combined score: each metric has a
different ground-truth requirement and a different confidence level,
and collapsing them into a single number now would fabricate a
precision this project doesn't have yet, the same discipline
ADR-0012 applied to the dashboard's business-impact score and the
scalability benchmark applied to CPES (see the audit doc §F.3).
"""

from __future__ import annotations

from pydantic import BaseModel


class AssessmentAgreementResult(BaseModel):
    """How often a human reviewer's real accept/edit/reject decision on
    an AI-proposed evidence link agreed with the proposal (i.e. was
    accepted as-is). Computable from real production review data, not
    just a labeled corpus — see
    `services/aqs_service.py.compute_assessment_agreement`.

    `agreement_rate` is None (not 0.0) when there is nothing reviewed
    yet to measure — a fresh assessment with only pending AI proposals
    has an undefined agreement rate, not a zero one.
    """

    total_ai_proposed: int
    pending: int
    accepted: int
    edited: int
    rejected: int
    agreement_rate: float | None


class AgreementByBand(BaseModel):
    """Agreement within one retrieval-confidence band (ADR-0070).

    The bands are R-16's measured structure, not round numbers: correct
    practice/evidence pairs were observed at 0.65-0.78 and incorrect ones
    at 0.43-0.53, with the live threshold at 0.55. Bucketing agreement
    this way is what turns "should we trust a high confidence score?"
    from an intuition into a question real review decisions can answer.
    """

    label: str
    min_confidence: float | None
    max_confidence: float | None
    agreement: AssessmentAgreementResult


class AssessmentAgreementReport(BaseModel):
    """Agreement overall and per confidence band, for one assessment.

    `interpretation` travels with the numbers rather than being left to
    each caller, the same discipline ADR-0012 applied to the dashboard's
    so_what sentences: a rate like this is easy to read as a score for
    the assessment, and it is a measurement of the mapping engine's
    proposals against what a human decided.
    """

    overall: AssessmentAgreementResult
    by_confidence_band: list[AgreementByBand]
    interpretation: str


class EvidencePrecisionRecallResult(BaseModel):
    """Precision/recall of the retrieval-only mapping engine's proposals
    against an expert-labeled ground-truth set of practice references
    that should have been proposed for a given evidence corpus. Requires
    a labeled corpus (see `scripts/measure_aqs.py`) — not computable
    from unlabeled production data the way AssessmentAgreementResult is.

    `precision`/`recall` are None (not 0.0) when their denominator is
    zero (no proposals made / no correct answers exist to find),
    matching AssessmentAgreementResult's None-over-zero convention.
    """

    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float | None
    recall: float | None


class UnsupportedClaimRateResult(BaseModel):
    """Always reports not-applicable in this sprint. The mission's
    Unsupported Claim Rate metric measures free-text claims a reasoner
    generates against evidence that doesn't actually support them — this
    project has no reasoner (ADR-0020: retrieval-only, permanent, not
    reopened this sprint; see the audit doc §F.1). A structural
    placeholder, not a silent omission, so a future AQS report can't be
    misread as implying a zero unsupported-claim rate when no claims
    exist to measure at all.
    """

    applicable: bool = False
    reason: str = (
        "No local reasoner is implemented (ADR-0020: retrieval-only mapping is "
        "permanent). There are no free-text claims to measure an unsupported-claim "
        "rate against. See docs/architecture/02-controlled-pilot-readiness-audit.md §F.1."
    )
