# ADR-0046: Compensating delete for the orphaned-chunks ingestion gap

**Status:** Accepted
**Sprint:** 18 (post-audit follow-up, project-owner directive: "work on the CI pipeline, and the
chunks edge case, and the TLS in deployment stack" — this ADR covers the chunks edge case)
**Deciders:** Fraz Ahmed
**Related:** ADR-0044 (found and reproduced this gap, disclosed rather than fixed at the time),
ADR-0039 (`Document` registry), ADR-0037 (`VectorRepository` table-handle caching)

## Context

ADR-0044's failure-injection tests found and reproduced a real gap in `IngestionService.ingest()`:
chunks are written to the vector store (LanceDB) before the `Document` registry row is persisted
(SQLite). If the registry write fails after the vector-store write already succeeded, the chunks
were left permanently orphaned — fully functional for evidence linking (existence is checked
directly against the vector store, per ADR-0039's design, not the `Document` table), but invisible
to `GET /documents/{id}` and any UI surface that lists documents via the registry. ADR-0044
deliberately disclosed this rather than fixing it that sprint, and named the two options already
considered and rejected then: full two-phase-commit-style cross-store transactions (disproportionate
engineering effort for this project's scale) and reordering the writes (merely moves the same risk
to the other direction — a phantom `Document` row pointing at nonexistent chunks).

The project owner directed picking this back up this sprint, alongside TLS and a CI pipeline.

## Decision

Added `VectorRepository.delete_chunks_for_document(document_id)` (`repositories/vector_repository.py`),
using LanceDB's native `table.delete("document_id = '...'")` predicate delete — verified empirically
via a standalone script before relying on it in real code (matching this project's established
practice, e.g. ADR-0037/ADR-0042's own empirical LanceDB verification): confirmed it removes only the
targeted document's rows, leaves other documents' chunks untouched, and is a safe no-op if the table
doesn't exist yet or the document has no chunks.

`IngestionService.ingest()` now wraps the `create_document()` call in try/except. On failure, it
calls `delete_chunks_for_document()` for the chunks it just wrote, then re-raises the original
exception unchanged (never swallowed or replaced by a delete-side failure).

This is a **compensating action, not a real distributed transaction** — deliberately not claimed as
such. If the compensating delete itself also fails (e.g. both stores are degraded simultaneously),
the original orphaning can still occur. This residual risk is disclosed in code comments and covered
by a dedicated test rather than assumed away.

**That dedicated test caught a real bug, not just a hypothetical, on its first run**: the initial
implementation's `except Exception: ...; raise` wrapped the compensating delete in the same `except`
block as `create_document()`'s own failure, so when the delete itself also failed, its exception
(`_VectorStoreFailure`) silently replaced the original `create_document` exception
(`_DocumentStoreFailure`) instead of the original propagating — the caller would have seen the wrong
error, and the log message naming the *original* failure would have been emitted, but a different
exception type would have surfaced. Fixed by nesting the delete in its own inner try/except that logs
a second, distinct message on delete failure but re-raises the outer (original) exception
unconditionally via a bare `raise` at the outer level. A concrete instance of this project's own
"verify, don't assume" discipline: the residual-risk case was already described correctly in the code
comment and this ADR's own prose before the bug was found, but only writing and running the test that
actually exercises it caught the implementation not living up to its own claim.

## Rationale

1. **Smallest fix that actually closes the disclosed gap**, matching this project's established bias
   against overengineering (ADR-0044's own rejection of full two-phase commit). A compensating delete
   is a well-understood, proportionate pattern for a two-store system that doesn't otherwise need
   distributed-transaction machinery anywhere else in the codebase.
2. **Deletion, not reordering.** ADR-0044 already established that reordering the writes only moves
   the same risk to the opposite failure mode (a phantom registry row with no chunks, which is arguably
   worse — it would pass `GET /documents/{id}` but return zero evidence on every downstream lookup,
   a silent-looking failure rather than a loud 404). Compensating deletion keeps the existing,
   already-reasoned-about write order and only adds cleanup on the specific failure path.
3. **Honest about the residual risk rather than presenting this as a complete fix.** A "the delete
   might also fail" case is real and cheap to test, so it is tested and disclosed here and in the
   code comments, rather than silently assumed away — this project's standing discipline (e.g.
   ADR-0038's prompt-injection posture, ADR-0044's own disclosure practice) applied consistently.
4. **Verified the underlying LanceDB `delete()` predicate behavior empirically before depending on
   it**, rather than trusting the API surface from documentation alone — the same "verified over
   fabricated" discipline already used for `add_columns()` (ADR-0042) and `checkout_latest()`
   (ADR-0037).

## Consequences

- `backend/src/compliance_platform/repositories/vector_repository.py`: new
  `delete_chunks_for_document(document_id)` method.
- `backend/src/compliance_platform/services/ingestion_service.py`: `create_document()` call now
  wrapped in try/except with a compensating delete on failure, re-raising the original exception.
- `backend/src/compliance_platform/services/tests/test_ingestion_service.py`: `_FakeVectorRepository`
  gained a `fail_delete` toggle and `deleted_document_ids` tracking. The existing orphaned-chunks test
  (previously documenting the gap as unfixed) now confirms the compensating delete runs and the chunks
  are removed. A new test confirms that when the compensating delete itself also fails, the *original*
  `create_document` exception still propagates (never swallowed) — the disclosed residual-risk case.
- ADR-0044's Consequences section (orphaned-chunks finding) is superseded by this ADR for the
  fixed case; the residual risk (compensating delete also failing) remains a real, disclosed,
  unresolved edge case, now covered by a test rather than left as an unknown.
- No change to `ingest()`'s write ordering, API surface, or any other service.

## Alternatives considered

- **Two-phase-commit-style cross-store transaction spanning LanceDB and SQLite.** Rejected — see
  ADR-0044 Rationale #3 and Alternatives; a materially larger undertaking with no precedent elsewhere
  in this codebase, disproportionate to the actual failure rate of a local SQLite write.
- **Reorder writes (`Document` row first, then chunks).** Rejected — see Rationale #2; moves rather
  than removes the risk, to a failure mode that is arguably harder to notice.
- **Leave disclosed and unfixed, matching ADR-0044's original scope decision.** Rejected this sprint
  specifically because the project owner directed picking it back up now that a proportionate fix
  (compensating delete) was identified; ADR-0044's original disclosure was itself provisional
  ("not fixed this sprint," not "won't fix").
