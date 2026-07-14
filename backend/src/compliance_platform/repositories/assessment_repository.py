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

from sqlmodel import Session, SQLModel, create_engine, select

from compliance_platform.models.assessment import (
    Assessment,
    AssessmentStatus,
    AssessmentStatusChange,
    EvidenceLink,
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
        with Session(self._engine) as session:
            statement = (
                select(AssessmentStatusChange)
                .where(AssessmentStatusChange.assessment_id == assessment_id)
                .order_by(AssessmentStatusChange.changed_at)
            )
            return list(session.exec(statement).all())

    def add_evidence_link(self, link: EvidenceLink) -> EvidenceLink:
        with Session(self._engine) as session:
            session.add(link)
            session.commit()
            session.refresh(link)
            return link

    def evidence_for_assessment(self, assessment_id: str) -> list[EvidenceLink]:
        with Session(self._engine) as session:
            statement = select(EvidenceLink).where(EvidenceLink.assessment_id == assessment_id)
            return list(session.exec(statement).all())
