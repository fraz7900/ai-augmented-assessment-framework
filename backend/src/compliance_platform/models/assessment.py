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

from sqlmodel import Field, SQLModel


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
