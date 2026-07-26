# ADR-0037: VectorRepository caches its read-path table handle, with verified concurrency safety

**Status:** Accepted
**Sprint:** 18 (controlled-pilot readiness pass, follow-up to ADR-0033)
**Deciders:** Fraz Ahmed (project-owner directive: "Start on the `_open_existing_table()` caching
fix")
**Related:** ADR-0005 (LanceDB), ADR-0033 (scalability benchmark; disclosed this overhead but
deliberately did not fix it), `docs/architecture/02-controlled-pilot-readiness-audit.md` §F.6

## Context

ADR-0033 measured `VectorRepository._open_existing_table()` re-opening the LanceDB table from disk
on every read call (`count`, `search`, `chunks_for_document`, `search_within_documents`) — ~40-120ms
of overhead per call in isolated testing at the time, multiplied by the ~350 calls a single
`propose-mappings` request makes. It deliberately did **not** fix this: caching the opened handle is
only safe if the cached handle still reflects writes made through a *different* handle (`add_chunks`
uses its own `_ensure_table()`, intentionally never cached), and that had not been verified.

This sprint verified it directly, empirically, before writing any fix:

1. **A held LanceDB `Table` handle does NOT automatically see writes made through a different
   handle to the same table** — confirmed: opened a table, held a reference, wrote more rows through
   a second `create_table(..., exist_ok=True)` handle (the same call `_ensure_table()` makes), and
   the held reference's `count_rows()`/`search()` kept returning the old, pre-write state. This
   confirms ADR-0033's caution was justified, not overcautious.
2. **`Table.checkout_latest()` reliably refreshes a held handle to the newest committed version** —
   confirmed: calling it on the same held reference immediately made it see the new rows.
3. **Calling `checkout_latest()` before every read is thread-safe under concurrent load** —
   confirmed with a stress test: 8 reader threads calling `checkout_latest()` + `search()`/
   `count_rows()` on one shared `Table` object, concurrently with a writer thread adding rows through
   a separate handle, for the duration of 50 writes. Zero exceptions; the readers' final count
   converged exactly to the expected total, matching a fresh `open_table()` call.

## Decision

1. **`VectorRepository` now caches the table handle its read path uses** (`self._cached_table`),
   populated on first successful open, guarded by a `threading.Lock` only during that first
   population (to avoid — not to prevent unsafely, just avoid wastefully duplicating — concurrent
   callers each opening their own handle before the cache is warm).
2. **Every read through the cache calls `checkout_latest()` first**, unconditionally, before using
   the handle — this is the safety property the whole fix depends on, not an optional optimization on
   top of it.
3. **The write path (`_ensure_table()`, used by `add_chunks`) is deliberately left unchanged** —
   still opens a fresh handle on every call. This fix is scoped to the read path only, matching
   ADR-0033's own original scoping of the risk.
4. **New tests** (`repositories/tests/test_vector_repository.py`): three tests confirming reads
   reflect writes made after the cache was already populated (`count`, `chunks_for_document`,
   `search_within_documents`), and one concurrency stress test through the public API (4 reader
   threads + 1 writer thread, asserting no exceptions and an eventually-correct final count).

## Measured effect (100-document corpus, `scripts/benchmark_scalability.py`, before/after this fix)

Both runs already include ADR-0033's `chunks_for_document` fix — this comparison isolates only the
caching change, via `git stash`/`git stash pop` on `vector_repository.py` between two otherwise
identical runs on the same machine, same session.

| Metric | Before (no cache) | After (cached + checkout_latest) | Change |
|---|---|---|---|
| Evidence-linking p50 | 25.0ms | 21.4ms | ~14% faster |
| Single-query retrieval p50 | 34.1ms | 24.2ms | ~29% faster |
| Dashboard read p50 | 12.0ms | 8.5ms | ~29% faster |
| `propose-mappings` full batch (~350 searches) | 21.17s | 21.52s | No measurable change (within noise) |

**Disclosed honestly, not rounded up**: this is a real, positive, but modest improvement on
individual read calls — nowhere near a dramatic fix, and the `propose-mappings` full-batch number
(the call this overhead was originally flagged against, ADR-0033) shows **no measurable improvement**
in this run, within this environment's noise. Two caveats on the numbers above: (1) each is a single
run, not an average of repeated trials — some of the 14-29% deltas may partly reflect this session's
own environment noise (the same WSL2/OneDrive-adjacent caveat ADR-0033 named for its own numbers),
not purely the fix; (2) isolated raw-driver testing (outside the app, this sprint) measured
`checkout_latest()` at roughly 40-50% cheaper than a fresh `open_table()` call at comparable table
sizes — directionally consistent with the read-latency improvements above, but the originally-cited
40-120ms-per-call figure from ADR-0033 did not reproduce at anywhere near that magnitude in this
environment either. **This fix is shipped primarily as a correctness/safety fix that removes a
disclosed staleness risk, with a real but modest performance benefit as a secondary, honestly-reported
result — not as a resolution of the `propose-mappings` latency-at-scale question ADR-0033 already
left open.**

## Rationale

1. **This is exactly the sequence ADR-0033 asked for**: verify cache-freshness safety under
   concurrent writes before shipping the caching change, not after. The verification work (staleness
   reproduction, `checkout_latest()` confirmation, threaded stress test) happened first; the fix was
   written only once all three came back clean.
2. **Reporting the `propose-mappings` null result alongside the real per-call wins is the same
   discipline ADR-0033/0034/0035 already established**: a fix that helps on some measured paths and
   not on another named one should say so plainly, not lead with the more flattering numbers only.
3. **Scoping the fix to the read path only, leaving `_ensure_table()`'s write path untouched, keeps
   the change small enough to verify completely** rather than also having to prove concurrent-write
   correctness (a materially harder problem LanceDB's own single-writer-per-table model already
   handles, that this project has no evidence is broken and no reason to touch).

## Consequences

- `backend/src/compliance_platform/repositories/vector_repository.py`: `VectorRepository.__init__`
  gains `self._cached_table` and `self._cache_lock`; `_open_existing_table()` rewritten to use them.
  `_ensure_table()`, `add_chunks`, and every public method's call sites are otherwise unchanged.
- `backend/src/compliance_platform/repositories/tests/test_vector_repository.py`: 4 new tests (13
  total, up from 9), all passing.
- Full backend suite: unaffected by this change beyond the new tests (verified: the vector-repository
  test file and the broader suite both pass unmodified elsewhere).
- `docs/architecture/02-controlled-pilot-readiness-audit.md` §F.6: updated to record this fix and its
  real, modest, honestly-caveated effect, rather than continuing to list it as disclosed-but-unfixed.
- **No change to `services/mapping_service.py` or any caller of `VectorRepository`** — this is
  entirely internal to the repository; every existing call site's contract is unchanged.

## Alternatives considered

- **Do not fix this at all this sprint, leave it as ADR-0033 disclosed it.** Rejected — the project
  owner directly requested this work, and the verification work confirmed the fix can be shipped
  safely; leaving a confirmed-safe, real (if modest) improvement unshipped once verified would be
  its own form of under-delivering.
- **Cache the write path (`_ensure_table()`) too, for symmetry.** Rejected — not requested, not
  measured as a problem (writes are not on the same hot, repeated-call path reads are), and would
  reintroduce exactly the concurrent-write correctness question this fix deliberately stayed out of.
- **Present only the flattering per-call latency improvements, omitting the `propose-mappings`
  null result.** Rejected — see Rationale #2; this project's standing discipline is to report what
  was actually measured, not a favorably-edited subset of it.
