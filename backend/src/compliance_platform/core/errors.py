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
