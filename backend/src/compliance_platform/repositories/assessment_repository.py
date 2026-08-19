"""Assessment + evidence-link relational storage (SQLite via SQLModel),
per ADR-0007.

Per the Repository pattern (repositories/README.md), services/ must
never open a SQLModel Session or import sqlmodel directly — only this
module's interface. That boundary is what makes ADR-0007 reversible if
a future sprint needs PostgreSQL for multi-tenant deployment.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, SQLModel, col, create_engine, select

from compliance_platform.core.errors import (
    AssessmentAlreadySealedError,
    AssessmentFinalizedError,
)
from compliance_platform.models.assessment import (
    Assessment,
    AssessmentDocument,
    AssessmentStatus,
    AssessmentStatusChange,
    Document,
    EvidenceLink,
    EvidenceRequest,
    EvidenceReviewStatus,
    IngestionJob,
    IngestionJobFailure,
    IngestionJobStatus,
    PracticeFinding,
    PracticeFindingChange,
    PracticeFindingStatus,
    SanitizationApproval,
    _new_id,
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
        _add_missing_columns(
            self._engine,
            "evidencelink",
            {"created_by": "TEXT", "reviewed_by": "TEXT"},
        )
        _add_missing_columns(self._engine, "assessmentstatuschange", {"actor": "TEXT"})
        self._backfill_document_associations()
        _add_missing_columns(
            self._engine,
            "assessment",
            {
                "framework_version": "TEXT",
                "sealed_digest": "TEXT",
                "sealed_at": "DATETIME",
                "seal_version": "TEXT",
            },
        )

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

    def _backfill_document_associations(self) -> None:
        """Materialise the associations that already existed implicitly.

        Before ADR-0062, "this document belongs to this assessment" was
        derived from the document_ids on an assessment's evidence links.
        Every such pair is an association by definition, so inserting
        them is lossless -- it records what the data already said rather
        than inventing anything. Without it, every existing assessment
        would open with an empty document list and look as though its
        evidence had vanished.

        Runs once per engine construction and is a no-op afterwards:
        it inserts only pairs that are missing. attached_by is left NULL
        because there is no honest name to put in it -- the link's own
        creator predates attribution too.
        """
        # Raw SQL on purpose, for both tables. A migration must not
        # depend on the CURRENT ORM mapping being able to deserialize
        # OLD rows -- and this one would not: a pre-ADR-0030 database
        # holds evidencelink rows whose `source` the present
        # EvidenceSource enum refuses to load, so reading them through
        # SQLModel would raise on exactly the databases this exists to
        # rescue. Only two opaque id columns are needed here anyway.
        with self._engine.connect() as connection:
            existing = {
                (row[0], row[1])
                for row in connection.exec_driver_sql(
                    "SELECT assessment_id, document_id FROM assessmentdocument"
                )
            }
            implied = {
                (row[0], row[1])
                for row in connection.exec_driver_sql(
                    "SELECT DISTINCT assessment_id, document_id FROM evidencelink"
                )
            }
            missing = implied - existing
            if not missing:
                return
            for assessment_id, document_id in sorted(missing):
                connection.exec_driver_sql(
                    "INSERT INTO assessmentdocument "
                    "(id, assessment_id, document_id, attached_at, attached_by) "
                    "VALUES (?, ?, ?, ?, NULL)",
                    # An ISO string, not a datetime: Python 3.12 deprecated
                    # sqlite3's implicit datetime adapter, and SQLModel stores
                    # this column in exactly this format anyway.
                    (_new_id(), assessment_id, document_id, datetime.now(UTC).isoformat()),
                )
            connection.commit()
            _logger.info("backfilled %d assessment-document association(s)", len(missing))

    def attach_document(
        self, assessment_id: str, document_id: str, attached_by: str | None = None
    ) -> AssessmentDocument:
        """Associate a document with an assessment, idempotently.

        Attaching twice is not an error: the caller's intent -- that this
        document belongs to this assessment -- is satisfied either way,
        and linking evidence attaches implicitly, so a reviewer who
        attaches first and links second would otherwise hit a spurious
        conflict for doing things in the sensible order.
        """
        with Session(self._engine) as session:
            self._assert_writable(session, assessment_id)
            existing = session.exec(
                select(AssessmentDocument).where(
                    AssessmentDocument.assessment_id == assessment_id,
                    AssessmentDocument.document_id == document_id,
                )
            ).first()
            if existing is not None:
                return existing
            association = AssessmentDocument(
                assessment_id=assessment_id,
                document_id=document_id,
                attached_by=attached_by,
            )
            session.add(association)
            session.commit()
            session.refresh(association)
            return association

    def detach_document(self, assessment_id: str, document_id: str) -> bool:
        """Remove an association. Returns whether one was removed.

        Deletes the association only, never the document: the same file
        may be attached to other assessments, and ingestion is expensive
        enough that discarding it as a side effect of tidying one
        assessment would be a poor trade.
        """
        with Session(self._engine) as session:
            self._assert_writable(session, assessment_id)
            association = session.exec(
                select(AssessmentDocument).where(
                    AssessmentDocument.assessment_id == assessment_id,
                    AssessmentDocument.document_id == document_id,
                )
            ).first()
            if association is None:
                return False
            session.delete(association)
            session.commit()
            return True

    def documents_for_assessment(self, assessment_id: str) -> list[Document]:
        """The attached documents, newest first, resolved to real rows.

        An association whose document has no registry row is skipped
        rather than faked: 27 of 30 documents in the original corpus
        predate ADR-0039 and have no Document row at all, and their
        evidence links are still valid. A placeholder here would put an
        unrecognisable entry in a chooser whose whole job is
        recognisability.
        """
        with Session(self._engine) as session:
            associations = session.exec(
                select(AssessmentDocument)
                .where(AssessmentDocument.assessment_id == assessment_id)
                .order_by(text("rowid"))
            ).all()
            documents = []
            for association in associations:
                document = session.get(Document, association.document_id)
                if document is not None:
                    documents.append(document)
            return documents

    def attached_document_ids(self, assessment_id: str) -> list[str]:
        """Every attached document id, including ones with no registry
        row -- the mapping engine searches the vector store, which knows
        nothing about the registry."""
        with Session(self._engine) as session:
            associations = session.exec(
                select(AssessmentDocument)
                .where(AssessmentDocument.assessment_id == assessment_id)
                .order_by(text("rowid"))
            ).all()
            return [association.document_id for association in associations]

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
        self,
        assessment_id: str,
        new_status: AssessmentStatus,
        note: str | None = None,
        actor: str | None = None,
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
                    actor=actor,
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
        reviewed_by: str | None = None,
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
            link.reviewed_by = reviewed_by
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

    def practice_finding_history_for_assessment(
        self, assessment_id: str
    ) -> list[PracticeFindingChange]:
        """Every practice-finding transition in this assessment, oldest
        first. practice_finding_history() answers the same question for
        one practice; the finalization seal needs the whole trail in one
        deterministic order, and rowid is this repository's established
        authority for insertion order (see status_history)."""
        with Session(self._engine) as session:
            statement = (
                select(PracticeFindingChange)
                .where(PracticeFindingChange.assessment_id == assessment_id)
                .order_by(text("rowid"))
            )
            return list(session.exec(statement).all())

    def store_finalization_seal(
        self, assessment_id: str, digest: str, seal_version: str
    ) -> Assessment | None:
        """Record the tamper-evidence digest for a just-finalized
        assessment.

        Deliberately not behind _assert_writable: this is the one write
        that must happen to an assessment that is already FINALIZED, and
        it is the write the lock exists to make meaningful. It touches
        only the seal columns, which are excluded from the sealed
        payload itself (services/audit_seal.py), so sealing cannot
        invalidate its own seal.

        Refuses to overwrite an existing seal. Re-sealing a record is
        indistinguishable from covering up an edit to it, so it is not
        an operation this repository offers.
        """
        with Session(self._engine) as session:
            assessment = session.get(Assessment, assessment_id)
            if assessment is None:
                return None
            if assessment.sealed_digest is not None:
                _logger.error(
                    "refused to overwrite the existing finalization seal on assessment %s",
                    assessment_id,
                )
                raise AssessmentAlreadySealedError(assessment_id)
            assessment.sealed_digest = digest
            assessment.seal_version = seal_version
            assessment.sealed_at = datetime.now(UTC)
            session.add(assessment)
            session.commit()
            session.refresh(assessment)
            return assessment

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

    # ---- Ingestion jobs (async ingestion) ----------------------------
    #
    # These run from a worker thread, not the request thread. That is
    # safe here because every method in this class opens and closes its
    # own Session against a shared engine whose pool hands out a
    # per-thread connection -- verified directly rather than assumed,
    # the same way ADR-0037 verified the vector store's read path under
    # concurrent load.

    def create_ingestion_job(self, job: IngestionJob) -> IngestionJob:
        with Session(self._engine) as session:
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    def get_ingestion_job(self, job_id: str) -> IngestionJob | None:
        with Session(self._engine) as session:
            return session.get(IngestionJob, job_id)

    def list_ingestion_jobs(self, limit: int = 50) -> list[IngestionJob]:
        """Most recently created first, so an operator sees the run they
        just started without paging."""
        with Session(self._engine) as session:
            statement = (
                select(IngestionJob).order_by(col(IngestionJob.created_at).desc()).limit(limit)
            )
            return list(session.exec(statement).all())

    def mark_ingestion_job_running(self, job_id: str) -> IngestionJob | None:
        with Session(self._engine) as session:
            job = session.get(IngestionJob, job_id)
            if job is None:
                return None
            job.status = IngestionJobStatus.RUNNING
            job.started_at = datetime.now(UTC)
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    def complete_ingestion_job(
        self,
        job_id: str,
        *,
        document_id: str,
        chunk_count: int,
        parse_status: str,
        parser_version: str,
        embedding_backend: str,
        parse_warnings: list[str],
    ) -> IngestionJob | None:
        with Session(self._engine) as session:
            job = session.get(IngestionJob, job_id)
            if job is None:
                return None
            job.status = IngestionJobStatus.SUCCEEDED
            job.finished_at = datetime.now(UTC)
            job.document_id = document_id
            job.chunk_count = chunk_count
            job.parse_status = parse_status
            job.parser_version = parser_version
            job.embedding_backend = embedding_backend
            job.parse_warnings_json = json.dumps(parse_warnings)
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    def fail_ingestion_job(
        self,
        job_id: str,
        *,
        category: IngestionJobFailure,
        message: str,
        parse_warnings: list[str] | None = None,
    ) -> IngestionJob | None:
        with Session(self._engine) as session:
            job = session.get(IngestionJob, job_id)
            if job is None:
                return None
            job.status = IngestionJobStatus.FAILED
            job.finished_at = datetime.now(UTC)
            job.failure_category = category
            job.failure_message = message
            if parse_warnings is not None:
                job.parse_warnings_json = json.dumps(parse_warnings)
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    def fail_interrupted_ingestion_jobs(self) -> int:
        """Fail every job left QUEUED or RUNNING by a previous process.

        Jobs live in the database but the executor that runs them lives
        in memory, so a restart (crash, redeploy, or an ordinary
        `docker compose up`) strands anything mid-flight: nothing will
        ever pick it up again, and a row that says RUNNING forever is
        worse than one that says it was interrupted. Called once at
        startup. Returns how many were swept, so the caller can log a
        real number rather than assert success.
        """
        with Session(self._engine) as session:
            statement = select(IngestionJob).where(
                col(IngestionJob.status).in_(
                    [IngestionJobStatus.QUEUED, IngestionJobStatus.RUNNING]
                )
            )
            stranded = list(session.exec(statement).all())
            for job in stranded:
                job.status = IngestionJobStatus.FAILED
                job.finished_at = datetime.now(UTC)
                job.failure_category = IngestionJobFailure.INTERRUPTED
                job.failure_message = (
                    "The server restarted while this document was being ingested. "
                    "Upload it again. If this document already appears in the "
                    "document list, it finished before the restart and does not "
                    "need re-uploading."
                )
                session.add(job)
            session.commit()
            return len(stranded)
