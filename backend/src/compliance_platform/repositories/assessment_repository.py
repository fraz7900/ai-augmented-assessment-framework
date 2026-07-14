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
    EvidenceLink,
    EvidenceReviewStatus,
)


class AssessmentRepository:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(f"sqlite:///{db_path}")
        SQLModel.metadata.create_all(self._engine)

    def create_assessment(self, name: str, framework_name: str) -> Assessment:
        assessment = Assessment(name=name, framework_name=framework_name)
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
                link.practice_reference = practice_reference
            if note is not None:
                link.note = note
            session.add(link)
            session.commit()
            session.refresh(link)
            return link
