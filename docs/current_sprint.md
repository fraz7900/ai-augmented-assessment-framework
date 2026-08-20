Current sprint: Sprint 24 — stop guessing about the mapping engine and start measuring it
Objective: the two items Sprint 23 kept naming and not doing. Expose the agreement measurement that
has existed since Sprint 18 with no endpoint, so real review decisions become data (T1). Then re-run
the precision measurement the pilot readiness audit recommended in Sprint 17, at a corpus size that
can actually answer whether 0.012 was an artifact of five documents (T2). Deliberately no change to
the mapping engine itself: measuring before optimising is this project's own rule and the reason
that finding was never acted on.
Status: **T1 is on PR #21. T2 is not begun.**
Sprint 23 closed with five tranches merged, all from one tester's report: `9436460` filters,
`336a952` domain completion chart, `07a41a5` bulk reject, `d67968f` review-progress bar, `76e7479`
exports carrying both visuals and the MIL-gate sentence. Two of those existed only because the report
was re-read against what had shipped rather than against a summary of it. The project status snapshot
was brought to Sprint 23 in `e81795c`, three sprints after it last was, and `docs/project-status.html`
was stamped a frozen Sprint 21 snapshot rather than half-updated.
T1 — the agreement endpoint (ADR-0070, accepted). `compute_assessment_agreement` has existed since
Sprint 18. It computes, from real review decisions and with no labeled corpus needed, how often a
human accepted an AI proposal as-is. It had no endpoint, so its only caller was a script pointed at a
five-document fixture. ADR-0065 meanwhile declined a threshold bulk accept partly because nobody knew
whether humans accept more of what scored higher — a question this codebase could have been answering
for six sprints and was not. Sprint 23 is what makes it worth doing now: with filters and bulk reject,
a reviewer can work a real queue at volume, and those decisions are the data.
T1, and the rule it changes. `models/aqs.py` said these shapes were "never surfaced in the product
itself". That rule protected something real, so it is amended rather than dropped: an agreement rate
reads as a verdict on the assessment when it is a measurement of the engine, and "4% agreement" beside
a maturity score invites exactly the misreading ADR-0012 refused for business impact — on a corpus
where most proposals are wrong, a low rate is the reviewer working correctly. The intent is kept by
construction: namespaced under `/aqs/`, rendered nowhere in the product UI, read-only and never
persisted, with a sentence in every response saying what the number is not.
T1, the three properties that make a measurement worth acting on. The bands are R-16's measured
structure rather than round numbers — correct pairs at 0.65-0.78, incorrect at 0.43-0.53, threshold
0.55 — and the top band is open-ended above 0.78 because nothing correct has ever been observed
there, which is precisely the band a bulk-accept proposal would want to select from. They partition
half-open, so a link sitting on a boundary is counted once rather than twice. An unreviewed band
reports None rather than 0.0: "no data up here" and "humans reject everything up here" are opposite
findings, and 0.0 states the wrong one. Empty bands are returned rather than omitted, for the same
reason. Bulk reject decisions show up here like any other review, which matters because bulk is now
the fastest way a reviewer works.
T2 (not begun) — re-measure precision at a corpus size that can answer the question. The pilot
readiness audit measured precision 0.012 and recall 1.0 on five documents, named
`mapping_candidates_per_practice=1` plus the 0.55 threshold as the cause, and explicitly did not act:
one 5-document run cannot distinguish a miscalibrated default from a small-corpus artifact, and
changing engine behaviour on that sample would be the optimise-before-benchmarking mistake this
project's own discipline prohibits. That recommendation has been open since Sprint 17. The measurement
has to be honest about its own method: synthetic positives paraphrased from practice text would
flatter the engine, so the variable worth scaling is the negative corpus — realistic documents that
are genuinely not evidence — with the hand-labelled positives kept as they are.
Still open and not claimed here, unchanged. R-9, no reproducible environment bootstrap, rated High
likelihood and already occurred once. R-33, OCR-recovered text is approximate and nothing downstream
flags a citation drawn from an OCR'd page. R-34, ADR-0057's scoring correction can lower a number
already given to a stakeholder and the platform cannot tell anyone it changed. R-40, client
separation is enforced by the product and not against a caller that bypasses it. R-35's in-memory
upload queue. Backups remain on demand, with no schedule, rotation or off-machine copy. The
copyright-limited transcriptions R-28/R-30/R-32. `docs/project-status.md` still reads "As of: Sprint
21" and accounts for neither Sprint 22 nor this sprint.
Also open and unchanged. Upload retention is not retroactive, so the 6 of 30 documents whose
originals were discarded before ADR-0056 stay permanently un-re-ingestible; 27 of 30 stored
documents predate the registry (ADR-0039) and carry no `content_hash`; and assessments finalized
before ADR-0060 carry no seal, report `unsealed` rather than `verified`, and are deliberately not
sealed retroactively.
Explicitly out of scope this sprint and not begun: any change to `mapping_candidates_per_practice` or
`mapping_similarity_threshold` — this sprint measures them and deliberately does not tune them; bulk
accept of any shape; an agreement number anywhere in the product UI; changes to
`mapping_candidates_per_practice` or `mapping_similarity_threshold`; authentication, RBAC and
per-user permissions; cloud deployment; organisation deletion, merge, or reassignment; new
frameworks; continuous monitoring; score-change notification; and legacy registry backfill.
Charter: PROJECT_CHARTER.md
Constraint: local-first by default. Evidence content must not be sent
to a cloud API unless explicitly opted in (see PROJECT_CHARTER.md Section 7).
Data rule: only public framework documentation or synthetic sample
evidence belongs anywhere under data/ (see data/sample_evidence/README.md).
