Current sprint: Sprint 30 — audit what is actually broken, and make the record true
Objective: a closing pass. Find anything genuinely critical and fix it, bring the status snapshot
back to the truth, and consolidate what this platform deliberately does not do into one place a
reader can actually finish. No new product features: the point of this sprint is that someone
picking the repository up should be able to trust what it says about itself.
Status: **Sprint 30 is closed.** T1 and T2 merged in PR #32; the follow-up in PR #33 stamps this
sprint into the snapshot itself, since a status document that stops one sprint short of the present
is the same defect this sprint existed to fix, only smaller.
Sprint 29 closed with both tranches merged in `4f98557`: the oldest open risk (ADR-0082) and one
backup command worth scheduling (ADR-0083).
The audit, and what it found. Run before deciding what to fix, so the answer would be evidence rather
than assumption: the golden-path end-to-end test passes, the app boots with all 40 endpoints
registered including every one added since Sprint 22, 811 backend and 146 frontend tests are green,
`ruff` is clean, there are **zero** TODO/FIXME/XXX/HACK markers anywhere in `backend/src` or
`frontend/src`, and no ADR reference in any document points at an ADR that does not exist.
One false alarm, recorded because reporting it as a defect would have been worse than missing it. A
first pass flagged 15 documents referencing scripts that "do not exist" — `scripts/measure_aqs.py`
and others. They all exist, at `backend/scripts/`; the check resolved paths from the repository root
and the ADRs write them relative to `backend/`. Nothing was wrong except the check.
T1 — the status snapshot was six sprints stale, and that was the critical finding. `docs/project-
status.md` read "As of: Sprint 23", claimed 69 ADRs against an actual 83 and 681 backend tests
against an actual 811, and accounted for none of Sprints 24-29 — which is to say none of the
mapping-engine measurement, the OCR provenance chain, export currency, the reproducible environment,
hash pinning, or R-11. That document is the one someone reads to decide whether to trust this
platform, so a stale one is not a tidiness problem: it is the platform making false claims about
itself, in the place most likely to be believed.
T1, what changed. Header and counts corrected. Six sprint rows added, each saying what the sprint
actually established rather than what it shipped. The backups limitation rewritten — it still said
"no schedule, no rotation, and no off-machine copy" when two of those three are now closed. Three new
limitations added that had never appeared in the snapshot at all: OCR provenance and its four-value
honesty, export currency and what a one-way digest cannot tell you, and hash-pinned dependencies plus
the interpreters being declared rather than installed. And the roadmap section rewritten, because it
still described re-measuring precision as the next step when Sprint 24 did it and got an answer.
T2 — what is deliberately not done, in one place (ADR-0084, accepted). This project's habit is to
disclose rather than hide, and that habit has a cost nobody notices while it accumulates: **the
limits are now spread across 83 ADRs and 40 register rows.** A limitation that takes an hour to find
is not meaningfully disclosed. ADR-0084 decides nothing new; it consolidates, and it sorts the open
items into three kinds a reader keeps conflating — scope decisions that are deliberately out and
recorded in the charter, items blocked for a stated structural reason, and things that could be
closed, have not been, and cost something real.
T2, and the line worth reading if only one is. The platform's conclusions are traceable, and its
retrieval is not accurate. Human review is what stands between those two facts — which is why it is
structural rather than advisory, and why every feature touching the review queue has been built to
make a reviewer's judgement cheaper rather than to replace it.
The largest honest gap, named as such. `/aqs/agreement` was built in Sprint 24 to turn real review
decisions into data, and **nothing has fed it.** Sprint 23's queue work came from one tester using
the product in anger and was measurably right; everything since has reasoned from fixtures. That is
the single largest distance between what this platform has measured and what it claims, and no
amount of further building closes it — only a reviewer at volume does.
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
