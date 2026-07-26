# ADR-0033: Scalability benchmark script; fixes VectorRepository.chunks_for_document's O(total corpus size) full-table-load bug

**Status:** Accepted
**Sprint:** 17 (controlled-pilot readiness pass, follow-up to ADR-0030/0031/0032)
**Deciders:** Fraz Ahmed (project-owner directive: "start on scalability benchmark," §F.6 of
`docs/architecture/02-controlled-pilot-readiness-audit.md`)
**Related:** ADR-0005 (LanceDB), ADR-0011 (retrieval-based mapping engine),
`docs/architecture/02-controlled-pilot-readiness-audit.md` §A.14/§F.6

## Context

This project had never measured behavior beyond a 2-document corpus (the entire contents of
`data/sample_evidence/`) before this sprint — confirmed by the controlled-pilot readiness audit. A
new benchmark script (`backend/scripts/benchmark_scalability.py`) measures ingestion throughput,
evidence-linking throughput, single-query retrieval latency, a full `propose-mappings` batch call,
dashboard read latency, report generation, storage growth, peak memory, and concurrent-read behavior,
against the real FastAPI app, SQLite, LanceDB, and ONNX embedder — at 100 and 1,000 synthetic
documents.

**Running it found a real, reproducible bug**, not a hypothetical one: evidence-linking latency
degraded ~7x (207ms → 1,428ms per link) going from 100 to 1,000 documents. Tracing the call path
(`services/assessment_service.py.link_evidence` → `repositories/vector_repository.py
.chunks_for_document`) found the cause immediately:

```python
def chunks_for_document(self, document_id: str) -> list[dict[str, Any]]:
    table = self._open_existing_table()
    if table is None:
        return []
    df = table.to_pandas()                              # loads EVERY row, every document
    matched = df[df["document_id"] == document_id]       # filters in Python, after the fact
    return matched.drop(columns=["vector"]).to_dict(orient="records")
```

`table.to_pandas()` materializes the entire vector store — every chunk from every document, including
the full 384-dimension vector for each — into memory, on every single call, regardless of how many
chunks the target document actually has. This is an O(total corpus size) operation for what should be
an O(this document's own chunk count) lookup, and it sits directly on `link_evidence`'s hot path
(called on every evidence link to confirm the target document was actually ingested).

The benchmark's other headline number — single-query retrieval latency degrading from 95ms to
~4,000ms (100 → 1,000 documents), and `propose-mappings` from 53 seconds to over 15 minutes — was
investigated the same way, but did **not** reproduce at anywhere near that magnitude in isolated
testing: a synthetic LanceDB table of matching size (3,000 rows, 384-dim vectors), queried with the
identical `document_id IN (...)`-filtered search pattern `services/mapping_service.py` uses, returned
in well under 100ms. The most likely explanation is this session's own measurement environment (a
long-running, heavily-loaded interactive WSL2 session on a OneDrive-synced filesystem — the same
"first uvicorn startup can take a couple of minutes... not a hang" characteristic `AGENTS.md` already
documents, and the same class of environment-dependent slowness R-9/R-11 in the risk register already
name), not a proven algorithmic defect in the query itself. Reporting that number as an equally-solid
finding would have been exactly the kind of unverified conclusion this project's discipline warns
against — see Consequences for how it's disclosed instead.

A second, smaller, high-confidence finding: `VectorRepository._open_existing_table()` re-opens the
LanceDB table from disk on **every** method call (no caching), measured at ~40-120ms of pure overhead
per call in isolated testing — multiplied by the ~350 calls a single `propose-mappings` request makes
(one search per not-yet-covered C2M2 practice), this is real, non-trivial overhead. **Not fixed this
sprint**: caching an opened table handle safely requires verifying it stays consistent with rows
written through a *different* handle in the same process (`add_chunks` opens its own table reference
via `_ensure_table()`) — a real data-staleness risk if gotten wrong, and not verified here under this
sprint's time constraints. Flagged as real, disclosed, unstarted follow-up work, not attempted
speculatively.

## Decision

1. **`backend/scripts/benchmark_scalability.py`** (new): a repeatable, standalone script (not a
   pytest test — see its own docstring) that measures the metrics named above at any corpus size,
   against the real application stack. Concurrent-read behavior is deliberately measured against a
   **real uvicorn subprocess with independent httpx clients**, not `TestClient` shared across worker
   threads — an earlier version of this measurement, using TestClient, reported a ~20x concurrent
   slowdown that did not reproduce against a real server; TestClient funnels calls from multiple
   external threads through one internal anyio portal/event loop, serializing far more than the real
   deployed app does. Reporting the TestClient number would itself have been an unverified
   deficiency.
