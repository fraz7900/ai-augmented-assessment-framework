"""Centralized exception -> HTTP status mapping (Sprint 9 refactor).

Registers a FastAPI exception handler once per domain exception type,
at the app level, for every custom exception that maps to the same
HTTP status code everywhere it is raised. Before this module existed,
api/assessments.py caught AssessmentNotFoundError in 12 separate
try/except blocks (always -> 404), FrameworkScoringUnavailableError in
5 (always -> 422), AssessmentFinalizedError in 3 (always -> 409), and
so on — a real, measured duplication found via a Sprint 9 code review,
not a hypothetical one. An endpoint that lets one of these exceptions
propagate now gets the correct response automatically; it no longer
needs to catch it itself. See ADR-0015.

Bare ValueError is deliberately NOT registered here: it is too generic
a type to intercept globally (many unrelated bugs raise plain
ValueError), so the one place that needs it
(api/assessments.py's review_evidence, for a missing
corrected_practice_reference) still catches it locally.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from compliance_platform.core.errors import OrganizationRequiredError
from compliance_platform.services.assessment_service import (
    AssessmentFinalizedError,
    AssessmentNotFoundError,
    AssessmentNotReadyForFinalizationError,
    ChatEngineUnavailableError,
    CrossOrganizationAttachmentError,
    DocumentNotAttachedError,
    DocumentNotFoundError,
    DocumentStillCitedError,
    EvidenceAlreadyReviewedError,
    EvidenceDocumentNotIngestedError,
    EvidenceLinkNotFoundError,
    EvidenceRequestNotFoundError,
    FrameworkScoringUnavailableError,
    InvalidPracticeReferenceError,
    InvalidReviewDecisionError,
    InvalidStatusTransitionError,
    MappingEngineUnavailableError,
    MissingEvidenceRequestNoteError,
    MissingFindingRationaleError,
    OrganizationNameRequiredError,
    OrganizationNameTakenError,
    OrganizationNotFoundError,
    SanitizationApprovalStaleError,
    SanitizationNotApprovedError,
    UnknownFrameworkVersionError,
)

_STATUS_CODE_BY_EXCEPTION: dict[type[Exception], int] = {
    AssessmentNotFoundError: 404,
    DocumentNotFoundError: 404,
    OrganizationNotFoundError: 404,
    EvidenceLinkNotFoundError: 404,
    EvidenceRequestNotFoundError: 404,
    AssessmentFinalizedError: 409,
    # Detaching a document that evidence still cites is a conflict
    # with the assessment's current state, not a bad request.
    DocumentStillCitedError: 409,
    # Attaching across an organisation boundary is a conflict with whose
    # record this is, not a malformed request (ADR-0063). A 409 also
    # reads correctly to the reviewer who caused it: the document is
    # real, the assessment is real, and they do not belong together.
    CrossOrganizationAttachmentError: 409,
    OrganizationNameTakenError: 409,
    DocumentNotAttachedError: 404,
    AssessmentNotReadyForFinalizationError: 409,
    EvidenceAlreadyReviewedError: 409,
    InvalidStatusTransitionError: 409,
    SanitizationApprovalStaleError: 409,
    FrameworkScoringUnavailableError: 422,
    EvidenceDocumentNotIngestedError: 422,
    InvalidPracticeReferenceError: 422,
    UnknownFrameworkVersionError: 422,
    InvalidReviewDecisionError: 400,
    # Not naming an organisation when more than one exists is a request
    # the server cannot answer, not a permission problem.
    OrganizationRequiredError: 400,
    OrganizationNameRequiredError: 400,
    MissingFindingRationaleError: 400,
    MissingEvidenceRequestNoteError: 400,
    MappingEngineUnavailableError: 503,
    ChatEngineUnavailableError: 503,
    SanitizationNotApprovedError: 412,
}


_logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    for exception_type, status_code in _STATUS_CODE_BY_EXCEPTION.items():

        def handler(
            request: Request, exc: Exception, status_code: int = status_code
        ) -> JSONResponse:
            # Every domain exception handled here used to vanish into a
            # JSON response with zero server-side record (security
            # hardening, controlled-pilot readiness audit §A.12: "zero
            # logging anywhere in the backend"). WARNING, not ERROR —
            # these are expected 4xx outcomes of normal operation
            # (a not-found ID, a finalized-assessment mutation attempt),
            # not application bugs. Never logs exc's full message body
            # if a future exception type embeds evidence/rationale text —
            # today's exception __str__ values are all IDs/status names,
            # not free text, so this is safe as written.
            _logger.warning(
                "%s -> %s %s: %s", request.method, status_code, request.url.path, exc
            )
            return JSONResponse(status_code=status_code, content={"detail": str(exc)})

        app.add_exception_handler(exception_type, handler)

    # Registered AFTER the loop so it replaces the generic handler for
    # this one type. A refused finalization has to say WHAT to fix in the
    # same machine-readable shape GET /finalization-readiness returns
    # (ADR-0058) — a caller should never have to parse the prose in
    # "detail" to discover that three AI proposals are unreviewed. The
    # blockers carry practice references and record ids only, never
    # evidence text, so this stays within the logging/response rule above.
    def not_ready_handler(request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, AssessmentNotReadyForFinalizationError)
        _logger.warning(
            "%s -> 409 %s: %s", request.method, request.url.path, exc
        )
        return JSONResponse(
            status_code=409,
            content={
                "detail": str(exc),
                "blockers": [blocker.model_dump(mode="json") for blocker in exc.blockers],
            },
        )

    app.add_exception_handler(AssessmentNotReadyForFinalizationError, not_ready_handler)
