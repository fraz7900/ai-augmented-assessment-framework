"""Domain exceptions shared by more than one layer.

Most of this project's exceptions live in
`services/assessment_service.py`, next to the rule they enforce, and
should stay there. This module exists for the few that a lower layer
also has to raise -- a repository cannot import from services without
creating an import cycle, and duplicating an exception class so each
layer can have its own would mean `except AssessmentFinalizedError`
silently failing to catch half of them.

`services/assessment_service.py` re-exports what it moved here, so
existing imports from the service keep working (ADR-0015's rule that a
refactor must not force unrelated call sites to change).
"""

from __future__ import annotations


class AssessmentFinalizedError(Exception):
    """A write was attempted against a finalized assessment.

    Raised by AssessmentService before any work is done, and again by
    AssessmentRepository inside the transaction that would perform the
    write. The second is a backstop, not a duplicate: see
    `AssessmentRepository._assert_writable` for why one check cannot do
    both jobs.
    """

    def __init__(self, assessment_id: str) -> None:
        self.assessment_id = assessment_id
        super().__init__(
            f"Assessment '{assessment_id}' is finalized; its audit record can no longer "
            "be modified."
        )


class AssessmentAlreadySealedError(Exception):
    """An attempt to write a finalization seal over one that exists.

    Raised by the repository rather than the service because it guards
    an invariant of the stored record, not a workflow rule: a record
    that can be re-sealed is one where an edit can be covered up by
    recomputing the digest over the edited version, which would leave
    the seal looking valid and meaning nothing.
    """

    def __init__(self, assessment_id: str) -> None:
        self.assessment_id = assessment_id
        super().__init__(
            f"Assessment '{assessment_id}' already carries a finalization seal; a seal is "
            "written once and never replaced."
        )


class OrganizationNotFoundError(Exception):
    """An organisation id was named that does not exist (ADR-0063).

    Lives here rather than in services/ for the same reason
    AssessmentFinalizedError does: the repository resolves and validates
    organisation ids for both the assessment router and the ingestion
    router, and a repository cannot import from services without
    creating a cycle.
    """

    def __init__(self, organization_id: str) -> None:
        self.organization_id = organization_id
        super().__init__(f"Organization '{organization_id}' does not exist.")


class OrganizationRequiredError(Exception):
    """No organisation was named and more than one exists (ADR-0063).

    Omitting the organisation is allowed only while exactly one exists,
    because only then is there exactly one honest answer. The moment a
    second organisation is created, the convenience becomes the failure
    R-39 describes -- one client's work silently filed under another --
    so it stops being a default and starts being an error. This is the
    same reasoning ADR-0059 applied to upload size: the boundary case is
    where being wrong costs most, so it must not sit on the far side of
    a number (or a default) nobody can see.
    """

    def __init__(self, count: int) -> None:
        self.count = count
        super().__init__(
            f"This instance has {count} organizations, so organization_id must be given "
            "explicitly; it may only be omitted while exactly one exists."
        )


class EvidenceLinkNotFoundError(Exception):
    """An evidence link id did not resolve on this assessment.

    Moved here from services/ when bulk reject (ADR-0067) gave the
    repository a reason to raise it: that method validates every id
    inside the transaction that writes, so an unknown or
    wrong-assessment id aborts the whole batch instead of letting a
    caller believe it acted on rows it never touched.
    """

    def __init__(self, evidence_link_id: str) -> None:
        self.evidence_link_id = evidence_link_id
        super().__init__(f"Evidence link '{evidence_link_id}' not found on this assessment.")


class CrossOrganizationAttachmentError(Exception):
    """A document was attached to an assessment belonging to a different
    organisation (ADR-0063).

    Raised by AssessmentService before any work is done, and again by
    AssessmentRepository inside the transaction that performs the
    attach. The second is a backstop, not a duplicate, for exactly the
    reasons `AssessmentRepository._assert_writable` already documents --
    and this guarantee is the one R-39 is about, so it gets the same
    treatment as the finalization lock rather than a weaker one.
    """

    def __init__(self, assessment_id: str, document_id: str) -> None:
        self.assessment_id = assessment_id
        self.document_id = document_id
        super().__init__(
            f"Document '{document_id}' belongs to a different organization than assessment "
            f"'{assessment_id}'; evidence cannot cross an organization boundary."
        )
