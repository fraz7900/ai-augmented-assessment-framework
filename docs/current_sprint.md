Current sprint: Sprint 26 — what the platform owes someone already holding something it produced
Objective: two disclosed gaps that share a shape. A reviewer holding a PDF this platform generated
cannot tell that a quoted passage was recognised rather than read (T1, finishing R-33), and cannot
tell whether the numbers in it have since changed (T2, R-21). Both are about an artifact that has
left the building and the person relying on it. No new frameworks, no auth, no notification
infrastructure — R-34's own register entry says to revisit that only if this platform gains
point-in-time or recurring reporting, and it has not.
Status: **T1 merged as `3d93d62` (PR #27). T2 is on PR #28.**
Sprint 25 closed with both tranches merged: `67570ec` OCR provenance per passage (ADR-0074) and
`b38c5df` a reproducible bootstrap and a machine that can be questioned (ADR-0075).
T1 — the OCR warning reaches the document (ADR-0076, accepted). ADR-0074 made provenance per-passage
and surfaced it in chat, then disclosed in its own consequences that the exports carried nothing.
That is the same screen/document divergence ADR-0069 closed one sprint earlier for the domain chart,
reopened in a narrower form, and the pattern is worth naming rather than repeating quietly: this
project keeps building a thing on screen, disclosing that the export lacks it, and closing the gap a
sprint later.
T1, why the export is where it matters most. An export is the artifact that LEAVES — filed with an
auditor, attached to a board pack, read six months later by someone who cannot ask the UI a question.
A quotation whose approximation warning exists only in a browser tab is missing exactly when it is
load-bearing.
T1, what it does. `EvidenceCitation` gains `text_provenance`, and the dashboard's gap list, the PDF
and the XLSX all render it. Resolved per CHUNK rather than per document, because falling back to the
document flags every citation from a mostly-exact one — the failure SUCCESS_PARTIAL_OCR's docstring
names and ADR-0074 already refused once. Looked up in bulk by the caller so `build_dashboard` stays
pure over its inputs, exactly as `superseded_document_ids` already works (ADR-0050): one read per
cited document, never one per citation. `exact` renders nothing, in the export as on screen.
What T1 actually took. Two test assumptions were wrong before they were right. A manual evidence link
is created ACCEPTED, so the first end-to-end attempt tried to reject one to make its practice a gap
and silently got a 409 — the same one-shot review rule bulk reject ran into in Sprint 23 — leaving
the practice met and the citation absent. Planting a pending AI proposal is both the state that
produces a citation and the realistic one. And the report route is `/report/pdf`, not `/report.pdf`.
Neither was caught by reading; both by a test asserting on the resolved output.
T1, what it is not. The **evidence review queue still shows no provenance**: it lists EvidenceLink
rows, which are persisted SQLModel objects returned directly, so a resolved field there needs a
response wrapper and a per-link chunk lookup. Disclosed rather than quietly skipped — it is the last
surface where a reviewer can meet OCR'd evidence without being told. R-33 stays narrowed, not closed.
The frontend runner, measured again this sprint. Three consecutive full runs on unchanged code gave
89, 75 and 112 passing with 8, 10 and 7 files lost to the forks-worker timeout and **zero assertion
failures** in any of them. `./scripts/doctor.sh` (ADR-0075) reported the environment sound each time,
including `npm ls` confirming a complete tree — so this is the flaky case that ADR-0075 explicitly
said the doctor detects nothing about, not the incomplete-install case it does. A reinstall via
`./scripts/bootstrap.sh` moved it from 75 to 112 and did not fix it, which is what AGENTS.md already
records. CI is the authority and settled it.
T2 — an export can be asked whether it is still true (ADR-0077, accepted). R-21 since Sprint 7: a
downloaded PDF is a point-in-time snapshot and nothing stops a board acting on a stale one. It is a
direct consequence of ADR-0013 not persisting exports, so the platform has no record of what is in
circulation and cannot chase a document. But the person holding one can ask, and that half is
solvable. Every export now prints a digest of the figures it was generated from, and
`GET /assessments/{id}/report-currency?digest=…` answers current / superseded / unverifiable.
T2, and why this is not the seal. ADR-0060 asks "has this finalized record been altered?" — evidence
of tampering on something that must not change, where a mismatch is a finding. This asks "have the
numbers moved since this page was printed?" on a living draft that is SUPPOSED to change, where a
mismatch is normal. Same technique, opposite subject; conflating them would make ordinary progress
look like tampering or the reverse. `unverifiable` is likewise not `superseded`: a report this build
cannot check is not evidence anything changed, which is ADR-0060's own distinction reapplied.
T2, the payload is a chosen subset. DashboardReport has gained fields in three of the last four
sprints, so digesting all of it would make every previously issued export report itself superseded
the moment an unrelated field was added — worse than useless, because it teaches people to ignore the
answer. The payload is what a reader acts on: scores, headline figures, review counts, and WHICH
practices are unmet rather than how many, since a gap closing while another opens is a real change
that a count would call no change. Versioned as v1 beside the digest, for the reason ADR-0060
versions its seal.
What T2 could not honestly do, and nearly did. The first draft produced a "what changed" list by
diffing the current payload against an empty one — which would have emitted "ACCESS score changed
from None to 1.0" for every field, a fabricated diff wearing the costume of a real one. A digest is
one-way and the reader's original figures are simply not recoverable from it. So a superseded answer
states what the record says NOW and tells the holder to compare against their printed copy, with that
limitation stated in the response body rather than only in this file.
T2, details that earned their tests. Both formats print the same digest from the one DashboardReport
they are rendered from, because a reader told their spreadsheet is stale and their PDF is not would
rightly stop believing either. The endpoint to call is printed on the page itself, since the page is
what leaves the building and its reader may never have seen the UI. And it notifies nobody: R-34's
register entry says to revisit push notification only if this platform gains point-in-time or
recurring reporting, and it has not.
Still open and not claimed here, unchanged. R-9 is narrowed but the interpreters still come from the
machine and nothing is hash-pinned. R-34, a score already reported to a stakeholder can change with
no way to tell them. R-40, client separation is enforced by the product and not against a caller that
bypasses it. R-35's in-memory upload queue. Backups remain on demand, with no schedule, rotation or
off-machine copy. The copyright-limited transcriptions R-28/R-30/R-32. R-16's precision ceiling, now
measured and partly reduced but not closed, and the labelled real corpus that would be needed to take
it further — which by policy cannot live in this repository at all.
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
