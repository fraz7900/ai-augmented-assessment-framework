# ADR-0044: Failure-injection tests and complexity-scaling performance-regression tests

**Status:** Accepted — the orphaned-chunks finding below (Decision #3) was fixed in ADR-0046 (Sprint
18 follow-up); read ADR-0046 for the compensating-delete fix and its own disclosed residual risk.
**Sprint:** 18 (controlled-pilot readiness pass, follow-up to ADR-0033 through ADR-0043)
**Deciders:** Fraz Ahmed (project-owner directive: "dig into testing-infrastructure item," Section
A #13 of `docs/architecture/02-controlled-pilot-readiness-audit.md`)
**Related:** ADR-0033/ADR-0037 (the real O(total corpus) regression this ADR's performance tests
directly protect against), ADR-0039 (`Document` registry — where the failure-injection finding below
surfaces)

## Context

The audit (§A.13) named two remaining testing gaps after this sprint's other fixes: no
failure-injection tests (deliberately simulating an infrastructure dependency failing, to see whether
the system degrades cleanly or leaves inconsistent state) and no performance-regression tests (nothing
would automatically catch a reintroduction of a bug like ADR-0033's `chunks_for_document` O(total
corpus) regression). Both are open-ended in principle; this sprint scoped each to a small number of
concrete, high-value cases rather than attempting exhaustive coverage.

## Decision

### Failure injection

Extended `services/tests/test_ingestion_service.py`'s existing fakes (`_FakeEmbedder`,
`_FakeVectorRepository`, `_FakeDocumentRepository`) with opt-in failure toggles, and added three tests
simulating each infrastructure dependency failing partway through `IngestionService.ingest()`'s
multi-step parse → chunk → embed → write-vectors → write-document-registry pipeline:

1. Embedder failure → confirmed no chunks or document persisted (fails before any write).
2. Vector-store write failure → confirmed no document persisted (embedding work already happened, but
   no state was written to either store).
3. Document-registry write failure **after** the vector-store write already succeeded → **a real,
   reproduced gap, not fixed this sprint**: the chunks remain in the vector store, fully functional for
   evidence linking (existence is checked directly against the vector store, per ADR-0039's own
   design, not the `Document` table), but no `Document` registry row exists for them, so
   `GET /documents/{id}` would 404 for a document that otherwise works correctly. There is no
   cross-store transaction spanning LanceDB and SQLite to roll the vector-store write back.

### Performance regression

