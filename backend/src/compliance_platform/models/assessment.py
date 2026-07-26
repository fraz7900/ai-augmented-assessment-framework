"""SQLModel entities for the assessment engine (Sprint 2).

Distinct from models/schemas.py (Sprint 1's plain Pydantic ingestion
schemas): these classes are both Pydantic validation models AND
SQLAlchemy table definitions, per ADR-0007. Persisted via
repositories/assessment_repository.py — services/ must never import
sqlmodel or open a database session directly (repositories/README.md).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel, UniqueConstraint


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AssessmentStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    FINALIZED = "finalized"


class EvidenceSource(StrEnum):
    MANUAL = "manual"
    AI_PROPOSED = "ai_proposed"


class EvidenceReviewStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"


class PracticeFindingStatus(StrEnum):
    """A human reviewer's explicit compliance judgment for one practice,
    distinct from EvidenceReviewStatus (which judges a single proposed
    evidence-to-practice LINK, not the practice's overall compliance
    state). Exists to close a real, confirmed scoring gap: without this,
    "no evidence has been linked yet" and "evidence was reviewed and
    shown the control is absent" both collapse to the same "not in
    performed_practice_ids" outcome in services/scoring_service.py — see
    ADR-0030.
    """

    SATISFIED = "satisfied"
    PARTIALLY_SATISFIED = "partially_satisfied"
    NOT_SATISFIED = "not_satisfied"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_APPLICABLE = "not_applicable"


class Assessment(SQLModel, table=True):
    """A single compliance assessment instance.

    framework_name is a free-text label (e.g. "C2M2") in Sprint 2 — not
    yet validated against a structured framework schema, since
    framework_mapping/ data does not exist until Sprint 3-4. See
    services/assessment_service.py and the framework-mapping skill.
    """

    id: str = Field(default_factory=_new_id, primary_key=True)
    name: str
    framework_name: str
    # The loaded FrameworkDefinition.version at the moment this
    # assessment was created (e.g. "4.0.1" for PCI DSS) — captured once,
    # never refreshed, so an assessment's own record of what it was
    # scored against survives a later framework_mapping/*.yaml content
    # change (ADR-0031). None only if no schema was loaded for
    # framework_name at creation time (the same "unrecognized framework
    # name falls back gracefully" case InvalidPracticeReferenceError's
    # docstring already describes) — never silently backfilled later.
    framework_version: str | None = None
    status: AssessmentStatus = Field(default=AssessmentStatus.DRAFT)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class EvidenceLink(SQLModel, table=True):
    """Associates an ingested document (Sprint 1, identified by
    document_id from the vector store) with an assessment and a practice
    reference.

    practice_reference is free text in Sprint 2 (e.g. "AM-1a") — becomes
    a real foreign key into framework_mapping/ once that data exists
    (Sprint 3+). Implements the assessment-generation skill's core
    invariant — no score exists without a linked evidence trail —
    enforced structurally by services/assessment_service.py, which
    refuses to create a link whose document_id was never actually
    ingested into the vector store.
    """

    id: str = Field(default_factory=_new_id, primary_key=True)
    assessment_id: str = Field(foreign_key="assessment.id", index=True)
    document_id: str = Field(index=True)
    chunk_id: str | None = None
    practice_reference: str
    # The practice_reference this link was FIRST created with, captured
    # automatically the first time an "edited" review decision changes
    # practice_reference (repositories/assessment_repository.py's
    # update_evidence_link_review). None until the first edit; never
    # overwritten again after that, so an AI's original proposal survives
    # a human correction instead of being silently lost — a real,
    # confirmed audit-trail gap, not a hypothetical one (see ADR-0030).
    original_practice_reference: str | None = None
    note: str | None = None
    source: EvidenceSource = Field(default=EvidenceSource.MANUAL)
    review_status: EvidenceReviewStatus = Field(default=EvidenceReviewStatus.ACCEPTED)
    # Retrieval-similarity heuristic (Sprint 5), set only for AI-proposed
    # links; None for manual ones. NOT a calibrated probability — see
    # services/mapping_service.py and ADR-0011. Explicitly distinct from
    # a model's self-reported confidence, per the evidence-extraction skill.
    confidence: float | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    reviewed_at: datetime | None = None


class AssessmentStatusChange(SQLModel, table=True):
    """Audit trail of every status transition an assessment goes through
    — the "state tracking" half of Sprint 2's scope, distinct from the
    evidence-to-score audit trail EvidenceLink provides. Directly serves
    the Internal Audit stakeholder in PROJECT_CHARTER.md's Stakeholder Map.
    """

    id: str = Field(default_factory=_new_id, primary_key=True)
    assessment_id: str = Field(foreign_key="assessment.id", index=True)
    from_status: AssessmentStatus | None = None
    to_status: AssessmentStatus
    note: str | None = None
    changed_at: datetime = Field(default_factory=_utcnow)


class PracticeFinding(SQLModel, table=True):
    """A human reviewer's explicit, current compliance judgment for one
    practice within one assessment (ADR-0030). At most one row per
    (assessment_id, practice_reference) — repositories/
    assessment_repository.py's set_practice_finding() upserts by that
    pair and writes a PracticeFindingChange row on every transition, the
    same append-only-history pattern AssessmentStatusChange already
    established for assessment-level status.

    Optional and additive: an assessment with zero PracticeFinding rows
    scores and reports identically to how it did before this table
    existed — see services/scoring_service.py's excluded_practice_ids
    parameter and services/assessment_service.py.compute_scores.
    """

    __table_args__ = (UniqueConstraint("assessment_id", "practice_reference"),)

    id: str = Field(default_factory=_new_id, primary_key=True)
    assessment_id: str = Field(foreign_key="assessment.id", index=True)
    practice_reference: str = Field(index=True)
    status: PracticeFindingStatus
    # Required, not optional: a NOT_SATISFIED or NOT_APPLICABLE judgment
    # that overrides what evidence-based scoring would otherwise show is
    # exactly the kind of consequential claim this project's "verified
    # over fabricated" discipline requires a stated reason for.
    rationale: str
    # Always "human" today — there is no generative reasoner in this
    # codebase (ADR-0011/ADR-0014/ADR-0020). Kept as a plain string, not
    # an enum, so a future reasoner integration is additive, not a schema
    # migration.
    set_by: str = Field(default="human")
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class PracticeFindingChange(SQLModel, table=True):
    """Append-only audit trail for PracticeFinding, mirroring
    AssessmentStatusChange. Every set_practice_finding() call writes one
    row here, including the very first (from_status=None) — so "what did
    we used to think about this practice, and when did that change" is
    always answerable, not just "what do we think now."
    """

    id: str = Field(default_factory=_new_id, primary_key=True)
    assessment_id: str = Field(foreign_key="assessment.id", index=True)
    practice_reference: str = Field(index=True)
    from_status: PracticeFindingStatus | None = None
    to_status: PracticeFindingStatus
    rationale: str
    set_by: str = Field(default="human")
    changed_at: datetime = Field(default_factory=_utcnow)
