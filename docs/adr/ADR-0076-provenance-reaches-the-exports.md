# ADR-0076: The OCR warning reaches the document, not just the screen

**Status:** Accepted
**Sprint:** 26
**Deciders:** Fraz Ahmed
**Related:** ADR-0074 (per-passage OCR provenance, which disclosed this gap), ADR-0069 (the same
screen/document divergence, closed once already), ADR-0040 and ADR-0050 (the citation shape and its
supersession flag, whose bulk-lookup pattern this copies), ADR-0013 (PDF/XLSX split), R-33

## Context

ADR-0074 made OCR provenance per-passage and surfaced it in chat, where the product quotes evidence
verbatim. It then disclosed, in its own consequences, that the exports carried neither the badge nor
anything like it — *"a reviewer sees the OCR badge in chat and the PDF says nothing."*

That is the same failure ADR-0069 closed one sprint earlier for the domain chart and the MIL gate,
reopened in a narrower form. It is worth being blunt about the pattern: this project keeps building a
thing on screen, disclosing that the export lacks it, and closing the gap a sprint later. The
disclosure is honest and the sequence is still costing a round trip each time.

It matters most here. An export is the artifact that **leaves** — filed with an auditor, attached to
a board pack, read six months later by someone who cannot ask a question of the UI. A quotation whose
approximation warning exists only in a browser tab is a warning that is absent exactly when it is
load-bearing.

## Decision

`EvidenceCitation` gains `text_provenance`, and everything that renders a citation renders it: the
dashboard's gap list, the PDF, and the XLSX.

**Resolved per chunk, not per document.** The citation names an evidence link, and a link usually
names a chunk. Falling back to the document would flag every citation from a mostly-exact document,
which is the failure `ParseStatus.SUCCESS_PARTIAL_OCR`'s own docstring warns about and which ADR-0074
already refused once. A link with no `chunk_id` is a coarse, document-level manual link and genuinely
has no passage to be precise about; it falls back, and can only reach `possibly_ocr`.

**Looked up in bulk by the caller.** `build_dashboard` stays a pure function over its inputs — it
does not reach for a vector store or a document registry. The service passes `chunk_provenance` and
`parse_status_by_document` in, exactly as it already passes `superseded_document_ids` for ADR-0050:
one read per cited document, never one per citation. Both default to empty, which resolves every
citation to `unknown` — honest for a caller that supplied nothing, and never a claim that the text is
exact.

**`exact` renders nothing, in the export as on screen.** A tag on every ordinary citation is noise,
and noise is what stops anyone reading the one that matters. The same reasoning ADR-0074 used for the
badge, applied to a document that cannot be scrolled past.

## Consequences

- A PDF filed with an auditor now says which cited passages were recognised rather than read. An
  integration test proves it end to end: a real scanned PDF, through real OCR, into a real generated
  export read back with `pypdf`.
- Screen and document agree again. `CitedEvidenceList` and the exports render from the same resolved
  field rather than each deciding for itself, which is the property ADR-0069 established and
  ADR-0074's `gate_note` reinforced.
- One extra read per cited document when building a dashboard. Bounded by the number of *documents*
  cited, not citations, and it replaces nothing — this information was simply absent before.
- 9 new tests: 6 on the export renderers, 3 on the citation list, plus the end-to-end one above.

## What this does not do

**The evidence review queue still does not show provenance.** The Evidence tab lists `EvidenceLink`
rows, which are persisted SQLModel objects returned directly; adding a resolved field there means a
response wrapper and a per-link chunk lookup, which is a different shape of change from reading a
field the dashboard already computes. Disclosed rather than quietly skipped — it is the last surface
where a reviewer can meet OCR'd evidence without being told.

**R-33 stays narrowed, not closed.** OCR output remains approximate. What has changed across ADR-0074
and this is that the approximation now travels with the quotation into the artifact that leaves the
building.

## Alternatives considered

**Resolve at the document level for citations.** Rejected: it is simpler and it re-creates the
over-warning problem on any partially-OCR'd document, which is most real scanned corpora.

**Have `build_dashboard` look the chunks up itself.** Rejected: it would make a pure function reach
for two stores, and the existing `superseded_document_ids` parameter already establishes how this
project passes bulk-resolved facts into that builder.

**Add a dedicated provenance column to the XLSX Gaps sheet.** Rejected: the citation cell already
carries `[SUPERSEDED]` in the same shape, and a column that is empty for most rows is worse than a
tag that appears when it has something to say. Consistency with the existing annotation won.

**Wait and do it alongside the evidence-queue surface.** Rejected: that is the larger change, and
bundling would delay the artifact that actually leaves the building behind the one a reviewer can
always re-check live.