2. **`VectorRepository.chunks_for_document` fixed**: now uses LanceDB's native
   `table.search().where(f"document_id = '{escaped_id}'").to_list()` — a server-side (Rust/Arrow-
   level) filter — instead of `to_pandas()` plus a Python-side filter. Same public contract (list of
   dicts, `vector` field dropped), verified by the existing `test_chunks_for_document_filters_by_document_id`
   test, which required no changes to keep passing.
3. **`_open_existing_table()`'s per-call re-open overhead is disclosed, not fixed**, per the
   Context section's staleness-risk reasoning — a deliberate decision not to ship a caching change
   without first proving it can't silently serve stale results after a concurrent write, consistent
   with this project's "fail closed when evidence/assessment state is uncertain" principle.
4. **The retrieval-latency-at-scale number is reported with an explicit confidence caveat**, not
   presented as equally solid to the `chunks_for_document` finding — see Consequences.

## Rationale

1. **This is exactly the "benchmark before optimizing" sequence the project's own discipline
   requires**: a real measurement surfaced a real bug with an unambiguous root cause (traced to one
   specific line, reproduced in isolation, fixed, verified against the existing test suite) — not a
   fix applied on suspicion. The `chunks_for_document` fix is the direct, disciplined output of that
   process.
2. **Refusing to over-claim the retrieval-latency finding is itself the correct application of the
   same discipline.** Finding a number that looks alarming and then NOT reproducing it in a controlled
   isolated test is real, useful information — it means the number as measured is not yet trustworthy
   evidence of an architectural defect, and asserting otherwise would be exactly the "speculative
   deficiency" the project's engineering discipline instructs against.
3. **Not fixing the table re-open overhead this sprint is a deliberate scope boundary, not an
   oversight**: a caching change touches the correctness of every read in the retrieval path (ADR-0011's
   core mapping engine), and shipping it without first verifying cache-invalidation safety under
   concurrent writes would risk a category of bug (silently stale evidence search results) far more
   serious than the latency it would fix.

## Consequences

- `backend/scripts/benchmark_scalability.py`: new file. Run manually (see its own docstring); not
  part of CI or the pytest suite (a performance benchmark script, not a correctness test).
- `repositories/vector_repository.py`: `chunks_for_document` rewritten; `add_chunks`, `search`,
  `search_within_documents`, `count` unchanged.
- Existing test suite: `repositories/tests/test_vector_repository.py`'s existing
  `test_chunks_for_document_filters_by_document_id` continues to pass unmodified, confirming the fix
  preserves the method's contract. No other test files needed changes.
- `docs/architecture/02-controlled-pilot-readiness-audit.md`: §A.14 (Scalability) and the CPES
  scalability line updated with real measured numbers (100 vs. 1,000 documents) instead of "not
  measured"; §F.6 marked delivered, with the table-reopen-overhead and retrieval-latency-confidence
  findings carried forward as named, bounded follow-up items rather than closed or silently dropped.
- **No change to `services/mapping_service.py` or the retrieval algorithm itself** — the one query
  pattern investigated (`document_id IN (...)` filtered vector search) was not disproven as sound by
  this sprint's evidence; a future sprint re-measuring on a dedicated (non-shared, non-WSL2-OneDrive)
  host is the right next step before considering any change there.

## Alternatives considered

- **Ship a table-handle-caching fix for the ~40-120ms per-call `open_table()` overhead this sprint
  too.** Rejected — real and measured, but the safe version of this fix (verifying cache freshness
  under concurrent writes) needs its own dedicated verification pass, not a quick addition once
  correctness risk was identified; see Context.
- **Present the 100→1,000-document retrieval latency degradation (95ms → ~4s) as a confirmed
  architectural bottleneck and redesign `search_within_documents` accordingly.** Rejected — isolated
  reproduction attempts did not support this conclusion at anywhere near the same magnitude; doing so
  would have substituted a plausible-sounding but unverified story for the real, disclosed uncertainty
  the actual evidence supports.
- **Treat the whole scalability pass as blocked until a clean benchmarking host is available.**
  Rejected — the `chunks_for_document` bug was real, reproducible, and fixable regardless of
  environment noise elsewhere in the same run; waiting would have meant sitting on a confirmed,
  low-risk fix for no benefit.
