# ADR-0015: Sprint 9's testing/refactoring pass — measured fixes only, no speculative cleanup

**Status:** Accepted
**Sprint:** 9
**Deciders:** Fraz Ahmed
**Related:** `docs/product/prioritization.md` ("Testing, refactoring, documentation pass"), R-13, ADR-0011 (R-13's origin)

## Context

Sprint 9's backlog entry has no fixed acceptance criteria — it is explicitly "already partially
happening every sprint... a dedicated pass still adds value before calling the MVP done." Without a
feature to build, the risk is doing unfocused busywork or refactoring for its own sake, which this
project's own standing discipline ("fix measured problems, not hypothetical ones" — see R-13, R-20's
own resolution language) argues against. This sprint's actual scope was therefore derived from real
measurements taken first, not decided in advance: a full-suite timing run, a `pytest --cov`
coverage report, and a manual scan of `api/assessments.py` for repeated exception-handling code —
each producing a concrete, numbered finding before any code changed.

## Decision

1. **Fixed a real, measured 46% test-suite runtime regression, exactly as R-13 had already
   diagnosed but never implemented.** `tests/test_assessment_api_integration.py` and
   `tests/test_ingestion_api_integration.py`'s `client` fixtures cleared
   `dependencies.get_cached_embedder`'s cache before and after every single test, forcing a fresh
   ~0.4s ONNX-session reload each time — measured directly (`LocalSemanticEmbedder()` construction:
   0.39-0.45s across three trials) — even though the embedder's configuration never varies between
   tests (only `vector_store_dir`/`assessments_db_path` do). Removed the embedder from both fixtures'
   per-test cache-clear list. Full suite: 127.36s → 68.59s for the same 153 tests, verified by
   re-running twice.
2. **Closed real, measured test-coverage gaps, prioritized by size and reachability, not chased to
   100%.** `pytest --cov-report=term-missing` showed `api/assessments.py` at 79% (an outlier — every
   other file was 85-100%) and `repositories/vector_repository.py` at 86% with *no dedicated test
   file at all*. Added: 8 new API integration tests covering every previously-untested
   `AssessmentNotFoundError`/`FrameworkScoringUnavailableError`/`AssessmentFinalizedError`/
   `InvalidReviewDecisionError`/`InvalidPracticeReferenceError` response path; 4 new
   `AssessmentService.answer_question` unit tests (this method had zero direct unit-test coverage
   since Sprint 8); a new `repositories/tests/test_vector_repository.py` (previously nonexistent);
   2 new `framework_loader.py` tests for `require()`'s own failure path; 4 new `document_parsers.py`
   tests for the "cannot even open the file" failure mode in both PDF and DOCX. Result:
   `api/assessments.py` 79% → 97%, `assessment_service.py` 98% → 100%, `vector_repository.py` and
   `framework_loader.py` 86%/88% → 100%, overall 94% → 98%. The two remaining gaps in
   `api/assessments.py` (`MappingEngineUnavailableError`/`ChatEngineUnavailableError`, both requiring
   `embedder=None`) are not reachable through the live app's real dependency injection and are
   already covered at the service-unit-test layer — a residual, understood gap, not an oversight.
