"""Assessment-Quality Score (AQS) measurement shapes (controlled-pilot
readiness audit §F.4).

Evaluation-only — never persisted, never surfaced in the product itself.
These are the computed outputs of `services/aqs_service.py`'s pure
measurement functions, consumed by `scripts/measure_aqs.py` and by
`services/tests/test_aqs_service.py`. Deliberately three separate
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
