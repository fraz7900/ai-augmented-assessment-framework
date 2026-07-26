"""Assessment + evidence-link relational storage (SQLite via SQLModel),
per ADR-0007.

Per the Repository pattern (repositories/README.md), services/ must
never open a SQLModel Session or import sqlmodel directly — only this
module's interface. That boundary is what makes ADR-0007 reversible if
a future sprint needs PostgreSQL for multi-tenant deployment.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

from compliance_platform.models.assessment import (
    Assessment,
    AssessmentStatus,
    AssessmentStatusChange,
    Document,
    EvidenceLink,
    EvidenceReviewStatus,
    PracticeFinding,
    PracticeFindingChange,
    PracticeFindingStatus,
    SanitizationApproval,
)


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

    def document_superseded_by(self, document_id: str) -> Document | None:
        """The document (if any) that explicitly declared it supersedes
        document_id — the reverse lookup a reviewer needs to answer "is
        the document THIS evidence link points to now out of date?"
        without having to scan every Document row themselves.
        """
        with Session(self._engine) as session:
            statement = select(Document).where(Document.supersedes_document_id == document_id)
            return session.exec(statement).first()
