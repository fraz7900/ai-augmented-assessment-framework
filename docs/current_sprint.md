Current sprint: Sprint 23 — act on a tester's report: make the review queue navigable, give the
dashboard a visual, and refuse the one request that would undo the platform's safety argument
Objective: one tester raised three things. Filters on the evidence queue (T1) and a domain
completion chart on the dashboard (T2) are built. Bulk actions — specifically "accept all with
confidence > 0.85" — are declined, on this project's own measurements rather than on preference,
and ADR-0065 records why in the terms a future reader will want. No change to the mapping engine, no
auto-accept, no new frameworks, no refactors outside the two.
Status: **Sprint 23 is complete. Both tranches are CI-confirmed and merged to `main`** — T1 as
`9436460` (PR #12), T2 as `336a952` (PR #13). CI reproduced this machine's numbers on both: **658
backend tests passing**, `ruff check` clean, **116 frontend tests across 18 files**, and `npm run
build`, the real `tsc -b`. `npm run lint` is not a CI step, so its result stays local: the same 2
pre-existing fast-refresh warnings in `EvidenceSourceBadge.tsx` and no new ones. Nothing is left in
the working tree. One measurement worth keeping from T2's local runs: the run that produced 116 was
clean at 18 of 18 files with zero errors, and the run immediately before it lost 5 files to the
forks-worker timeout with zero assertion failures — same code, same machine, minutes apart.
AGENTS.md's reading of that as the environment rather than the code holds, and CI settled it both
times.
All three of the tester's items are now closed: filters shipped (T1), the completion chart shipped
(T2), and the threshold bulk-accept is declined in writing (ADR-0065) rather than left as an
unrecorded no.
Sprint 22 closed before this one began: T1 merged as `dac8c52` (PR #9), T2 as `9a1a223` (PR #10),
the record corrected in `7816ee0` (PR #11). R-39 is mitigated with residual R-40; R-35 is half
closed, its in-memory half still open.
The feedback, and why it splits. The tester reported that the Evidence page piles up links and that
going through them with Accept/Edit/Reject one at a time is a pain, asking for bulk actions and for
filters by domain and status. The first half is simply true and had no counter-argument:
`GET /assessments/{id}/evidence` took no parameters and returned every link on the assessment, so
scrolling was the only tool. The second half collides with three things this repository already
knows, which is why it is refused in writing rather than quietly not built.
Why "confidence > 0.85" is not a conservative setting. R-16's Sprint 5 calibration put correct
practice/evidence pairs at 0.65–0.78 and incorrect ones at 0.43–0.53, with the live threshold at
0.55 and a confirmed false positive at 0.71 — above many genuinely correct pairs. **Nothing correct
has ever been observed above 0.78**, so a 0.85 cutoff does not select the safest links, it selects
from a band nobody has characterised. The value is also not a probability: `distance_to_confidence`
calls itself a similarity heuristic in its own docstring, and `ConfidenceMeter` already refuses to
collapse it into a pass/fail badge. And auto-accept is AGENTS.md rule 2, the rule R-1's Closed status
and R-16's "mitigated by human-in-the-loop" both rest on — a threshold accept reopens both.
What the tester actually found, under-sold. The pilot readiness audit measured mapping precision at
**0.012** — 4 true positives against 338 false positives across 342 proposals — because
`mapping_candidates_per_practice=1` proposes the best chunk for every uncovered practice whenever it
clears 0.55, and on a small corpus nearly every practice finds one. The queue is long for that
reason, not for want of buttons, and bulk-accepting from a pool that is ~99% noise would
industrialise a wrong answer into a sealed, exported record. The audit labels its own run
scaffolding-scale (5 documents), which is an argument for re-running it at 100–1,000, not for
automating on top of it.
T1 (merged, `9436460`) — filters (ADR-0065, accepted). `GET /assessments/{id}/evidence` gains `review_status`, `domain`,
`min_confidence` and `max_confidence`, all optional, response shape unchanged so an existing caller
sees exactly what it saw. Domain is resolved through the framework definition
(`domain_for_practice_id`) against the assessment's **pinned** version (ADR-0058), never stored on
the row — domain membership is framework data (ADR-0002) and a denormalised column would drift from
it. An unknown domain returns nothing rather than everything, because a filter that degrades to "no
filter" looks like it worked. A link with no confidence is excluded from a confidence filter rather
than treated as 0.0: a manual link has none because a human chose it, not because retrieval scored
it badly. Filtering runs in the service layer because the domain filter cannot be expressed in SQL
at all, and splitting it across two layers would be worse than scanning one assessment's links.
T1 counts, and why they are a second endpoint. `GET /assessments/{id}/evidence/summary` reports
totals by status and by domain over the WHOLE queue and takes no filter parameters, because a total
that moves with the filter cannot tell a reviewer what they are not looking at. It also reports
`unmapped`: links whose practice is not in the pinned framework, which belong to no domain and which
no domain filter can reach. Those are surfaced in the UI rather than left to be discovered — a
reviewer working domain by domain would otherwise never learn they exist. They are not creatable
through today's API, which validates practice references; they come from rows predating that
validation and from practices leaving framework data under a pinned version, so the integration test
plants one through the repository the way reality produces it.
T1 frontend. A filter bar on the Evidence tab: review state, domain, and confidence as **named bands
rather than a free number** — "Measured-correct band (0.65–0.78)", "Above any measured match
(> 0.78)" — because a box inviting someone to type 0.85 invites exactly the cutoff this sprint
declined, and the top band carries a note that no correct match has been measured there. Every count
shown comes from the unfiltered summary, the bar always reads "showing N of M", and the domain
chooser offers only domains with links in them. The filter is component state, not a URL parameter:
a filtered queue is a reading aid for one sitting, and a bookmarkable one can later be mistaken for
the whole queue.
T1, what it is not. The filter control has exactly one button, "Clear filters", and a test asserts it
has no other — the requested feature is one button away from existing, and what stops it should be a
test rather than a memory. **This makes the queue readable, not shorter.** The precision finding is
untouched; a reviewer with a good filter still faces a queue that is mostly noise. A filter can also
hide work from someone who forgets it is applied, which is mitigated by construction — unfiltered
counts, an explicit "N of M", and the unmapped disclosure — rather than by a note.
What T1 actually took, recorded against the plan. Two assumptions were wrong in front of the code.
First, this plan expected `practice_reference` to be free text, per the model's own docstring; the
API has validated it against the framework since well before now and returns 422, so the unmapped
case is unreachable through it and the test had to plant the row at the repository. Second,
React Query invalidation after a review had to move to an unfiltered key prefix: with the filter now
part of the query key, the existing `keys.evidence(id)` invalidation would only have refreshed the
unfiltered list, leaving a reviewer working inside a filter looking at a row they had just decided
on. Neither was caught by inspection — the first by a test failing on a 422, the second by reasoning
about the key while writing it, which is the cheaper of the two ways to find it.
T2 — a domain completion chart (ADR-0066, accepted). The tester's other request: the dashboard was
text and numbers with no visuals. The whole decision was which number the bars draw from, because the
obvious candidate is wrong in a way nobody would notice later. `domain_scores` is already on the wire
and one line from being charted — and it is an ordinal MIL 0-3 under one scoring model and a 0.0-1.0
fraction under the other, so bars drawn from it put a maturity level and a percentage on one axis.
That is R-15 verbatim, and it would have looked entirely plausible: MIL2 of 3 renders as a
two-thirds bar and nothing in the output would announce that an ordinal scale had been stretched
into a proportion.
T2, what the bars actually are. `met_practices` over `total_practices`, applicable practices only —
the same denominator `compute_domain_coverage` uses, so the bar and the score beside it cannot
disagree about what was counted. Computed server-side as `DashboardReport.domain_progress`, because
`DashboardTab`'s own contract is that it re-derives nothing and a percentage assembled in the browser
would be a second implementation of that denominator. Not derived from `complication`, which lists
only domains with at least one gap: right for "where gaps remain", wrong for a chart, since dropping
the finished domains overstates what is outstanding and hides the best news in the assessment. The
domain's real score travels beside each bar in its own units — `MIL2`, `50% coverage` — so the two
read as two facts rather than one.
T2, the field that is the point. Under a cumulative framework completion and score are different
shapes: MIL2 requires EVERY MIL1 practice, so 9 of 10 met is a 90% bar sitting next to MIL0 when one
MIL1 practice is missing. Correct behaviour that reads as a bug. `blocking_mil` and
`blocking_practice_count` name which level is blocked and by how many, and the chart says it under
the bar — "1 practice(s) at MIL1 still unmet, so this domain cannot score above MIL0 however
complete the bar looks." A reader who would have filed a defect learns what to do next instead. The
fields mirror `compute_domain_mil`'s rule rather than reimplementing its result, and are None on a
coverage framework and at the top level, where there is no gate to name.
T2, what it is not. **The exports do not get the chart.** PDF and XLSX carry the same numbers through
`complication` and `so_what` but neither the visual nor the MIL-gate sentence, so a reviewer who
reads the gate explanation on screen and then sends the PDF has sent something without it. That is a
real screen/document inconsistency, disclosed in ADR-0066 rather than left to be found, and closing
it is work in the report renderers. Unpopulated domains are omitted rather than charted at zero, and
so is a domain whose every practice is NOT_APPLICABLE — `0 of 0` reads as "nothing done" rather than
"nothing applies". No charting library: ten bars do not justify a dependency (ADR-0016), and each bar
carries an `aria-label` with the same numbers in words.
What T2 actually took, recorded against the plan. One thing was wrong in front of the code, and it
was in the tests rather than the feature: the first draft asserted that a NOT_APPLICABLE finding
shrinks the chart's denominator, with no evidence attached to the finding. ADR-0057 only lets a
SUPPORTED finding move anything, so the code was right and three tests were wrong. Fixing them made
them better tests, since they now encode the evidence requirement rather than assuming it away.
Next (not started). The three steps this sprint's analysis put in front of any bulk-action work, in
order. Expose `compute_assessment_agreement` (ADR-0034), which already computes accept/edit/reject
rates from real human decisions and has no endpoint, bucketed by confidence band — after a few
hundred reviews that is this project's first real answer to what fraction of proposals above a given
band a human actually accepts. Re-run `scripts/measure_aqs.py` against 100–1,000 documents with
negative labels, which is the audit's own recommended next step and has been open since Sprint 17.
Only then design bulk review, most likely as filter-read-confirm with per-link audit rows and a real
actor (ADR-0061), never as a threshold. Separately, and smaller: carry the MIL-gate sentence into the
PDF and XLSX renderers, which T2 deliberately left on screen only.
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
Explicitly out of scope this sprint and not begun: bulk review decisions of any shape; charts in the
PDF and XLSX exports; changes to
`mapping_candidates_per_practice` or `mapping_similarity_threshold`; authentication, RBAC and
per-user permissions; cloud deployment; organisation deletion, merge, or reassignment; new
frameworks; continuous monitoring; score-change notification; and legacy registry backfill.
Charter: PROJECT_CHARTER.md
Constraint: local-first by default. Evidence content must not be sent
to a cloud API unless explicitly opted in (see PROJECT_CHARTER.md Section 7).
Data rule: only public framework documentation or synthetic sample
evidence belongs anywhere under data/ (see data/sample_evidence/README.md).
