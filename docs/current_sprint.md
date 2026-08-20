Current sprint: Sprint 24 — stop guessing about the mapping engine and start measuring it
Objective: the two items Sprint 23 kept naming and not doing. Expose the agreement measurement that
has existed since Sprint 18 with no endpoint, so real review decisions become data (T1). Then re-run
the precision measurement the pilot readiness audit recommended in Sprint 17, at a corpus size that
can actually answer whether 0.012 was an artifact of five documents (T2). Deliberately no change to
the mapping engine itself: measuring before optimising is this project's own rule and the reason
that finding was never acted on.
Status: **T1 `edfc0b6` (PR #21), T2 `cb1eef7` (PR #22), T3 `36bd9ce` (PR #23) are merged. T4 is on PR #24.**
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
T2 — the precision question is answered (ADR-0071, accepted). Open since Sprint 17: was 0.012 a
miscalibrated default or an artifact of five documents? It is neither miscalibrated nor an artifact —
it is structural. `scripts/measure_aqs.py` gained a `--distractors` sweep that scales only the
negative half of the corpus, because synthetic positives paraphrased from practice text would be
embedding the framework's own words back at itself and calling the match a success. The distractors
are policy-shaped and use domain-general security vocabulary, which is the hard case: R-16 names
exactly that vocabulary as the mechanism behind false positives near the threshold.
T2, what it measured. Across 5, 30, 80, 205 and 505 documents on this machine against the real stack,
precision moved 0.0117 to 0.0113 — in the wrong direction — while recall stayed 1.0 throughout. A
101x increase in documents changed precision by 0.0004.
T2, the finding that matters more than the number. **The proposal count saturates at 355 and then
stops moving entirely**, identical at 205 and 505 documents. C2M2 has 356 practices and one was
already covered by the fixture, so 355 is every uncovered practice: the engine proposes one candidate
for each, and at any realistic corpus size essentially every practice finds some chunk clearing 0.55.
The false-positive count is therefore a property of the FRAMEWORK, not of the evidence. Precision is
bounded by roughly (practices with genuine evidence) / (all uncovered practices) no matter how good
retrieval gets — on a real corpus the numerator would be far higher than this fixture's 4, but the
denominator does not depend on the corpus at all.
T2, what is deliberately not done. No engine parameter changed. Measuring was this sprint's scope and
tuning is not, which is the same discipline the audit invoked when it declined to act on the original
run. Raising the threshold is ruled out on evidence rather than preference: R-16 puts a confirmed
false positive at 0.71, inside the 0.65-0.78 band correct pairs were measured in, so no single cutoff
separates them. The direction that survives is competitive rather than absolute selection — proposing
only where the best match stands out from its own alternatives, and letting some practices receive no
proposal at all. That changes recall and deserves its own ADR, measurement and sprint.
T2, stated limits. The distractors contribute no true positives by construction, so a real
500-document corpus would show higher absolute precision; the false-positive behaviour is what this
establishes and that part is corpus-independent. 505 documents is the low end of the audit's stated
100-1,000 range — the curve is flat and saturated well before it, but it was not run there. Six tests
cover the corpus construction only: the script is a script, but the ground-truth set is the answer key
a precision number is computed against, and a defect there would produce a plausible wrong measurement
rather than a loud failure.
T3 — competitive candidate selection (ADR-0072, accepted). The change T2 said was needed and
deliberately did not make. Before designing it, the shape of the proposals was measured: at 80
documents, 354 proposals landed on only **53 distinct chunks**, one chunk was proposed against **44
different practices**, and the top eight chunks absorbed 158 between them. That concentration is
ADR-0071's mechanism made visible — a chunk that is the best match for 44 practices is not evidence
for 44 things, it is a paragraph general enough to look plausible against most of a framework.
T3, what it does. After per-practice selection produces candidates, group by chunk, sort by
confidence, keep the strongest N. `mapping_max_practices_per_chunk` defaults to 3; 0 restores the old
engine exactly. Ties break on practice id so two runs produce the same queue. At 80 documents
precision goes 0.0113 to 0.0305 with recall 1.000; at 505 documents 0.0113 to 0.0195. The benefit
shrinks as the corpus grows and that is recorded rather than the better number quoted: the cap works
by resolving contention, and contention falls once chunks outnumber practices.
T3, why 3 when 1 measured better. A cap of 1 gives 0.0755 on the fixture and was rejected. Every
document in that fixture states exactly one practice, so it measures no recall loss at any cap —
which is a property of the fixture, not evidence of safety. Choosing 1 on it would be fitting the
engine to the answer key, the same mistake ADR-0071 recorded the audit refusing. So the cap comes
from what a paragraph plausibly evidences: a handful of related practices, given that one document
serving several practices is the reuse ADR-0062 is built around.
T3, the recall cost accepted deliberately. When a chunk genuinely evidences more practices than the
cap, real matches are dropped — demonstrated by a unit test that asserts the two weakest claims are
lost, so the cost is visible in the suite rather than only in prose. Accepted because what is dropped
is always the weakest claim on that chunk; because recall into a queue nobody can work through is not
recall; because a missed practice stays visible as a gap and in the finalization gate, so the
assessment scores unmet rather than silently assessed; and because evidence can still be linked by
hand with the cap one setting from off. The fixture cannot quantify that cost and no number here
should be read as having measured it.
What T3 actually took. The cap was per-call and that made it advisory: practices already holding
proposals drop out of the next run as covered, freeing their slots for the next three, so clicking
propose repeatedly would rebuild the old flood a tier at a time. The existing end-to-end test caught
it — a second propose call stopped being the no-op it has always been. The cap now counts all live
claims on a chunk. That is the second time in two sprints a test written for another purpose has
found a real defect.
T4 — does the concentration survive real documents? (ADR-0073, accepted). A fair objection to T3: its
evidence came from a corpus padded with one-paragraph synthetic distractors, so chunk concentration
might be an artifact of short uniform text rather than a property of the engine. Two things had to be
said before anything could be measured. Precision and recall cannot be computed on a real corpus here
— they need an expert-labelled answer key and no real corpus has one. And real evidence cannot enter
this repository at all: `docs/testing-with-real-documents.md` is explicit that the repo is public and
the working copy is cloud-synced, so real documents belong only in a Docker volume on the machine
that owns them. That is a constraint, not a gap to route around.
T4, what is measurable without labels. Chunk concentration needs no ground truth — it is a property
of the proposals alone, and it is exactly the mechanism ADR-0071 identified and ADR-0072 acts on. The
corpus is what `data/sample_evidence/` legitimately holds, including one genuinely real document:
`nerc_cip_003_8.pdf`, a public NERC CIP standard nobody wrote for this project, which alone produces
107 chunks. On 128 chunks: the old engine made **355 proposals over just 65 distinct chunks with one
chunk claimed by 56 practices**; with the cap, 149 proposals over the same 65 chunks.
T4, the answer. Concentration is worse on real documents, not better — 56 practices on one chunk
against 44 on the synthetic corpus. A long standards PDF contains paragraphs of general governance
language that look plausible against most of a framework, and they absorb proposals exactly as the
synthetic ones did. The proposal count is 355 again, the same figure ADR-0071 measured at 5 and at 505
documents, on a completely different corpus of real prose — that structural finding reproduced
independently. The cap's default of 3 is left unchanged: this measurement gives no reason to move it,
and moving it on a corpus with no answer key would be picking a number to flatter a statistic.
T4 also went to `main` without a pull request before this one, which is worth recording rather than
quietly fixing: every other change in this project has had a review trail and that one did not. CI was
green on it, so nothing shipped unverified — but it was reverted (`a8bac3b`) and reapplied through
this PR rather than force-pushed over, because rewriting a branch other clones may hold is a worse
trade than a visible correction.
Found while doing T4, not reported by anyone. `scripts/measure_aqs.py` wrote its retained originals
(ADR-0056) into the repository's own `data/raw` rather than its temp directory, so T2 and T3's corpus
sweeps left **2,320 files** behind in a cloud-synced working copy. Gitignored, so never committed,
and still exactly what `docs/testing-with-real-documents.md` exists to prevent. Cleaned up and the
script fixed.
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
