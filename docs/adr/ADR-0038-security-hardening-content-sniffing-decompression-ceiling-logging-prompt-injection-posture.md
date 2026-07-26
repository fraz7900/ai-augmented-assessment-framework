# ADR-0038: Security hardening — content-sniffing, decompression-bomb ceiling, structured logging, standing prompt-injection posture

**Status:** Accepted
**Sprint:** 18 (controlled-pilot readiness pass, follow-up to ADR-0033/0034/0035/0036/0037)
**Deciders:** Fraz Ahmed (project-owner directive: "Start with security hardening," Section A #12 of
`docs/architecture/02-controlled-pilot-readiness-audit.md`)
**Related:** ADR-0020 (retrieval-only, permanent), ADR-0036 (reasoner go/no-go reconfirmed),
`docs/architecture/02-controlled-pilot-readiness-audit.md` §A.12, §B.3

## Context

The controlled-pilot readiness audit (§A.12) classified "Security and failure handling" as PARTIAL,
naming four specific, disclosed gaps rather than a vague "needs hardening" note:

1. File-type validation was extension-only — a renamed file went straight to that extension's parser
   regardless of its real content.
2. No timeout or decompression-bomb ceiling — a pathological nested-object PDF or DOCX-zip had no
   cap beyond the raw 25MB pre-decompression upload limit.
3. **Zero logging anywhere in the backend** (`grep logger` returned nothing) — no audit/observability
   trail at all, for any action.
4. No documented prompt-injection posture — architecturally moot today (no generative LLM call
   exists to inject into), but undocumented, which becomes a real gap the moment a reasoner is ever
   built.

## Decision

### 1. Content-sniffing (`services/document_parsers.py`)