Added two tests to `repositories/tests/test_vector_repository.py`
(`test_chunks_for_document_latency_does_not_scale_with_unrelated_document_count`,
`test_search_within_documents_latency_does_not_scale_with_unrelated_document_count`) measuring the
**ratio** between a small-corpus and a >100x-larger-corpus latency for the same document-scoped
lookup — not an absolute wall-clock threshold. Both call sites use a `.where(...)`-filtered native
LanceDB query (the same shape ADR-0033's fix introduced for `chunks_for_document`); a regression back
to a full-table-load pattern would produce a slowdown proportional to corpus growth (>100x here),
which an 8x ratio ceiling would catch with wide margin. Each measurement includes a 10-call warm-up
before timing 50 calls, to exclude cold-open/first-query overhead — confirmed empirically necessary:
an initial version of this test without warm-up showed the SMALL-corpus measurement as *slower* than
the large-corpus one, an artifact of first-call overhead dominating a tiny sample, not a real signal.
Verified stable across repeated runs in this environment (ratio consistently ~1.5-2.1x for the actual,
correctly-fixed implementation) before choosing the 8x ceiling.

## Rationale

1. **Choosing a complexity-scaling ratio over an absolute wall-clock threshold is the only design that
   can be reliable in this project's actual development environment.** `AGENTS.md` and
   ADR-0033/ADR-0037 already document this WSL2/OneDrive-mounted-filesystem environment as too noisy
   for absolute timing assertions; a ratio between two measurements taken back-to-back in the same
   process is far more robust to that noise while still being exactly the right shape to catch the one
   real regression class this project has already experienced once.
2. **Verifying the warm-up requirement empirically, rather than assuming reasonable measurement
   hygiene, caught a real design flaw in an earlier draft of this test before it shipped** — the same
   "verify, don't assume" discipline this project's own benchmark work (ADR-0033) already established.
3. **Documenting the orphaned-chunks finding rather than fixing it is a deliberate, disclosed scope
   decision, not an oversight.** Fixing it properly would require either a genuine two-phase-commit-
   style coordination across LanceDB and SQLite (a materially larger undertaking, and a new kind of
   cross-store transaction this codebase has never needed before) or reordering the writes (persist the
   `Document` row first, then the chunks — which merely moves the same risk to the other direction: a
   vector-store write failure after a successful `Document` write would then leave a registry entry
   pointing at chunks that don't exist). Neither is a quick fix, and shipping either without properly
   verifying it doesn't introduce a *different* inconsistency would repeat exactly the "unverified
   fix" mistake this project's discipline warns against.
4. **Scoping failure injection to `IngestionService`'s one genuinely multi-step, multi-store pipeline**,
   rather than spreading thin across every service method, matches where this class of risk actually
   concentrates — most other service methods are single-write operations where Python's normal
   exception propagation already provides the relevant guarantee (confirmed, not merely assumed, by
   this project's own lack of blanket try/except patterns anywhere in `assessment_service.py`'s
   mutation methods).

## Consequences

- `backend/src/compliance_platform/services/tests/test_ingestion_service.py`: `_FakeEmbedder`,
  `_FakeVectorRepository`, `_FakeDocumentRepository` gain failure-injection toggles; 3 new tests.
- `backend/src/compliance_platform/repositories/tests/test_vector_repository.py`: 2 new
  complexity-scaling regression tests, `_bulk_chunks`/`_measure_chunks_for_document` helpers.
- `docs/architecture/02-controlled-pilot-readiness-audit.md` §A.13: updated with what was delivered
  and the real orphaned-chunks finding, disclosed as unfixed.
- **A real, known limitation is now documented and covered by a reproducing test, where before it was
  an unknown risk**: a document-registry write failure after a successful vector-store write during
  ingestion leaves orphaned-but-functional chunks. Not fixed this sprint.
- **No CI pipeline was added.** These tests run as part of the existing manual `pytest -q` invocation;
  nothing automatically runs them on push. A real, disclosed, separate gap from what this ADR
  addresses — the audit's own §A.13 entry now names it explicitly rather than implying test existence
  alone solves "no performance-regression testing."
- **No change to `ingestion_service.py`'s actual write ordering or any application behavior** — this
  ADR is testing infrastructure only.

## Alternatives considered

- **Reorder `ingestion_service.py` to write the `Document` registry row before the vector-store
  chunks, so a failure leaves a "phantom" Document with no chunks instead of orphaned chunks with no
  Document.** Rejected — see Rationale #3; this doesn't eliminate the inconsistency, it only changes
  which side ends up orphaned, and swapping the order without separately verifying the new failure
  mode's own consequences would be exactly the kind of unverified change this project avoids.
- **Add a full CI pipeline (e.g. GitHub Actions) running the whole suite on every push, as part of
  "testing infrastructure."** Deferred, not rejected — a real, valuable next step, but a materially
  different kind of work (repository/CI configuration, secrets, runner selection) than the two testing
  gaps actually named in the audit's §A.13 line item; disclosed explicitly rather than silently
  bundled in or silently dropped.
- **Use absolute wall-clock thresholds (e.g. "chunks_for_document must complete in under 200ms")
  for the performance-regression tests.** Rejected — see Rationale #1; this environment's own
  documented noise characteristics make that design unreliable, and a flaky test that fails on
  unrelated environment noise trains contributors to ignore failures, which is worse than no test.
- **Attempt exhaustive failure-injection coverage across every service method.** Rejected — see
  Rationale #4; the concentrated risk is in genuinely multi-step, multi-store operations, and most of
  this codebase's service methods are not that shape.
