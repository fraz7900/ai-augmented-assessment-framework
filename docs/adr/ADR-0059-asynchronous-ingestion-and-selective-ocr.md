# ADR-0059: Ingest documents through a pollable job queue, and OCR only the pages that need it

**Status:** Accepted
**Sprint:** 21
**Deciders:** Fraz Ahmed
**Related:** ADR-0046 (compensating delete for orphaned chunks — the failure ordering this reuses
rather than re-derives), ADR-0055 (local OCR; `SUCCESS_OCR`), ADR-0056 (upload retention, written
only after the registry write succeeds), ADR-0042 (page-boundary provenance and `parser_version`),
ADR-0039 (the document registry), ADR-0058 (the closed-enum precedent this follows for failure
categories), ADR-0045/ADR-0047 (the nginx deployment whose read ceiling forced this)

## Context

**Ingestion held the HTTP request open for the whole parse/chunk/embed pass.** nginx closes a proxied
read at 300s (`deployment/frontend.nginx.conf`), which covers roughly 400 chunks or a 200-page
document at the measured ~0.7s per chunk. Past that the browser received a gateway timeout for an
ingestion that was still running — and there was no record the work had ever started, no way to
distinguish a timeout from a rejection, and nothing to poll. The documented remedy in that same
config file, written in Sprint 18, was already: *"the fix for that is background ingestion with a
job-status endpoint, not a bigger number."*

The ceiling is reachable with ordinary evidence for this product, not with a pathological input: a
505-page policy manual, or a deck needing OCR on most of its pages. And the observed user response
to an apparent failure is to upload again, which is how three copies of one document ended up
competing in retrieval (the incident behind `UploadProgress`).

**Separately, a part-scanned PDF paid the full scanned-document price.** `parse_pdf` chose between
"pypdf found text" and "OCR everything". A document with a real text layer on most pages and scanned
signature pages on three of them either lost those three pages entirely or had every page re-read by
OCR — replacing exact extracted text with an approximation of itself, at seconds per page, and
spending the `max_pages` OCR budget on pages that never needed it.

## Decision

### Asynchronous ingestion

1. **`POST /ingest/async`** records an `IngestionJob` and returns **202** with the job. 202, not 201:
   nothing exists yet except the intent to try.
2. **`GET /ingest/jobs` and `GET /ingest/jobs/{job_id}`** return the job; the client polls.
3. **`IngestionService.ingest()` is called unchanged.** The job service is a job record wrapped
   around the same call, so ADR-0046's compensating delete and ADR-0055's retain-after-registry-write
   ordering keep their exact sequence.
4. **One worker** (`ThreadPoolExecutor(max_workers=1)`), which also gives the queue FIFO order.
5. **`max_pending_ingestions` (default 10)** bounds the queue; exceeding it is **429**, not 503.
6. **Failures are recorded, never discarded**, under a closed `IngestionJobFailure` enum:
   `unsupported_document`, `unknown_superseded_document`, `too_large`, `interrupted`,
   `internal_error`. Human-readable detail lives beside it in `failure_message`.
7. **Jobs left `RUNNING` by a restart are swept to `interrupted`** on the next start (FastAPI
   `lifespan`), and the executor is shut down without waiting on exit.
8. **Oversized uploads are refused at submit time**, before a job row exists.
9. **The frontend uploads exclusively through the queue**, polls at 2s until the job settles, and
   lists recent jobs so a reviewer who navigated away can still find the outcome. The synchronous
   `POST /ingest` remains, unchanged and still tested.

### Selective OCR

10. **`ocr_pdf_page_texts` takes `only_pages`**, so a mixed document OCRs only the pages pypdf found
    no text on, and the `max_pages` budget counts pages actually recognised.
11. **A new `SUCCESS_PARTIAL_OCR` parse status**, distinct from `SUCCESS_OCR`, with a composite
    `parser_version` naming both pypdf and the OCR engine.
12. **A document that already parsed acceptably never becomes worse for having tried OCR**: if OCR
    is unavailable or recovers nothing, the pypdf text stands exactly as it was.

## Rationale

**Why the browser uses the queue for every upload, regardless of size.** A size threshold puts the
two paths' behaviour on opposite sides of a number nobody can see, and the boundary case — a 24MB
scan that OCRs for six minutes — is exactly where being wrong costs the most. One path also means one
set of states to get right in the UI.

