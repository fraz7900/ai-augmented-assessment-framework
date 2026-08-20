# ADR-0078: The screen where the decision is made finally says where the text came from

**Status:** Accepted
**Sprint:** 27
**Deciders:** Fraz Ahmed
**Related:** ADR-0074 (per-passage provenance, in chat), ADR-0076 (the same in the dashboard and the
exports), ADR-0065 (the queue's filters, which this must not break), R-33

## Context

R-33 has now been narrowed twice. ADR-0074 resolved OCR provenance per passage and surfaced it in
chat; ADR-0076 carried it into the dashboard's citations and both exports. Each disclosed that the
**evidence review queue** still showed nothing.

That is the surface where it matters most and it was left for last, which is worth stating rather
than glossing. Chat is where a reviewer *reads* evidence; the dashboard and the exports are where
they *report* it. The queue is where they **decide** — accept, edit, reject — and a reviewer
accepting a proposal quoted from an OCR'd page had no way to know the wording was approximate at the
moment the decision was recorded.

## Decision

`GET /assessments/{id}/evidence` returns `EvidenceLinkView`: every field of the stored
`EvidenceLink`, plus a resolved `text_provenance`.

**A view, not a column.** Provenance is computed from the vector store at read time. Storing it on
the link would duplicate a fact the chunk already owns and let the two disagree — and the chunk is
the one that knows, because ADR-0074 put it there.

**Flat, not nested.** Callers read the response exactly as they read the link today. The cost is
drift: a new `EvidenceLink` field would be silently absent from the view. So a test asserts the view
covers every stored field and that the only addition is `text_provenance`. That guard is the price of
the ergonomics, paid explicitly.

**Resolved in bulk.** One vector-store read per cited *document*, not one per link — the same shape
ADR-0076 used for the dashboard. The queue is the screen most likely to hold hundreds of rows, which
makes it the worst possible place for a per-row lookup.

**Provenance survives filtering.** ADR-0065's filters narrow what a reviewer reads, and a field that
appeared only on the unfiltered call would be missing exactly when they had narrowed to the rows they
intend to act on. Tested directly.

## Consequences

- **R-33's last surface is covered.** A reviewer now meets the OCR warning at the point of decision,
  not only afterwards in a report.
- The response shape of the queue endpoint changed. That is a real change for any consumer, and the
  filters' 17 existing integration tests passing through it unmodified is the evidence that it did
  not change anything else.
- 4 new tests here, on top of those 17: the drift guard, provenance present on every link, provenance
  surviving a filter, and every stored field still readable off the response.

## What this does not do

**It does not make OCR text accurate**, and R-33 stays open on that basis — it was never a defect to
be fixed, only an uncertainty to be made visible.

**The badge does not change what a reviewer may do.** An approximate quotation is still accept-able;
this is information, not a gate. Gating on it would be inventing a policy nobody asked for, and the
reviewer is the judge (ADR-0011).

## Alternatives considered

**Store `text_provenance` on `EvidenceLink`.** Rejected: two records of one fact, and the row would
go stale the moment a document were re-ingested.

**Return `{links: [...], provenance: {id: value}}`.** Drift-free without a guard test, and rejected
for ergonomics: every consumer would have to join two structures to render one row, which is a worse
daily cost than a test that fails loudly on a rare event.

**A second endpoint returning provenance by link id.** Rejected: a second round trip on the busiest
screen, and two calls that can disagree if the queue changes between them.

**Leave it, since the dashboard shows it.** Rejected — the whole Context section. The dashboard is
where a decision is *reported*; the queue is where it is *made*.
