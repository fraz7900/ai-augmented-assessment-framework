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

    # Tamper-evidence for the finalized record (R-12 Step 2). Written
    # once, at the moment of finalization, over the whole assessment --
    # see services/audit_seal.py for what is covered and, just as
    # importantly, what this does and does not prove. None for any
    # assessment that has never been finalized, and for assessments
    # finalized before this existed: an unsealed record is reported as
    # unsealed, never as verified, and never back-filled, because a seal
    # computed today over a record that may already have been altered
    # would attest to nothing while looking like it attested to
    # something.
    sealed_digest: str | None = None
    sealed_at: datetime | None = None
    # Which canonical payload shape the digest was computed over, so a
    # later change to that shape does not invalidate existing seals.
    seal_version: str | None = None


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


class SanitizationApproval(SQLModel, table=True):
    """A human's explicit sign-off on one specific sanitized report
    (ADR-0032) — "internal assessment -> sanitization -> preview/diff ->
    human approval -> sanitized export", never a silent step.

    sanitized_content_hash pins exactly what was approved: a SHA-256 of
    the sanitized DashboardReport's own JSON content, recomputed fresh
    every time a sanitized export is requested
    (services/assessment_service.py.generate_dashboard_pdf/xlsx). If
    anything the report is built from has changed since approval (a new
    finding, an edited rationale, a newly accepted evidence link), the
    freshly recomputed hash will not match this stored one, and export
    is blocked (SanitizationApprovalStaleError) until re-approved —
    approval is tied to specific content, not to "sanitization is on"
    as a standing toggle that could authorize a materially different
    report than what was actually reviewed.
    """

    id: str = Field(default_factory=_new_id, primary_key=True)
    assessment_id: str = Field(foreign_key="assessment.id", index=True)
    sanitized_content_hash: str
    # JSON-encoded list[str] of the custom terms (names, facility/
    # vendor/employee identifiers, etc.) in effect for this approval —
    # stored, not re-derived, so a later export reproduces exactly what
    # was reviewed rather than whatever custom-term list happens to be
    # supplied at export time.
    custom_terms_json: str
    approved_by: str
    approved_at: datetime = Field(default_factory=_utcnow)


class Document(SQLModel, table=True):
    """A durable record of one ingested document (Sprint 18, ADR-0039).

    Before this, no such record existed anywhere: SourceDocumentMetadata
    (models/schemas.py) is computed at parse time and returned in the
    ingestion API response, but nothing durable persisted filename/
    content_hash/submitter past that single response — only each
    chunk's bare document_id survived, in the vector store. This closes
    a real, confirmed gap (controlled-pilot readiness audit §A.3): "no
    document_version (a re-upload gets a fresh, unlinked document_id)".

    id matches the document_id already used by the vector store (see
    services/document_parsers.py._new_document_id) and every
    EvidenceLink.document_id that already references it — the same
    identifier, now also durably recorded here, not a second ID scheme.

    supersedes_document_id is explicit and human-declared at upload
    time, never inferred from filename or content similarity — the same
    "verified over fabricated" discipline every human-in-the-loop
    decision in this project already follows (PracticeFinding,
    SanitizationApproval): silently guessing which upload replaces which
    risks marking an evidence trail stale on a false positive, or
    missing a real supersession on a false negative. None until an
    uploader explicitly names the document_id this one replaces.
    """

    id: str = Field(primary_key=True)
    filename: str
    file_type: str
    content_hash: str
    submitter: str | None = None
    uploaded_at: datetime = Field(default_factory=_utcnow)
    supersedes_document_id: str | None = Field(default=None, index=True)
    # Sprint 18, ADR-0042: the real installed parser library version
    # that produced this document's chunks (e.g. "pypdf==6.14.2"), not
    # a hand-maintained internal counter. See models/schemas.py
    # .SourceDocumentMetadata.parser_version for the full rationale.
    # Default "" only for schema-evolution safety (a value is always
    # supplied by ingestion_service.py in practice); no pre-existing
    # Document row can lack it, since this table is new this same sprint.
    parser_version: str = ""


class IngestionJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class IngestionJobFailure(StrEnum):
    """Why an ingestion job failed, as a closed set rather than prose.

    Same discipline as ADR-0058's FinalizationBlockerCategory: the UI
    decides what to render and whether a retry is worth offering, and
    parsing English to make that decision breaks the first time the
    wording improves. The human-readable detail lives alongside this in
    failure_message; this field is what code branches on.
    """

    UNSUPPORTED_DOCUMENT = "unsupported_document"
    UNKNOWN_SUPERSEDED_DOCUMENT = "unknown_superseded_document"
    TOO_LARGE = "too_large"
    INTERRUPTED = "interrupted"
    INTERNAL_ERROR = "internal_error"


class IngestionJob(SQLModel, table=True):
    """One queued/running/finished attempt to ingest one uploaded file.

    Ingestion was synchronous until now: the HTTP request held open for
    the whole parse/chunk/embed pass, so a large or scanned document
    could exceed the proxy's 300s read ceiling
    (deployment/frontend.nginx.conf) and fail as a gateway timeout with
    no record that the work had ever started. A 505-page PDF, or one
    needing OCR on most of its pages, is ordinary real evidence -- so
    that ceiling was a real functional limit, not a theoretical one.

    This record is what makes the work observable once the response no
    longer carries it: the upload returns immediately with a job id, and
    the client polls this row. It deliberately stores the *outcome*
    fields of IngestionResult rather than replacing it -- the
    synchronous endpoint still exists and still returns the same shape,
    because nothing about it was wrong for small documents.

    A job row is never deleted on failure. A failed ingestion is exactly
    the case an operator needs to see, and discarding the record would
    reproduce the gateway-timeout problem this table exists to fix.
    """

    id: str = Field(default_factory=_new_id, primary_key=True)
    status: IngestionJobStatus = Field(default=IngestionJobStatus.QUEUED, index=True)
    filename: str
    submitter: str | None = None
    supersedes_document_id: str | None = None

    created_at: datetime = Field(default_factory=_utcnow, index=True)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    # Populated only on success. document_id is the same identifier the
    # vector store and every EvidenceLink already use -- not a second
    # ID scheme (see Document.id).
    document_id: str | None = Field(default=None, index=True)
    chunk_count: int | None = None
    parse_status: str | None = None
    parser_version: str | None = None
    embedding_backend: str | None = None

    # Parse warnings are a list, and this project has no JSON column
    # convention yet (ADR-0007 keeps the SQLite schema deliberately
    # plain). Stored as a JSON string and decoded at the repository
    # boundary rather than introducing a sa_column here for one field --
    # services and the API only ever see list[str].
    parse_warnings_json: str = "[]"

    failure_category: IngestionJobFailure | None = None
    failure_message: str | None = None


class EvidenceRequest(SQLModel, table=True):
    """A reviewer's explicit request that someone go find and upload
    MORE evidence for a specific practice (Sprint 18, ADR-0043) —
    distinct from PracticeFindingStatus.INSUFFICIENT_EVIDENCE, which is
    a compliance JUDGMENT (this project's own visible reading of the
    evidence gathered so far). A request is a WORKFLOW action directed
    at a person (frequently Sam, the OT engineering contributor persona
    who submits evidence but doesn't judge compliance) — "please go get
    X" — and can coexist with any PracticeFindingStatus, including
    PARTIALLY_SATISFIED ("this is good enough to note partial credit,
    but I still want more to fully confirm it").

    Unlike PracticeFinding, no separate append-only history table:
    a request's lifecycle is a simple open -> resolved transition, not
    a repeatedly-mutating judgment, so resolved_at/resolved_by directly
    on this row is itself the complete audit record. Multiple open
    requests can exist for the same practice (no uniqueness constraint)
    — a real, disclosed simplification, not an oversight: enforcing
    "at most one open request per practice" would need to define what
    happens to an already-open request when a second is filed, and
    nothing in this feature's actual use case requires that.

    Resolution is always explicit, never inferred from a new evidence
    link being added — linking evidence doesn't guarantee it actually
    addresses what was requested, the same "nothing silently automatic"
    discipline every other human-in-the-loop decision in this project
    already follows (PracticeFinding, SanitizationApproval).
    """

    id: str = Field(default_factory=_new_id, primary_key=True)
    assessment_id: str = Field(foreign_key="assessment.id", index=True)
    practice_reference: str = Field(index=True)
    note: str
    requested_by: str
    requested_at: datetime = Field(default_factory=_utcnow)
    resolved_at: datetime | None = None
    resolved_by: str | None = None
