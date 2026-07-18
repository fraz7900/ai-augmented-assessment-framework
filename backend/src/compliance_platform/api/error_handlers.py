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

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from compliance_platform.services.assessment_service import (
    AssessmentFinalizedError,
    AssessmentNotFoundError,
    ChatEngineUnavailableError,
    EvidenceAlreadyReviewedError,
    EvidenceDocumentNotIngestedError,
    EvidenceLinkNotFoundError,
    FrameworkScoringUnavailableError,
    InvalidPracticeReferenceError,
    InvalidReviewDecisionError,
    InvalidStatusTransitionError,
    MappingEngineUnavailableError,
)

_STATUS_CODE_BY_EXCEPTION: dict[type[Exception], int] = {
    AssessmentNotFoundError: 404,
    EvidenceLinkNotFoundError: 404,
    AssessmentFinalizedError: 409,
    EvidenceAlreadyReviewedError: 409,
    InvalidStatusTransitionError: 409,
    FrameworkScoringUnavailableError: 422,
    EvidenceDocumentNotIngestedError: 422,
    InvalidPracticeReferenceError: 422,
    InvalidReviewDecisionError: 400,
    MappingEngineUnavailableError: 503,
    ChatEngineUnavailableError: 503,
}


def register_exception_handlers(app: FastAPI) -> None:
    for exception_type, status_code in _STATUS_CODE_BY_EXCEPTION.items():

        def handler(
            request: Request, exc: Exception, status_code: int = status_code
        ) -> JSONResponse:
            return JSONResponse(status_code=status_code, content={"detail": str(exc)})

        app.add_exception_handler(exception_type, handler)
