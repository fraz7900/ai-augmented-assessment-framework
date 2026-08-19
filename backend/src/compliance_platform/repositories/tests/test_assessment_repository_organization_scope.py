"""The organisation boundary, enforced at the repository layer, and the
migration that carries an existing database onto it (ADR-0063).

R-39 has been open since Sprint 21: scoping documents to assessments
narrowed the evidence chooser but separated nothing, because the attach
flow still browsed every document on the instance. Every guard test here
calls the repository directly, with no service involved, which is the
only way to prove the check is where it claims to be.

The migration tests matter more than the guard tests, and are first for
that reason. The guard protects work that has not happened yet; the
migration runs once, in place, against the only copy of a record whose
whole value proposition is immutability. A pre-sprint database is
simulated honestly -- the columns are dropped and the organisation table
removed, so the reopened repository sees exactly what an older build
left behind, not a fixture that merely resembles one.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from compliance_platform.core.errors import (
    CrossOrganizationAttachmentError,
    OrganizationNotFoundError,
    OrganizationRequiredError,
)
from compliance_platform.models.assessment import (
    DEFAULT_ORGANIZATION_ID,
    DEFAULT_ORGANIZATION_NAME,
    Document,
    EvidenceLink,
    EvidenceReviewStatus,
    EvidenceSource,
)
from compliance_platform.repositories.assessment_repository import AssessmentRepository


def _repo(tmp_path: Path) -> AssessmentRepository:
    return AssessmentRepository(tmp_path / "assessments.db")


def _document(document_id: str, organization_id: str) -> Document:
    return Document(
        id=document_id,
        organization_id=organization_id,
        filename=f"{document_id}.pdf",
        file_type="pdf",
        content_hash=f"hash-{document_id}",
    )


def _regress_to_pre_sprint_schema(db_path: Path) -> None:
    """Turn a current-schema database back into a pre-ADR-0063 one.

    A column drop will not do it: SQLModel emits a FOREIGN KEY clause
    naming organization_id, and SQLite refuses to drop a column a
    constraint still references. A table an older build created never
    carried that clause, so the faithful simulation is SQLite's
    documented table rewrite -- recreate each table from its own DDL with
    the column and its constraint removed, copy every row across, and
    drop the original.

    legacy_alter_table is on for the rename because `assessment` is
    referenced by six other tables' foreign keys. Without it SQLite
    helpfully rewrites those references to point at the renamed copy,
    which is the opposite of what a migration test wants: the references
    must keep naming `assessment` so the recreated table satisfies them.
    """
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA legacy_alter_table=ON")
        for table in ("assessment", "document"):
            ddl = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()[0]
            indexes = [
                row[0]
                for row in connection.execute(
                    "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? "
                    "AND sql IS NOT NULL",
                    (table,),
                )
                if "organization_id" not in row[0]
            ]
            without_column = "\n".join(
                line for line in ddl.splitlines() if "organization_id" not in line
            )
            # Removing a middle column leaves the line before the closing
            # paren ending in a comma.
            without_column = re.sub(r",(\s*\))", r"\1", without_column)
            columns = [
                row[1]
                for row in connection.execute(f"PRAGMA table_info({table})")
                if row[1] != "organization_id"
            ]
            column_list = ", ".join(columns)
            connection.execute(f"ALTER TABLE {table} RENAME TO {table}_pre_sprint")
            connection.execute(without_column)
            connection.execute(
                f"INSERT INTO {table} ({column_list}) SELECT {column_list} "
                f"FROM {table}_pre_sprint"
            )
            connection.execute(f"DROP TABLE {table}_pre_sprint")
            for index in indexes:
                connection.execute(index)
        connection.execute("DROP TABLE organization")
        connection.commit()
    finally:
        connection.close()


# --- the migration (ADR-0063) -----------------------------------------


def test_a_pre_sprint_database_opens_and_lands_on_the_default_organization(
    tmp_path: Path,
) -> None:
    """The test that decides whether every existing install survives.

    An assessment and a document written by an older build carry no
    organisation at all. If the migration is wrong, the failure is not a
    wrong answer -- it is a database that will not load.
    """
    repo = _repo(tmp_path)
    assessment = repo.create_assessment(name="Legacy", framework_name="C2M2")
    repo.create_document(_document("doc-1", DEFAULT_ORGANIZATION_ID))
    _regress_to_pre_sprint_schema(tmp_path / "assessments.db")

    reopened = AssessmentRepository(tmp_path / "assessments.db")

    migrated = reopened.get_assessment(assessment.id)
    assert migrated is not None
    assert migrated.organization_id == DEFAULT_ORGANIZATION_ID
    document = reopened.get_document("doc-1")
    assert document is not None
    assert document.organization_id == DEFAULT_ORGANIZATION_ID


def test_the_migration_leaves_evidence_and_associations_intact(tmp_path: Path) -> None:
    # The organisation column is new; nothing else about the record is,
    # and a migration that quietly dropped an evidence link would be a
    # far worse outcome than one that failed loudly.
    repo = _repo(tmp_path)
    assessment = repo.create_assessment(name="Legacy", framework_name="C2M2")
    repo.create_document(_document("doc-1", DEFAULT_ORGANIZATION_ID))
    repo.add_evidence_link(
        EvidenceLink(
            assessment_id=assessment.id,
            document_id="doc-1",
            practice_reference="AM-1a",
            source=EvidenceSource.MANUAL,
            review_status=EvidenceReviewStatus.ACCEPTED,
        )
    )
    repo.attach_document(assessment.id, "doc-1")
    _regress_to_pre_sprint_schema(tmp_path / "assessments.db")

    reopened = AssessmentRepository(tmp_path / "assessments.db")

    assert len(reopened.evidence_for_assessment(assessment.id)) == 1
    assert reopened.attached_document_ids(assessment.id) == ["doc-1"]


def test_the_migration_is_idempotent(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assessment = repo.create_assessment(name="Legacy", framework_name="C2M2")
    _regress_to_pre_sprint_schema(tmp_path / "assessments.db")

    AssessmentRepository(tmp_path / "assessments.db")
    reopened = AssessmentRepository(tmp_path / "assessments.db")

    assert len(reopened.list_organizations()) == 1
    migrated = reopened.get_assessment(assessment.id)
    assert migrated is not None
    assert migrated.organization_id == DEFAULT_ORGANIZATION_ID


def test_a_fresh_database_gets_exactly_one_organization(tmp_path: Path) -> None:
    # So the single-organisation deployment the charter scopes works
    # without anyone having to create something first.
    repo = _repo(tmp_path)

    organizations = repo.list_organizations()

    assert [(o.id, o.name) for o in organizations] == [
        (DEFAULT_ORGANIZATION_ID, DEFAULT_ORGANIZATION_NAME)
    ]


def test_the_bootstrap_does_not_add_a_second_organization_to_a_populated_instance(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    repo.create_organization(name="Coastal Utility")

    reopened = AssessmentRepository(tmp_path / "assessments.db")

    assert len(reopened.list_organizations()) == 2


# --- resolving an organisation ----------------------------------------


def test_omitting_the_organization_is_allowed_while_exactly_one_exists(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)

    assessment = repo.create_assessment(name="Pilot", framework_name="C2M2")

    assert assessment.organization_id == DEFAULT_ORGANIZATION_ID


def test_omitting_the_organization_is_refused_once_a_second_exists(tmp_path: Path) -> None:
    """The boundary case, and the whole reason omission is conditional
    rather than a default: with two clients on one instance, guessing is
    exactly the failure R-39 describes."""
    repo = _repo(tmp_path)
    repo.create_organization(name="Coastal Utility")

    with pytest.raises(OrganizationRequiredError):
        repo.create_assessment(name="Pilot", framework_name="C2M2")


def test_an_unknown_organization_is_refused_rather_than_created(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    with pytest.raises(OrganizationNotFoundError):
        repo.create_assessment(
            name="Pilot", framework_name="C2M2", organization_id="no-such-organization"
        )


# --- the boundary itself ----------------------------------------------


def test_attaching_a_document_from_another_organization_is_refused(tmp_path: Path) -> None:
    """R-39 made executable. No service is involved: this is the direct
    repository call the risk register has described since Sprint 21."""
    repo = _repo(tmp_path)
    other = repo.create_organization(name="Coastal Utility")
    assessment = repo.create_assessment(
        name="Pilot", framework_name="C2M2", organization_id=DEFAULT_ORGANIZATION_ID
    )
    repo.create_document(_document("theirs", other.id))

    with pytest.raises(CrossOrganizationAttachmentError):
        repo.attach_document(assessment.id, "theirs")

    assert repo.attached_document_ids(assessment.id) == []


def test_attaching_a_document_from_the_same_organization_is_allowed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assessment = repo.create_assessment(name="Pilot", framework_name="C2M2")
    repo.create_document(_document("ours", DEFAULT_ORGANIZATION_ID))

    repo.attach_document(assessment.id, "ours")

    assert repo.attached_document_ids(assessment.id) == ["ours"]


def test_a_document_with_no_registry_row_is_still_attachable(tmp_path: Path) -> None:
    """27 of the 30 documents in the original corpus predate ADR-0039 and
    have no Document row to carry an organisation. Refusing them would
    break real assessments to enforce a boundary the data cannot express;
    the gap is disclosed in ADR-0063 and R-40 instead."""
    repo = _repo(tmp_path)
    assessment = repo.create_assessment(name="Pilot", framework_name="C2M2")

    repo.attach_document(assessment.id, "predates-the-registry")

    assert repo.attached_document_ids(assessment.id) == ["predates-the-registry"]


def test_the_refusal_is_logged_because_reaching_it_means_a_bypass(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # A backstop that fires silently stops being a backstop -- the same
    # reasoning ADR-0060 applied to the finalization guard.
    repo = _repo(tmp_path)
    other = repo.create_organization(name="Coastal Utility")
    assessment = repo.create_assessment(
        name="Pilot", framework_name="C2M2", organization_id=DEFAULT_ORGANIZATION_ID
    )
    repo.create_document(_document("theirs", other.id))

    with caplog.at_level("ERROR"), pytest.raises(CrossOrganizationAttachmentError):
        repo.attach_document(assessment.id, "theirs")

    assert "cross-organization attach" in caplog.text


# --- scoped lists -----------------------------------------------------


def test_listing_documents_never_returns_another_organizations_rows(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    other = repo.create_organization(name="Coastal Utility")
    repo.create_document(_document("ours", DEFAULT_ORGANIZATION_ID))
    repo.create_document(_document("theirs", other.id))

    ours = repo.list_documents(DEFAULT_ORGANIZATION_ID)

    assert [document.id for document in ours] == ["ours"]


def test_listing_assessments_never_returns_another_organizations_rows(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    other = repo.create_organization(name="Coastal Utility")
    repo.create_assessment(
        name="Ours", framework_name="C2M2", organization_id=DEFAULT_ORGANIZATION_ID
    )
    repo.create_assessment(name="Theirs", framework_name="C2M2", organization_id=other.id)

    ours = repo.list_assessments(DEFAULT_ORGANIZATION_ID)

    assert [assessment.name for assessment in ours] == ["Ours"]


def test_renaming_an_organization_moves_no_record(tmp_path: Path) -> None:
    """Which is why the seal covers the id and not the name."""
    repo = _repo(tmp_path)
    assessment = repo.create_assessment(name="Pilot", framework_name="C2M2")

    renamed = repo.rename_organization(DEFAULT_ORGANIZATION_ID, "Riverbend Power")

    assert renamed is not None
    assert renamed.name == "Riverbend Power"
    unchanged = repo.get_assessment(assessment.id)
    assert unchanged is not None
    assert unchanged.organization_id == DEFAULT_ORGANIZATION_ID
