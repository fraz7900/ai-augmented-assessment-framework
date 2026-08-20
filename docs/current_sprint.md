Current sprint: Sprint 25 — close two gaps this project has disclosed for years and not fixed
Objective: the register's own two longest-standing open items that are actually fixable here. R-33,
open since Sprint 19: OCR text is approximate, the product's credibility rests on verbatim quotation,
and nothing downstream of ingestion could tell a reviewer which passages were which (T1). R-9, the
only High-likelihood open risk and one that has already occurred once: no reproducible environment
bootstrap (T2). Neither needs data this repository cannot hold, which is what disqualified the
precision work from continuing.
Status: **T1 is on PR #25. T2 is not begun.**
Sprint 24 closed with four tranches merged: `edfc0b6` the agreement endpoint, `cb1eef7` precision
measured at scale (0.012 is structural, not a small-corpus artifact), `36bd9ce` competitive candidate
selection, `300b3b2` the same validated on real documents. One of those reached main without a PR and
was reverted and reapplied through one (`a8bac3b`, then PR #24) rather than force-pushed over.
T1 — OCR provenance follows the citation (ADR-0074, accepted). R-33 was disclosed rather than hidden,
but disclosure at UPLOAD is not disclosure at the point of use: `ParseStatus.SUCCESS_OCR` is a
warning tone in the upload UI, and by the time a reviewer read a quotation back in chat the fact was
gone. That matters more here than it would elsewhere, because Sprint 19 rewrote the chunker
specifically to protect verbatim quotation, taking mid-word chunks from 140 to 2.
T1, and why a document-level flag would not do. `ParseStatus.SUCCESS_PARTIAL_OCR` exists because "all
of this is approximate" and "pages 3, 5 and 7 are approximate, the rest is exact" are different
instructions to a reviewer — its own docstring says collapsing them either makes a mostly-exact
document look wholly untrustworthy or hides that any of it is approximate. A document-level warning
on citations reproduces that dilemma one layer down: on a 200-page policy where OCR recovered three
appendix pages, every quotation from the other 197 carries a warning it does not deserve, and a
reviewer who learns the badge is usually wrong stops reading it.
T1, what it does. The information already existed and was thrown away: `parse_pdf`'s selective-OCR
path computes exactly which textless pages the recogniser replaced, uses it to pick a ParseStatus,
and discards the list. It is now carried to the chunk, persisted on the vector store as a nullable
column, and resolved per passage into a closed four-value set — `exact`, `ocr`, `possibly_ocr`,
`unknown`. Four rather than two because "cannot say" is a real answer: `unknown` is not `exact`,
since `exact` is a claim about an intact text layer and absence of a record is not evidence for it.
27 of 30 stored documents predate even the registry. Surfaced first in chat, where the product quotes
evidence verbatim, with `exact` rendering nothing at all — a badge on every ordinary quotation is
noise, and noise is what stops people reading the badge that matters.
What T1 actually took, and two defects it found. `Document` had no parse status at all: the field
lives on `IngestionJob`, the transient row that ADR-0064 sweeps after 30 days, and never on the
durable record — so a document's provenance was being deleted on a retention schedule while the
document lived on, and the fallback this design needs had nothing to fall back to. Added, written at
ingestion, migrated as nullable-with-no-default. Then: SQLModel accepted a keyword for a field that
did not exist and silently dropped it, because `table=True` models skip validation, so the first
attempt to persist it looked like it worked and stored nothing. Caught by an integration test
asserting the resolved value rather than by inspection — the third time in three sprints a test
written for one purpose has found a different real defect. `ParseResult` also widened from a 5-tuple
to a 6-tuple across all 22 parser return sites, which was the smaller change than restructuring every
parser's return shape for one field.
T1, what it is not. **R-33 is narrowed, not closed** — OCR output is still approximate; what changed
is that the approximation is visible where it is acted on. The exports do not carry the badge yet,
which reopens a narrower version of the screen/document gap ADR-0069 closed, and is the obvious next
tranche. Evidence links in the review queue do not carry it either: that needs a chunk lookup per
link rather than reading a field the chat search already returns.
T2 (not begun) — R-9, no reproducible environment bootstrap. Rated High likelihood and already
occurred once. AGENTS.md carries the symptoms rather than the cause: `npm install` needs
`--legacy-peer-deps` for a real peer conflict, `node_modules` goes subtly incomplete on this
filesystem in a way that looks like test failures rather than an install problem, and the documented
remedy is a 3.5-minute delete-and-reinstall. The fix is a bootstrap that either produces a known-good
environment or fails loudly saying why, plus a check that can tell "your environment is wrong" from
"your code is wrong" — which is the distinction that cost this project a sprint's worth of confusion
already.
Also open and unchanged. Upload retention is not retroactive, so the 6 of 30 documents whose
originals were discarded before ADR-0056 stay permanently un-re-ingestible; 27 of 30 stored
documents predate the registry (ADR-0039) and carry no `content_hash`; and assessments finalized
before ADR-0060 carry no seal, report `unsealed` rather than `verified`, and are deliberately not
sealed retroactively.
Explicitly out of scope this sprint and not begun: any change to `mapping_candidates_per_practice` or
`mapping_similarity_threshold` — T3 changed how candidates compete, and deliberately left both of
those alone, on ADR-0071's evidence that no threshold separates a confirmed false positive at 0.71
from correct pairs measured at 0.65-0.78; bulk
accept of any shape; an agreement number anywhere in the product UI; changes to
`mapping_candidates_per_practice` or `mapping_similarity_threshold`; authentication, RBAC and
per-user permissions; cloud deployment; organisation deletion, merge, or reassignment; new
frameworks; continuous monitoring; score-change notification; and legacy registry backfill.
Charter: PROJECT_CHARTER.md
Constraint: local-first by default. Evidence content must not be sent
to a cloud API unless explicitly opted in (see PROJECT_CHARTER.md Section 7).
Data rule: only public framework documentation or synthetic sample
evidence belongs anywhere under data/ (see data/sample_evidence/README.md).