`parse_document` now checks the uploaded content's real bytes against its claimed extension-derived
`FileType` *before* dispatching to any format-specific parser: PDF must start with `%PDF-`; DOCX (an
OOXML/ZIP archive) must start with a real ZIP signature (`PK\x03\x04` or `PK\x05\x06`); TXT/MD must
not contain a NUL byte in their first 8KB (a standard binary-content heuristic that does not fire on
genuinely invalid-UTF-8 text, which `parse_plain_text`'s existing latin-1 fallback already handles).
A mismatch returns the existing `ParseStatus.FAILED` — reusing the enum, not adding a new value, so
every pre-existing test asserting `FAILED` on garbage content (`test_parse_pdf_handles_malformed_content`,
`test_parse_docx_handles_malformed_content`) continues to pass unmodified; the failure is now just
detected earlier, before wasting cycles inside a parser given content it was never going to succeed on.

### 2. Decompression-bomb ceiling

Two complementary checks, since no single check covers every format cheaply:

- **DOCX-specific, pre-extraction** (`parse_docx`): a ZIP archive's central directory carries each
  entry's real uncompressed size (`ZipInfo.file_size`) — readable without decompressing a single byte.
  Rejects if the sum exceeds 200MB, before `python-docx` ever opens the archive.
- **Format-agnostic, post-extraction** (`ingestion_service.ingest`, new
  `Settings.max_extracted_text_chars`, default 20,000,000): applies to every format uniformly,
  including PDF, whose internal Flate-compressed streams have no equivalent cheap pre-check the way
  a ZIP's central directory does.

No wall-clock parsing timeout was added — implementing one safely for CPU-bound calls into `pypdf`/
`python-docx` (C-extension-backed, not cleanly interruptible via threading, would need
subprocess-level isolation) is a materially harder problem than either check above, and a half-safe
attempt risks introducing its own bugs without a real correctness guarantee. Disclosed as a real,
remaining gap, not silently treated as covered by the two checks above.

### 3. Structured logging (`core/logging_config.py`, new `Settings.log_level`)

Stdout-only, one shared format, level configurable via environment variable — no file/rotation policy
to maintain (a local-first, single-process app; a container/process supervisor already captures
stdout). Wired in at `main.py` import time via `configure_logging(get_settings())`. Log calls added at
the actual audit-relevant boundaries, not sprinkled everywhere:

- `api/error_handlers.py`: every handled domain exception now logs at WARNING (method, status,
  path, exception message) before being converted to its JSON response — previously vanished with
  zero server-side record.
- `services/ingestion_service.py`: document ingested (INFO: id, filename, file_type, chunk_count) or
  rejected (WARNING: filename, status/reason).
- `services/assessment_service.py`: assessment created, status transition, evidence linked, evidence
  reviewed, practice finding set, sanitization approved, propose-mappings run — all at INFO, logging
  IDs/counts/statuses only.

**Never logs evidence content, finding rationale, or sanitization `custom_terms`** — the same fields
this project's own sanitization design (`models/sanitization.py`) already treats as the sensitive
surface. `approve_sanitization`'s log line records `custom_term_count`, not the terms themselves —
logging the actual terms would defeat the feature's entire purpose. This is enforced by convention/
code review at each call site, not by a type system.

An `Exception`-type catch-all handler for genuinely unhandled errors was considered and **not**
added — see Alternatives.

### 4. Documented prompt-injection posture

No code change (there is no generative LLM call to secure) — this decision **formalizes**, as a
standing, citable requirement, guidance that already existed only informally, scattered across
ADR-0036's design notes and this project's general "verified over fabricated" posture:

> **Any future generative capability in this codebase (a local reasoner, or anything else that feeds
> retrieved evidence-chunk text to a model) MUST structurally separate two categories of input:**
> framework/practice text (trusted, this project's own verified transcription) and evidence-chunk
> text (untrusted, human-uploaded, quoted verbatim into any prompt — never interpreted, summarized in
> a way that could execute embedded instructions, or treated as anything other than data). A model's
> output MUST be validated post-hoc against its own input (citations checked against the real
> `EvidencePack` it was given) before being persisted, and MUST land as a `PENDING`,
> `set_by="model"` result requiring human review — never auto-applied. This requirement is not
> optional or a nice-to-have for a future sprint to revisit; it is a precondition of building any such
> capability at all, exactly as strict as the citation/human-review requirements ADR-0011/0014 already
> enforce for the retrieval-only capabilities that exist today.

## Rationale

1. **Every fix here matches an audit finding named with a specific citation, not a generic "harden
   security" pass** — the same discipline every sprint this pass has followed (ADR-0033 through
   ADR-0037): find the real, disclosed gap, fix exactly that, disclose what's still not covered.
2. **Reusing `ParseStatus.FAILED` rather than adding new enum values for content-sniffing/ceiling
   rejections keeps every existing test passing unmodified** — a real, verified property (see
   Consequences), not an assumption; the failure mode is genuinely "this could not be usefully
   ingested," which `FAILED` already accurately describes.
3. **Declining to implement a parsing timeout, rather than shipping a partial one, follows this
   project's "no half-finished implementations" discipline directly** — a timeout mechanism that
   doesn't actually reliably interrupt a blocking C-extension call would be worse than no timeout at
   all: it would create a false sense of protection.
4. **Logging only at genuine audit-relevant boundaries, with an explicit "never log sensitive content"
   rule enforced at every call site, matches this project's local-first privacy stance** — the fix for
   "no audit trail" must not become a new leak vector for the same evidence content the whole platform
   already goes out of its way to protect (sanitization, retrieval-only chat, local embedding).
5. **Formalizing the prompt-injection posture now, while no generative capability exists, is
   deliberately preemptive** — writing the requirement down before it's urgently needed means it
   constrains the *design* of any future reasoner from day one, rather than being bolted on after
   the fact once a real injection vulnerability is found in a shipped feature.

## Consequences

- `backend/src/compliance_platform/services/document_parsers.py`: content-sniffing check added to
  `parse_document`; decompression-bomb pre-check added to `parse_docx`. `parse_pdf`/`parse_plain_text`
  unchanged internally (the sniffing check runs before any parser is called).
- `backend/src/compliance_platform/services/ingestion_service.py`: post-extraction ceiling check;
  ingestion success/rejection logging.
- `backend/src/compliance_platform/core/config.py`: new `Settings.log_level` (default `"INFO"`),
  `Settings.max_extracted_text_chars` (default 20,000,000).
- `backend/src/compliance_platform/core/logging_config.py`: new file, `configure_logging`.
- `backend/src/compliance_platform/main.py`: calls `configure_logging(get_settings())` at import time.
- `backend/src/compliance_platform/api/error_handlers.py`: WARNING-level logging for every handled
  domain exception.
- `backend/src/compliance_platform/services/assessment_service.py`: INFO-level logging at 7 call
  sites (create, transition, link, review, finding, sanitization approval, propose-mappings).
- New tests: 6 in `test_document_parsers.py`, 1 in `test_ingestion_service.py`, 2 in
  `core/tests/test_logging_config.py` (new file), 1 in `test_assessment_service.py`, 1 in
  `test_assessment_api_integration.py`.
- Full backend suite: verified passing after this change (see commit).
- `docs/architecture/02-controlled-pilot-readiness-audit.md` §A.12: updated to record what was fixed
  and what remains disclosed as not covered (parsing timeout).
- **No change to any API contract, response shape, or existing endpoint behavior** — every fix here
  is either a new rejection path that reuses an existing status/response shape, or a side-effect-only
  logging addition.

## Alternatives considered

- **Add a magic-byte-sniffing library (e.g. `python-magic`) instead of hand-rolled signature checks.**
  Rejected — the actual signature set needed (PDF, ZIP, "not obviously binary") is small and stable;
  hand-rolling it avoids a new dependency (this project's own precedent, ADR-0006/0008, is to evaluate
  new dependencies deliberately, not add them casually) for a check simple enough not to need one.
- **Implement a wall-clock parsing timeout via `signal.alarm` (POSIX-only) or a worker thread.**
  Rejected — see Rationale #3. `signal.alarm` only works on the main thread of the main process (breaks
  under a threaded WSGI/ASGI worker model), and a thread-based "timeout" cannot actually kill a
  blocking synchronous C-extension call, only stop waiting for it while it keeps running in the
  background — a correctness risk (resource exhaustion continues silently) worse than the status quo.
- **Add a catch-all `Exception` handler in `error_handlers.py` for genuinely unhandled errors, logging
  them at ERROR with a traceback.** Rejected for this sprint — Starlette's own default behavior for an
  unhandled exception (no registered handler) already returns a safe generic 500 and re-raises, which
  uvicorn's own process-level logging already surfaces to the console; duplicating that behavior
  risks subtly changing the existing safe-default response shape for a case that isn't the audit's
  named gap (the named gap was *expected* domain exceptions vanishing with no record, which is fixed).
  Left as an explicit, disclosed follow-up if server-side structured (not just console) logging of
  truly unexpected errors is wanted later.
- **Log full request/response bodies for every API call (a more complete audit trail).** Rejected —
  request bodies for assessment/evidence endpoints can contain the exact free-text fields
  (`rationale`, `custom_terms`, chat `question`) this ADR's own logging rule exists to keep out of
  logs; a blanket body-logging middleware would silently reintroduce the leak this fix was written to
  prevent.