**Why the synchronous endpoint stays.** It is correct for a caller that genuinely wants to block
until the work is done — a script, a test — and it is the browser specifically that cannot use it
safely. Removing it would be deleting a working interface to make a point.

**Why one worker.** Parsing, OCR and embedding are CPU-bound, and this is a single-user/small-team
local product (charter Section 12) that may be sharing a laptop with the browser driving it. Several
at once would not finish the queue sooner and would make the machine unusable while it happened.

**Why the queue is bounded.** The synchronous endpoint had natural backpressure: one request, one
upload, held only as long as the work took. Accepting uploads immediately removes that, and a queued
job holds its bytes in memory until a worker frees up. The bound is reintroduced deliberately rather
than assumed away — 429 says the server is fine and waiting is the right response.

**Why failure categories are a closed enum.** Same discipline as ADR-0058's blockers: the UI decides
whether a retry could possibly help, and parsing English to decide that breaks the first time the
wording improves. `interrupted` is the one category worth retrying verbatim, and only a machine-
readable value can say so.

**Why a failed job row survives.** A failed ingestion is exactly what an operator needs to see.
Discarding it would recreate the invisible-failure mode this whole change exists to remove.

**Why `SUCCESS_PARTIAL_OCR` is its own status.** "All of this is approximate" and "pages 3, 5 and 7
are approximate" are different instructions to a reviewer. Collapsing into `SUCCESS_OCR` makes a
mostly-exact document look wholly untrustworthy; collapsing into `SUCCESS` hides that any of it is
approximate — the defect the value was added to fix. `parser_version` names both engines for the same
reason: it is what ADR-0042 makes citations reproducible against, and only one of them read any given
page.

## Consequences

- A document larger than nginx's read ceiling can now be ingested at all. The ceiling still applies
  to `POST /ingest`, and `proxy_read_timeout` stays at 300s for it.
- The upload response no longer carries the outcome, so the UI needed a recent-jobs list: "is it in
  the document list?" cannot distinguish a still-running ingestion from a failed one.
- Cache invalidation moved from the upload to the job's success. Refreshing on the 202 would show a
  document list that does not contain the file just uploaded.
- Upload stays disabled for the whole job rather than the POST, since the POST now returns in about a
  second while the work runs for minutes.
- `UploadProgress` no longer tells the reviewer not to close the tab — true when the work lived in the
  request, false now. Pressing Upload again still duplicates, and it still says so.
- A restart loses in-flight work. It is reported as `interrupted` rather than retried automatically:
  re-running ingestion without a human asking could duplicate a document whose registry write had
  already landed.
- Jobs accumulate. There is no retention policy for the table yet — see below.

## Alternatives considered

**Raise `proxy_read_timeout` again.** Rejected, and already rejected in Sprint 18 by the comment in
the config file. It moves the ceiling without removing it, and every value is wrong for some real
document.

**Threshold on size: small documents synchronous, large ones queued.** Rejected — see Rationale. Two
behaviours separated by an invisible number, and the boundary is where the cost of guessing wrong is
highest.

**A real task queue (Celery, RQ, arq).** Rejected as disproportionate: all of them want a broker
process, which is new deployment surface for a product whose charter is a single trusted machine. A
`ThreadPoolExecutor` plus a persisted job row provides what is actually needed — durability of the
*record*, not of the queue.

**Retry interrupted jobs automatically on startup.** Rejected: ingestion is not idempotent from the
outside. A job interrupted after the registry write would produce a second copy of the document, and
the operator, not the sweeper, should decide.

**Persist queued uploads to disk instead of holding them in memory.** Rejected for now; the bounded
queue caps the exposure at `max_pending_ingestions × max_upload_bytes` (250MB worst case), and disk
spooling adds a cleanup problem — orphaned spool files after a crash — for a case the bound already
covers.

**Job retention/cleanup.** Deliberately not built. Jobs are small rows and nobody has yet run enough
ingestions for the table to matter; a retention rule invented now would be a guess. Revisit when a
real corpus makes the number concrete, consistent with this project's practice of fixing measured
problems rather than hypothetical ones (R-13, R-20).