3. **Centralized exception-to-HTTP-status mapping into one new module
   (`api/error_handlers.py`), removing ~25 duplicated `try/except` blocks from
   `api/assessments.py`.** A manual scan found `AssessmentNotFoundError` caught identically (always
   → 404) in 12 separate places, `FrameworkScoringUnavailableError` in 5 (always → 422),
   `AssessmentFinalizedError` in 3 (always → 409) — real, counted duplication, not an aesthetic
   guess. Registered one FastAPI exception handler per custom exception type, at the app level
   (`main.py`); every endpoint that only needed to catch-and-translate now simply lets the exception
   propagate. `api/assessments.py`: 328 → 250 lines. Bare `ValueError` (used once, for
   `review_evidence`'s missing `corrected_practice_reference` case) was deliberately *not* added to
   the global registry — it is too generic a builtin type to intercept app-wide without risking
   silently reclassifying an unrelated bug as a deliberate 400 — so that one case still has a local
   `try/except` in `review_evidence` itself.
4. **No other refactor was attempted.** `assessment_service.py` (473 lines, the largest file) was
   inspected and found to already be a thin façade over `report_service.py`/`export_service.py`/
   `chat_service.py`/`mapping_service.py`'s actual logic, at 100% test coverage post-fix — a
   plausible-looking "this class does too much" instinct did not survive being checked against
   actual duplication or actual test/comprehension difficulty, so it was left alone.

## Rationale

1. **A prior risk register entry (R-13) had already done the diagnostic work and named the fix
   ("a session-scoped test fixture for the embedder would resolve it") two sprints before this one
   implemented it.** Re-measuring rather than re-guessing confirmed the diagnosis was still correct
   and quantified the actual win, consistent with this project's standing "verify before deciding"
   practice (ADR-0009/0010/0011's shared discipline, applied here to test infrastructure).
2. **Coverage was treated as a signal to investigate, not a score to maximize.** `api/assessments.py`
   at 79% against a 85-100% baseline everywhere else was the only real outlier and got real
   investigation; the two residual gaps in the same file (both requiring an unreachable
   dependency-injection state) were left as a documented, understood limit rather than contorted
   into an artificial 100% via mocking the app's real DI wiring for its own sake.
3. **A global FastAPI exception handler is the idiomatic, well-established mechanism for exactly
   this scenario** (a fixed set of domain exceptions that always map to the same status code
   regardless of which endpoint raised them) — not a novel abstraction invented for this codebase.
   The refactor was done with a full, passing 181-test suite as a safety net (built earlier in this
   same sprint), and verified live against a running server afterward, not merely by unit test.
4. **Bare `ValueError` was excluded from the global registry on purpose, not by oversight.** Unlike
   every other exception type here, `ValueError` is a generic builtin that unrelated code anywhere
   in the app could raise for unrelated reasons; a global handler for it would risk quietly turning
   a real bug into a client-facing 400 with no visibility. Keeping its one legitimate use local,
   explicit, and narrowly scoped is more honest than a broader mapping that "happens to work" today.

## Consequences

- `backend/tests/test_assessment_api_integration.py` and `test_ingestion_api_integration.py`: the
  embedder is now a session-lifetime singleton across the whole test run (never cache-cleared),
  documented inline as a deliberate choice, not an accidental omission.
- New files: `backend/src/compliance_platform/repositories/tests/test_vector_repository.py`,
  `backend/src/compliance_platform/api/error_handlers.py`.
- `backend/src/compliance_platform/api/assessments.py` no longer imports any of the custom
  `assessment_service` exception classes — they are only referenced from `error_handlers.py` now.
- `backend/src/compliance_platform/main.py` calls `register_exception_handlers(app)` once at
  startup.
- `api/README.md` updated: the stale "Planned: `mappings.py` (Sprint 5), `reports.py` (Sprint 7)"
  note (those features shipped inside `assessments.py` instead, three and two sprints ago
  respectively) is corrected, and `error_handlers.py` is documented.
- 181 tests passing (up from 153 at Sprint 8's close), `ruff check` clean, full suite runtime 113s
  (down from what would have been ~145s+ without the fixture fix, given the proportional increase
  from 28 new tests).

## Alternatives considered

- **Chase 100% line coverage across every file.** Rejected — several residual gaps (a rare
  mid-extraction `pypdf` exception per PDF page, an encoding-failure-then-still-empty edge case, two
  scoring-service defensive branches for framework shapes that don't occur in real transcribed data)
  would have required either contrived test setups or mocking library internals for a benefit no
  real usage pattern has ever exercised — coverage theater, not a measured improvement.
- **Split `assessment_service.py` into multiple smaller service-façade classes.** Considered and
  rejected — see Decision 4. No duplication or comprehension problem was actually found; the file's
  size is proportional to genuinely covering six sprints' worth of distinct, cohesive concerns behind
  one façade, which is the pattern the codebase has used consistently since Sprint 2, not new debt.
- **Register a global handler for bare `ValueError` too, for symmetry.** Rejected — see Rationale 4;
  symmetry is not itself a reason to widen a global handler to a generic exception type with no
  domain-specific meaning.
