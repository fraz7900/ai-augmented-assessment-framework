# ADR-0074: OCR provenance follows the citation, per page, or says it cannot

**Status:** Accepted
**Sprint:** 25
**Deciders:** Fraz Ahmed
**Related:** ADR-0055 (local OCR, and the selective-OCR path that already knew this), ADR-0042
(per-chunk page provenance), ADR-0039 (the document registry), ADR-0064 (job retention, which is why
the job row is not a durable home for this), ADR-0007 (SQLite, no migration tool), R-33

## Context

R-33 has been open since Sprint 19: *"OCR-recovered text is approximate, and the product's
credibility rests on verbatim quotation: a citation drawn from an OCR'd page may not match the source
page character-for-character, and nothing downstream of ingestion can tell the difference."*

It was disclosed rather than hidden — `ParseStatus.SUCCESS_OCR` is a warning tone in the upload UI —
but disclosure at upload is not the same as disclosure at the point of use. By the time a reviewer
read a quotation back in chat, or quoted one into a report, the fact was gone. That matters here more
than it would elsewhere: Sprint 19 rewrote the chunker specifically to protect verbatim quotation,
taking mid-word chunks from 140 to 2, because a misquoted citation in an audit deliverable is the
failure this product cannot afford.

The information already existed. `parse_pdf`'s selective-OCR path (ADR-0055) computes exactly which
textless pages the recogniser replaced — `recovered_pages` — uses it to choose a `ParseStatus`, and
then throws the list away. That discard is what made R-33 unfixable downstream rather than merely
unfixed.

## Why a document-level flag was not enough

`ParseStatus.SUCCESS_PARTIAL_OCR` exists because "all of this is approximate" and "pages 3, 5 and 7
are approximate, the rest is exact" are different instructions to a reviewer. Its own docstring says
collapsing them either *"make[s] a mostly-exact document look wholly untrustworthy"* or *"hide[s]
that any of it is approximate"*.

A document-level warning on citations reproduces exactly that dilemma one layer down. On a 200-page
policy where OCR recovered three scanned appendix pages, every quotation from the other 197 would
carry a warning it does not deserve — and a reviewer who learns the badge is usually wrong stops
reading it, which costs more than never having shown it.

## Decision

**Provenance is resolved per passage, and reported as a closed four-value set.**

`ParsedDocument.ocr_page_numbers` carries the pages OCR recovered, 1-indexed to match
`EvidenceChunk.page_number`. `chunk_document` uses it to set `EvidenceChunk.is_ocr_derived` per
chunk, and the vector store persists that as a nullable column — nullable because *unknown* has to
survive the round trip rather than collapsing into false.

`TextProvenance` is what a caller reads:

| value | meaning |
|---|---|
| `exact` | read from a real text layer; a quotation should match character for character |
| `ocr` | this passage's own page was recognised; the wording is approximate |
| `possibly_ocr` | OCR ran in this document, but which page this passage came from was not recorded |
| `unknown` | no recorded parse status; no basis for an answer |

**`unknown` is not `exact`, and that is the point of having four values.** `exact` is a claim about
an intact text layer. Absence of a record is not evidence for it, and 27 of 30 stored documents
predate even the registry — asserting they are exact would be the kind of unearned confidence this
project's whole argument is against.

**The chunk's own answer wins; the document's status is the fallback.** A chunk written before this
existed has no flag, so the document's `parse_status` is the only evidence left and can only support
`possibly_ocr`. A document that never involved OCR resolves to `exact` even for an unflagged chunk,
because `SUCCESS` means every character came from a text layer and there is nothing per-page to be
uncertain about.

**Surfaced first where the product quotes evidence verbatim.** Chat results carry
`text_provenance`, and the badge sits next to the quotation it qualifies. `exact` renders nothing at
all: a badge on every ordinary quotation is noise, and noise is what stops people reading the badge
that matters.

## Two defects found while doing this

**`Document` had no parse status at all.** The field exists on `IngestionJob` — the transient row,
swept after 30 days by ADR-0064 — and never on the durable document record. So the fallback this
design needs had nothing to fall back to, and more generally a document's provenance was being
deleted on a retention schedule while the document itself lived on. `Document.parse_status` is added,
written at ingestion, and migrated onto existing databases as a nullable column with no default.

**SQLModel accepted a keyword for a field that did not exist and silently dropped it.** `table=True`
models skip validation, so the first attempt to persist `parse_status` on `Document` looked like it
worked and stored nothing. Caught by an integration test asserting the resolved value, not by
inspection — the third time in three sprints a test written for one purpose has found a different
real defect.

## Consequences

- A reviewer reading a quotation is told whether its wording can be trusted, per passage.
- **R-33 is narrowed, not closed.** OCR output is still approximate; what changes is that the
  approximation is now visible where it is acted on. The register entry says so rather than claiming
  a fix.
- `ParseResult` widened from a 5-tuple to a 6-tuple, touching all 22 parser return sites. Mechanical,
  and the smaller change than restructuring every parser's return shape for one field — recorded here
  because a reader meeting a 6-positional tuple deserves to know it was a considered trade.
- Two schema migrations, both nullable-with-no-default, both following the idioms already in place:
  `_add_missing_columns` for SQLite (ADR-0007's no-migration-tool reality) and `add_columns` for
  LanceDB (the same path `page_number` took in ADR-0042).
- 19 new tests: 9 on the resolution rule, 3 driving a real scanned PDF through the real OCR path to
  chat, and 7 on the badge. The OCR test builds its own image-only PDF at test time rather than
  skipping when the gitignored sample is absent -- it was skipping in CI on the first run, which
  meant the one test covering the actual OCR path protected nothing there. Generating it is also
  what `backend/conftest.py` already says to do with binary fixtures.

## What this does not do

**The exports do not carry it yet.** ADR-0069 closed the screen/document gap for the domain chart and
the MIL gate, and this reopens a narrower version of it: a reviewer sees the OCR badge in chat and
the PDF says nothing. Disclosed here rather than discovered, and it is the obvious next tranche.

**Evidence links in the review queue do not carry it.** The Evidence tab shows a chunk id and, for
AI proposals, a quoted snippet in the note. Resolving provenance there needs a chunk lookup per link,
which is a different shape of change from reading a field the chat search already returns.

**It does not make OCR text accurate.** Nothing here improves recognition. It makes the
uncertainty legible, which is the honest available move.

## Alternatives considered

**Flag at the document level only.** Rejected — the whole "why a document-level flag was not enough"
section above.

**Recompute provenance at read time from the document's status.** Rejected: it cannot distinguish
pages, which is the entire problem, and it would make every citation's answer depend on a second
lookup rather than on what the store recorded when it knew the truth.

**Backfill `is_ocr_derived = false` for existing chunks.** Rejected as the most tempting wrong
answer. It would make every legacy chunk claim an intact text layer, which is precisely the assertion
nobody can support, and it would silently convert a disclosed unknown into a false assurance.

**A boolean instead of a four-value set.** Rejected: it forces "cannot say" to be reported as one of
the two claims, and which one you pick decides whether the product invents warnings or hides them.
