# ADR-0077: An export can be asked whether it is still true

**Status:** Accepted
**Sprint:** 26
**Deciders:** Fraz Ahmed
**Related:** ADR-0013 (exports are generated fresh and never persisted — the decision that creates
this problem), ADR-0060 (the finalization seal, whose technique this borrows and whose question it
does *not* ask), ADR-0057 and R-34 (a reported score can legitimately change), R-21

## Context

R-21 has been open since Sprint 7: *"A downloaded PDF/XLSX report is a point-in-time snapshot;
nothing prevents a board or reviewer from acting on a stale export after evidence has since been
reviewed, added, or rejected."*

It is a direct consequence of ADR-0013's decision not to persist exports, which was right for other
reasons and means the platform has no record of which snapshots are in circulation. It therefore
cannot chase one. R-34 names the same shape from the other end: a score already reported to a
stakeholder can legitimately drop, and nothing can tell the person holding the earlier number.

The existing mitigations are real but partial. Every export prints a generation timestamp, and since
ADR-0060 a *finalized* one carries a seal identifying exactly which version of the record it came
from. A **draft** export — which is most of them, since the interesting reporting happens while an
assessment is still moving — has neither.

The platform cannot find the document. But the person holding it can ask about it, and that half is
solvable.

## Decision

**Every export prints a digest of the figures it was generated from, and an endpoint answers whether
that digest is still current.**

`GET /assessments/{id}/report-currency?digest=…` returns `current`, `superseded`, or `unverifiable`.

**This is not the seal, and the difference matters.** ADR-0060 asks *"has this finalized record been
altered?"* — tamper-evidence on something that must not change, where a mismatch is a finding. This
asks *"have the numbers moved since this page was printed?"* on a living draft that is **supposed** to
change, where a mismatch is normal. Same technique, opposite subject. Conflating them would either
make ordinary progress look like tampering or make tampering look like ordinary progress.

**`unverifiable` is not `superseded`.** A report this build cannot check — no digest, or one from a
payload version it does not know — is not evidence that anything changed. Reporting it stale would
raise a false alarm about a document that may be perfectly current, which is precisely the
`altered` / `unverifiable` distinction ADR-0060 already drew.

**The digest covers a chosen subset, not the whole `DashboardReport`.** That model has gained fields
in three of the last four sprints. Digesting all of it would make every previously issued export
report itself superseded the moment an unrelated field was added — which is worse than useless,
because it trains people to ignore the answer. So the payload is the figures a reader acts on: the
scores, the headline numbers, the review counts, and **which** practices are unmet rather than how
many. A gap closing while another opens is a real change to what the report says, and a count alone
would call that no change at all.

The payload is versioned, printed as `v1` beside the digest, for the reason ADR-0060 versions its
seal: so a future change to the shape is recognisable rather than silently reported as staleness.

## What the answer honestly cannot include

**It cannot say what the report used to say.** A digest is one-way; the reader's original figures are
not recoverable from it. The first draft of this change produced a "changes" list by diffing the
current payload against an empty one, which would have emitted *"ACCESS score changed from None to
1.0"* for every field — a fabricated diff wearing the costume of a real one.

So a `superseded` answer states **what the record says now** and tells the holder to compare against
the figures printed on their copy, with the limitation stated in the response body itself. That is
the real thing this can offer. Inventing the rest would be exactly the failure this project is
organised against.

## Consequences

- The half of R-21 that is solvable is solved: a person holding a report can find out whether to
  trust it, in one request, without the platform needing to have tracked the document.
- Draft exports gain something they never had. The seal only ever covered finalized ones.
- The instruction travels **on the page** — the export prints the endpoint to call, because the page
  is what leaves the building and the person reading it may never have seen the UI.
- Both formats print the same digest, from the one `DashboardReport` they are both rendered from
  (ADR-0013). A test pins that, because a reader told their spreadsheet is stale and their PDF is not
  would rightly stop believing either.
- 19 new tests: 12 on the digest and the comparison, 7 driving a real generated PDF and XLSX.

## What this does not do

**It does not notify anyone.** R-34's register entry says to revisit notification only if this
platform gains point-in-time or recurring reporting, and it has not. This is pull, not push: it
answers a question when asked, and does not pretend to reach a document that has already left.

**It does not version or store the export.** ADR-0013's decision stands. Two people holding two
different stale reports get told, individually, that each is stale — and neither can be reconstructed.

**It does not cover figures outside the payload.** A change to a `so_what` sentence or an assessment's
name leaves an existing report `current`, deliberately. Those do not change what a reader decides.

## Alternatives considered

**Reuse the finalization seal.** Rejected on the question-mismatch above, and because the seal exists
only for finalized assessments while the staleness problem is worst for drafts.

**Digest the entire `DashboardReport`.** Rejected: every unrelated field addition would invalidate
every export in existence, and an alarm that is usually wrong is worse than none.

**Persist each generated export server-side so the diff is exact.** Rejected: it reverses ADR-0013
for a benefit — a precise change list — that only matters after someone has already discovered the
report is stale, which this delivers without storing anything.

**Embed the full figures in the export instead of a digest, so a true diff is possible.** Tempting,
and rejected for now: it puts a machine-readable payload on a human-facing document, and the digest
plus "compare against your printed copy" gets a reader to the same decision. Worth revisiting if
anyone ever wants this automated across many reports at once.
