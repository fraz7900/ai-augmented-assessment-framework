"""Assessment + evidence-link relational storage (SQLite via SQLModel),
per ADR-0007.

Per the Repository pattern (repositories/README.md), services/ must
never open a SQLModel Session or import sqlmodel directly — only this
module's interface. That boundary is what makes ADR-0007 reversible if
a future sprint needs PostgreSQL for multi-tenant deployment.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, SQLModel, col, create_engine, select

from compliance_platform.core.errors import AssessmentFinalizedError
from compliance_platform.models.assessment import (
    Assessment,
    AssessmentStatus,
    AssessmentStatusChange,
    Document,
    EvidenceLink,
    EvidenceRequest,
    EvidenceReviewStatus,
    PracticeFinding,
    PracticeFindingChange,
    PracticeFindingStatus,
    SanitizationApproval,
)

_logger = logging.getLogger(__name__)


def _add_missing_columns(engine, table: str, columns: dict[str, str]) -> None:
    """SQLModel.metadata.create_all only creates missing TABLES, not
    missing COLUMNS on a table that already exists on disk (ADR-0007
    has no Alembic-style migration tool — a deliberate choice for a
    local-first, single-file-SQLite product, not an oversight). A new
    nullable column added to an existing model (e.g.
    EvidenceLink.original_practice_reference, ADR-0030) would otherwise
    silently be absent from any pre-existing local assessments.db,
    turning every read into a schema-mismatch error. This runs once per
    engine construction, is a no-op on a fresh database (create_all
    already created the column), and only ever ADDs — it never drops or
    alters existing data.
    """
    with engine.connect() as conn:
        existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
        for column, sql_type in columns.items():
            if column not in existing:
                conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}")
        conn.commit()


class AssessmentRepository:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(f"sqlite:///{db_path}")
        SQLModel.metadata.create_all(self._engine)
        _add_missing_columns(
            self._engine, "evidencelink", {"original_practice_reference": "TEXT"}
        )
        _add_missing_columns(self._engine, "assessment", {"framework_version": "TEXT"})

    def _assert_writable(self, session: Session, assessment_id: str) -> None:
        """Refuse a write to a finalized assessment, inside the caller's
        own transaction.

        AssessmentService checks this before calling any of these
        methods and that check stays: it is what turns the refusal into
        a 409 before any work happens, and it can say which operation
        was refused. This one exists because that check cannot do two
        other things.

        First, it closes a real check-then-act window (R-11's bug class,
        R-12's risk). The service reads the assessment through
        get_assessment(), which opens a session, reads, and closes it —
        then calls one of these methods, which opens a *second* session
        to write. An assessment finalized between those two moments was
        written to anyway. Reading the status in the same transaction as
        the write removes the window: on SQLite's default rollback
        journal the shared lock taken by this read is held until the
        write commits, so a concurrent finalize cannot land in between.

        Second, it applies to callers that never went through the
        service at all — a script, a future endpoint, a migration. R-12
        has recorded since Sprint 2 that nothing prevented such a caller
        from writing straight through the audit-immutability guarantee,
        and ADR-0058's finalization gate has since been built on top of
        that same single layer of enforcement.

        Reaching this raise means a caller skipped the service check, so
        it is logged: a backstop that fires silently is one that stops
        being a backstop and starts being the only check.

        A missing assessment is deliberately NOT an error here. There is
        no lock to enforce on an assessment that does not exist, the
        service already raises AssessmentNotFoundError long before this
        point, and inventing a second opinion in the repository would
        change behaviour this change has no business changing.
        """
        assessment = session.get(Assessment, assessment_id)
        if assessment is None:
            return
        if assessment.status == AssessmentStatus.FINALIZED:
            _logger.error(
                "blocked a write to finalized assessment %s at the repository layer; "
                "the caller bypassed AssessmentService's check",
                assessment_id,
            )
            raise AssessmentFinalizedError(assessment_id)

    def create_assessment(
        self, name: str, framework_name: str, framework_version: str | None = None
    ) -> Assessment:
        assessment = Assessment(
            name=name, framework_name=framework_name, framework_version=framework_version
        )
        with Session(self._engine) as session:
            session.add(assessment)
            session.add(
                AssessmentStatusChange(
                    assessment_id=assessment.id,
                    from_status=None,
                    to_status=assessment.status,
                    note="Assessment created.",
                )
            )
            session.commit()
            session.refresh(assessment)
            return assessment

    def get_assessment(self, assessment_id: str) -> Assessment | None:
        with Session(self._engine) as session:
            return session.get(Assessment, assessment_id)

    def list_assessments(self) -> list[Assessment]:
        with Session(self._engine) as session:
            return list(session.exec(select(Assessment)).all())

    def update_status(
        self, assessment_id: str, new_status: AssessmentStatus, note: str | None = None
    ) -> Assessment | None:
        with Session(self._engine) as session:
            assessment = session.get(Assessment, assessment_id)
            if assessment is None:
                return None
            previous_status = assessment.status
            assessment.status = new_status
            assessment.updated_at = datetime.now(UTC)
            session.add(assessment)
            session.add(
                AssessmentStatusChange(
                    assessment_id=assessment_id,
                    from_status=previous_status,
                    to_status=new_status,
                    note=note,
                )
            )
            session.commit()
            session.refresh(assessment)
            return assessment

    def status_history(self, assessment_id: str) -> list[AssessmentStatusChange]:
        # Ordered by SQLite's implicit rowid, not changed_at: Python-side
        # datetime.now(UTC) timestamps (set at object construction, see
        # models/assessment.py's _utcnow default_factory) are not a
        # reliable ordering key when two writes land close enough
        # together to tie at whatever resolution the host clock actually
        # provides — caught as a real, intermittent test failure (status
        # entries returned out of insertion order), not assumed as a risk
        # in the abstract. rowid is monotonically increasing per insert
        # regardless of wall-clock behavior. This is SQLite-specific;
        # revisit if ADR-0007's future PostgreSQL migration ever happens
        # (Postgres has no rowid — an explicit sequence column would be
        # needed there).
        with Session(self._engine) as session:
            statement = (
                select(AssessmentStatusChange)
                .where(AssessmentStatusChange.assessment_id == assessment_id)
                .order_by(text("rowid"))
            )
            return list(session.exec(statement).all())

    def add_evidence_link(self, link: EvidenceLink) -> EvidenceLink:
        with Session(self._engine) as session:
            self._assert_writable(session, link.assessment_id)
            session.add(link)
            session.commit()
            session.refresh(link)
            return link

    def evidence_for_assessment(self, assessment_id: str) -> list[EvidenceLink]:
        # Ordered by rowid for the same reason as status_history above:
        # this previously had no explicit ORDER BY at all, which is not
        # guaranteed to return insertion order — a latent instance of the
        # same bug class, fixed preemptively once the first instance
        # (status_history) was found and root-caused, not left for a
        # second occurrence to surface separately.
        with Session(self._engine) as session:
            statement = (
                select(EvidenceLink)
                .where(EvidenceLink.assessment_id == assessment_id)
                .order_by(text("rowid"))
            )
            return list(session.exec(statement).all())

    def get_evidence_link(self, evidence_link_id: str) -> EvidenceLink | None:
        with Session(self._engine) as session:
            return session.get(EvidenceLink, evidence_link_id)

    def update_evidence_link_review(
        self,
        evidence_link_id: str,
        review_status: EvidenceReviewStatus,
        practice_reference: str | None = None,
        note: str | None = None,
    ) -> EvidenceLink | None:
        """Applies a human review decision (accept/edit/reject) to an
        existing evidence link. practice_reference is only passed for an
        "edit" decision (services/assessment_service.py.review_evidence);
        None leaves the original practice_reference untouched.
        """
        with Session(self._engine) as session:
            link = session.get(EvidenceLink, evidence_link_id)
            if link is None:
                return None
            self._assert_writable(session, link.assessment_id)
            link.review_status = review_status
            link.reviewed_at = datetime.now(UTC)
            if practice_reference is not None:
                # Preserve whatever practice_reference this link had
                # *before* this edit — captured only on the first edit
                # (None check), so a second correction doesn't overwrite
                # the true original with an intermediate value. See
                # models/assessment.py's EvidenceLink.original_practice_reference
                # and ADR-0030.
                if link.original_practice_reference is None:
                    link.original_practice_reference = link.practice_reference
                link.practice_reference = practice_reference
            if note is not None:
                link.note = note
            session.add(link)
            session.commit()
            session.refresh(link)
            return link

    def set_practice_finding(
        self,
        assessment_id: str,
        practice_reference: str,
        status: PracticeFindingStatus,
        rationale: str,
        set_by: str = "human",
    ) -> PracticeFinding:
        """Upserts the single PracticeFinding row for this
        (assessment_id, practice_reference) pair and records the
        transition in PracticeFindingChange — see models/assessment.py
        and ADR-0030.
        """
        with Session(self._engine) as session:
            self._assert_writable(session, assessment_id)
            statement = select(PracticeFinding).where(
                PracticeFinding.assessment_id == assessment_id,
                PracticeFinding.practice_reference == practice_reference,
            )
            existing = session.exec(statement).first()
            from_status = existing.status if existing is not None else None

            if existing is not None:
                existing.status = status
                existing.rationale = rationale
                existing.set_by = set_by
                existing.updated_at = datetime.now(UTC)
                finding = existing
            else:
                finding = PracticeFinding(
                    assessment_id=assessment_id,
                    practice_reference=practice_reference,
                    status=status,
                    rationale=rationale,
                    set_by=set_by,
                )
            session.add(finding)
            session.add(
                PracticeFindingChange(
                    assessment_id=assessment_id,
                    practice_reference=practice_reference,
                    from_status=from_status,
                    to_status=status,
                    rationale=rationale,
                    set_by=set_by,
                )
            )
            session.commit()
            session.refresh(finding)
            return finding

    def practice_findings_for_assessment(self, assessment_id: str) -> list[PracticeFinding]:
        with Session(self._engine) as session:
            statement = (
                select(PracticeFinding)
                .where(PracticeFinding.assessment_id == assessment_id)
                .order_by(text("rowid"))
            )
            return list(session.exec(statement).all())

    def practice_finding_history(
        self, assessment_id: str, practice_reference: str
    ) -> list[PracticeFindingChange]:
        # Ordered by rowid, same reliable-ordering reasoning as
        # status_history/evidence_for_assessment above.
        with Session(self._engine) as session:
            statement = (
                select(PracticeFindingChange)
                .where(
                    PracticeFindingChange.assessment_id == assessment_id,
                    PracticeFindingChange.practice_reference == practice_reference,
                )
                .order_by(text("rowid"))
            )
            return list(session.exec(statement).all())

    def create_sanitization_approval(self, approval: SanitizationApproval) -> SanitizationApproval:
        with Session(self._engine) as session:
            session.add(approval)
            session.commit()
            session.refresh(approval)
            return approval

    def latest_sanitization_approval(self, assessment_id: str) -> SanitizationApproval | None:
        # Most recent by rowid (same reliable-ordering reasoning as
        # status_history above), i.e. the current standing approval —
        # an assessment can be re-sanitized and re-approved repeatedly
        # as its content evolves; only the latest one governs export.
        with Session(self._engine) as session:
            statement = (
                select(SanitizationApproval)
                .where(SanitizationApproval.assessment_id == assessment_id)
                .order_by(text("rowid desc"))
                .limit(1)
            )
            return session.exec(statement).first()

    def create_document(self, document: Document) -> Document:
        with Session(self._engine) as session:
            session.add(document)
            session.commit()
            session.refresh(document)
            return document

    def get_document(self, document_id: str) -> Document | None:
        with Session(self._engine) as session:
            return session.get(Document, document_id)

    def list_documents(self) -> list[Document]:
        """Every registered document, newest upload first.

        Exists so the UI can offer a chooser. Before this, linking
        evidence required the reviewer to copy a UUID off the upload
        screen and paste it into the Evidence tab by hand, because
        nothing could enumerate what had been ingested.

        Unpaginated, deliberately: this is a local-first,
        single-organisation deployment whose Document table holds one row
        per uploaded file. If that ever reaches a size where this is the
        wrong shape, the fix is a paged endpoint with a real cursor, not
        a silent limit here that would hide documents from a chooser
        claiming to list them all.
        """
        with Session(self._engine) as session:
            statement = select(Document).order_by(Document.uploaded_at.desc())  # type: ignore[attr-defined]
            return list(session.exec(statement).all())

    def document_superseded_by(self, document_id: str) -> Document | None:
        """The document (if any) that explicitly declared it supersedes
        document_id — the reverse lookup a reviewer needs to answer "is
        the document THIS evidence link points to now out of date?"
        without having to scan every Document row themselves.
        """
        with Session(self._engine) as session:
            statement = select(Document).where(Document.supersedes_document_id == document_id)
            return session.exec(statement).first()

    def superseded_document_ids(self, document_ids: Iterable[str]) -> set[str]:
        """Bulk form of document_superseded_by's reverse lookup, for
        callers checking many documents at once (report_service.py's
        dashboard/export citation flagging, ADR-0050) — one query
        instead of one per document_id. Returns the subset of
        document_ids that some OTHER document has declared it
        supersedes; a document_id absent from the result is either not
        superseded or not a real document at all (this method doesn't
        distinguish the two, since callers already have the real
        document_ids from their own EvidenceLink/Document rows).
        """
        ids = list(document_ids)
        if not ids:
            return set()
        with Session(self._engine) as session:
            statement = select(Document.supersedes_document_id).where(
                col(Document.supersedes_document_id).in_(ids)
            )
            return {row for row in session.exec(statement) if row is not None}

    def create_evidence_request(self, request: EvidenceRequest) -> EvidenceRequest:
        with Session(self._engine) as session:
            self._assert_writable(session, request.assessment_id)
            session.add(request)
            session.commit()
            session.refresh(request)
            return request

    def get_evidence_request(self, request_id: str) -> EvidenceRequest | None:
        with Session(self._engine) as session:
            return session.get(EvidenceRequest, request_id)

    def evidence_requests_for_assessment(self, assessment_id: str) -> list[EvidenceRequest]:
        # Ordered by rowid, same reliable-ordering reasoning as
        # status_history/evidence_for_assessment above -- oldest
        # requests first, matching a worklist's natural reading order.
        with Session(self._engine) as session:
            statement = (
                select(EvidenceRequest)
                .where(EvidenceRequest.assessment_id == assessment_id)
                .order_by(text("rowid"))
            )
            return list(session.exec(statement).all())

    def resolve_evidence_request(
        self, request_id: str, resolved_by: str
    ) -> EvidenceRequest | None:
        with Session(self._engine) as session:
            request = session.get(EvidenceRequest, request_id)
            if request is None:
                return None
            self._assert_writable(session, request.assessment_id)
            request.resolved_at = datetime.now(UTC)
            request.resolved_by = resolved_by
            session.add(request)
            session.commit()
            session.refresh(request)
            return request
