Current sprint: Sprint 22 — give the platform a concept of whose assessment this is, and stop
ingestion job rows accumulating forever
Objective: two independent tranches. First, an organisation that owns assessments and documents, so
one client's evidence cannot be attached to another client's assessment through the product — R-39,
the only open risk carrying High impact, and the one `docs/project-status.md` names as what stands
between this and a multi-client pilot. Second, a retention policy for the `ingestionjob` table,
which ADR-0059 disclosed rather than solved. No authentication, no RBAC, no cloud deployment, no
new frameworks, no refactors outside the two.
Status: **Sprint 22 is complete. Both tranches are CI-confirmed and merged to `main`** — T1 as
`dac8c52` (PR #9), T2 as `9a1a223` (PR #10). The charter decision below came back yes, so T1 ran: `f25668f` (backend, ADR-0063, the charter amendment, R-39 and R-40) and `ce5094e`
(frontend). The branch is pushed and PR #9 is open against `main`; run `32280521820` is green on
both jobs. CI reproduced this machine's numbers rather than merely agreeing with them: **615 backend
tests passing** in 5m45s, `ruff check` clean, **93 frontend tests across 16 files**, and `npm run
build`, which is the real `tsc -b` typecheck. `npm run lint` is not a CI step, so its result stays a
local one: the same 2 pre-existing fast-refresh warnings in `EvidenceSourceBadge.tsx` and no new
ones. Nothing is left in the working tree. The local frontend count had come from a re-run — the
first attempt lost 7 of 16 files to the forks-worker timeout with zero assertion failures — and the
runner taking all 16 first time is one more measurement supporting AGENTS.md's reading of that as
this environment rather than the code. T1's last open acceptance criterion, CI green on the branch,
was met there, and PR #9 merged as `dac8c52`. T2 follows on `feat/ingestion-job-retention`, branched
from the merge rather than developed alongside it, for the conflict reason this file records below.
Its own run, `32283465604` on PR #10, is green on both jobs and again reproduces this machine's
numbers: **630 backend tests passing** (615 plus 15 new), `ruff check` clean. T2 is backend-only, so
the frontend numbers are unchanged and were confirmed unchanged rather than assumed — 93 across 16
files on the same run. Nothing is left in the working tree on either branch.
`docs/project-status.md` still reads "As of: Sprint 21" and has not been rolled forward — it
predates this sprint, so nothing in it accounts for the organisation boundary, R-40, or the
retention window, and it should not be read as a current view until it is.
Decision made, and recorded rather than assumed. PROJECT_CHARTER.md Section 12 listed
"multi-tenant authentication and role-based access control" as explicitly out of scope for the MVP.
T1 built the data-model half of that line and none of the identity half: assessments and documents
gained an owner enforced server-side, while who the requester is stays exactly where ADR-0061 left
it, a username asserted by the reverse proxy. Whether that counted as reopening the charter line
was the project owner's call rather than this file's, the precedent being Sprint 19's OCR
reversal — made by direct owner instruction and recorded in Section 12 rather than quietly
delivered. The answer was yes, given directly, and Section 12 now
carries the reversal in that same shape: what was built, what was not, and where the residual is
recorded. The alternative first tranche this paragraph named if the answer had been no — the ops
items under Next, R-9 first — is untouched and still available.
T1 — an organisation that owns assessments and documents (ADR-0063, accepted). `Organization(id,
name, created_at)` with a unique name, then `Assessment.organization_id` and
`Document.organization_id`, both foreign keys, both indexed, both non-null. The document field is
the part that needs justifying rather than merely implementing, because ADR-0062 refused
`Document.assessment_id` three weeks ago and a reader is entitled to wonder whether the project
changed its mind. It did not, and the ADR should say so in those terms: one policy PDF legitimately
serves a C2M2 assessment and a NIST CSF one over the same corpus, which is the cross-framework
workflow this product is built around — but it serves them for one client, never two. So the
assessment relation stays many-to-many and the organisation relation is single-owner, and the two
are consistent rather than contradictory.
T1 enforcement, in the place Sprint 21 learned to put it. `AssessmentRepository` gains an
`_assert_same_organization` that re-reads both rows inside the transaction performing the attach —
ADR-0060's lesson applied to a new guarantee rather than re-learned two sprints later, since a
check that reads through one session and writes through another is the R-11 bug class and this is
the second guarantee in a row meant to be absolute. The service check stays in front of it, because
it produces the 409 before any work is done, and the repository check logs at error level, because
a backstop that fires silently stops being a backstop. Scoping applies to `GET /documents`, `GET
/assessments`, the attach flow, `propose_mappings`, and chat retrieval. The last two are where this
is easiest to get wrong and where being wrong costs most: both reach the vector store rather than
the relational one, so the test that earns its keep plants a cross-organisation document holding a
deliberately high-similarity chunk and asserts it is never proposed and never quoted.
T1 migration, which is the riskiest hour of this sprint and not the feature. Insert the default
organisation row first, then add each column with `ALTER TABLE ... ADD COLUMN organization_id TEXT
NOT NULL DEFAULT 'org_default'` — legal in SQLite with a default, and following the existing
`_add_missing_columns` idiom rather than introducing a second one. Raw SQL, for the reason
ADR-0062's backfill already documents and proved: a migration must not depend on the current ORM
mapping being able to read old rows, and on this codebase it demonstrably cannot, since a
pre-ADR-0030 database holds `evidencelink` rows whose `source` today's enum refuses to load. The
disclosure that travels with it belongs in the ADR and the register rather than a release note:
backfilling does not retroactively separate anything. An instance that already mixed two clients'
documents stays mixed, because nothing in the data can tell them apart and guessing would be worse
than not trying. `scripts/backup.sh` exists now — run it before the first migration against a real
database, and say so in the ADR.
T1 seal, and what stays immutable. `organization_id` joins the seal payload at version 3, so an
assessment cannot be moved between organisations after finalization without the seal reporting it.
This is ADR-0060's per-version field lists doing exactly what they were built for: v2 seals keep
verifying under v2 rules, and a v3 seal read by a build that only knows v2 reports `unverifiable`
rather than `altered`. An assessment's organisation is set at creation and never reassignable this
sprint, and organisation deletion and merge are not built — deleting an organisation that owns
assessments is a data-loss question that deserves its own decision rather than a default.
T1 frontend. An organisation selector in the app shell; assessment creation requires one; upload
targets one; `AttachDocumentControl` and `DocumentPicker` list only same-organisation documents.
The assessment header shows the organisation name, and so do the PDF and XLSX headers — the
cheapest confidentiality control in this sprint is a reviewer always being able to see whose record
they are looking at, and it costs a line in each export.
T1, what it is not, stated as loudly as ADR-0062 stated its own limit. Anything able to reach the
API directly can still pass any `organization_id` and read any organisation's data. After this
tranche the product cannot cross the boundary and accidental cross-attachment becomes impossible; a
deliberate API call is unaffected. **R-39 is therefore narrowed, not closed** — it moves from
"possible by hand through the UI" to "possible by bypassing the UI," which is the same perimeter
assumption ADR-0061's attribution already rests on and the same reason the stack must not be
exposed to a network. A new register entry, R-40, should name that residual precisely, so this
sprint is not read as having delivered tenancy.
T1 acceptance criteria: creating an assessment or ingesting a document without an organisation is
refused by the API; a cross-organisation attach returns 409 enforced at the repository inside the
write transaction and logged at error level, proven by a test that calls the repository directly
rather than through the service; `GET /documents` and `GET /assessments` never return another
organisation's rows; `propose_mappings` and chat cannot surface a cross-organisation chunk, proven
by the planted-chunk test above; a fixture database built at the pre-sprint schema — including a
finalized, sealed assessment and pre-ADR-0030 evidence links — opens, backfills, and every
pre-existing seal still verifies as `verified`; exports name the organisation and new seals are v3;
suite green, `ruff` clean, `tsc -b` and lint clean, CI green on the branch.
T1 sequence, in dependency order, with the migration test written before the migration because it
is the only step whose failure mode is unrecoverable for an existing install: model, migration and
default-organisation bootstrap; repository scoping and the in-transaction attach guard; the service
and API surface (organisation create and list only, scoped lists, ingestion carrying an
organisation); seal v3 and export headers; frontend. Expected files: `models/assessment.py`,
`models/schemas.py`, `repositories/assessment_repository.py`, the assessment, ingestion, audit_seal,
export, report, chat and mapping services, `api/{assessments,documents,ingestion,dependencies}.py`,
and on the frontend `api/assessments.ts`, `api/types.ts`, a new `OrganizationSelect.tsx`,
`AssessmentsListPage`, `AssessmentDetailPage`, `UploadPage`, `AttachDocumentControl`,
`DocumentPicker`. Roughly 25-35 new backend tests and 6-10 frontend; this tranche is the larger of
the two by a wide margin.
What T1 actually took, recorded against the plan rather than tidied to match it. Two things were
decided differently once the code was in front of them. First, this file said `organization_id`
would be non-null and required; it is non-null, but omitting it is allowed while exactly one
organisation exists, because requiring it everywhere would have churned roughly 140 call sites to
make the single-organisation deployment the charter scopes worse, while the conditional rule
refuses the one case that is actually dangerous. Second, `link_evidence` needed the boundary check
too, which this plan did not anticipate: linking attaches implicitly (ADR-0062) and the attach runs
after the evidence link is persisted, so leaving the attach to refuse would have written a
cross-organisation citation and then returned a 409 too late to matter. It was found while writing
the integration test for it rather than by inspection — the third time in two sprints that a test
written for one purpose has found a different real defect.
Delivered inside T1 and not listed in this plan, named rather than absorbed: `IngestionJob` gained
an organisation so "Recent uploads" is scoped, while the queue's backpressure count deliberately
stays instance-wide, since scoping that count would hand each organisation the full queue depth and
the bound would stop meaning anything; and organisations can be renamed, which is what makes a
migrated instance's "Unassigned" survivable, and is safe precisely because the seal covers the id
rather than the name. The migration-test helper also cost more than expected: a pre-sprint schema
cannot be simulated by dropping the column, because SQLite refuses to drop one a foreign key still
names, so it rebuilds both tables the way SQLite's own documented table rewrite does.
T2 (built) — a retention policy for ingestion jobs (ADR-0064, accepted). `ingestionjob` rows
accumulated with no bound (R-35). Terminal jobs whose `finished_at` passes a configurable window are
now deleted, swept at startup and after each job completes; a QUEUED or RUNNING row is never touched
however old it is, and the count swept is logged. The default is argued rather than picked, which
this file asked for: a job row is needed while the browser polls it, and afterwards only to answer
"what happened to that upload?", a question with a horizon of weeks rather than months, since the
outcome is visible in the document list either way — 30 days, configurable, is defensible on that
reasoning and nothing longer is. R-35's other half stays open and disclosed: queued uploads are
still held in memory until a worker frees up, and spooling them to disk changes the queue's failure
model rather than extending a retention sweep. The register row now says half-closed rather than
closed, for that reason.
What T2 actually took, recorded against the plan rather than tidied to match it. Three things this
plan did not say. First, ADR-0059 had deferred retention until "a real corpus makes the number
concrete", so ADR-0064 had to deal with that deferral rather than quietly overrule it: the honest
answer is that the measurement is not coming — no volume threshold on a hand-fed local instance
makes the table's own size alarming — and the argument actually needed never depended on volume, so
the ADR says that in those terms instead of claiming evidence it does not have. Second, a retention
window of 0 disables the sweep entirely, which the plan did not call for; a deletion policy with no
way to turn it off is a worse default than one with an escape hatch, and an operator reconstructing
an upload history for an audit should not have to patch code. Third, the two sweeps at startup are
ordered, and the order is load-bearing rather than incidental: the interrupted sweep stamps each
stranded job with a `finished_at` of now, so running retention afterwards gives a job stranded a
year ago its full window as a readable FAILED row instead of converting and deleting it in the same
second. That has a test of its own, because a comment explaining an ordering is not the same thing
as an ordering that stays.
Delivered inside T2 and named rather than absorbed: the sweep runs in a `finally` and swallows its
own exceptions, so a broken cleanup cannot cost a user the upload they were waiting on — the job
outcome is already persisted by then; and the sweep is deliberately instance-wide rather than scoped
to an organisation, on exactly the reasoning ADR-0063 used for the backpressure count, since a
per-organisation sweep would leave every other organisation growing as before. 15 tests: 7 at the
repository where the deletion happens, 8 at the service where the window and the timing do. The
repository tests are the ones that earn their keep, and they are mostly about what the sweep does
*not* delete.
Known about this plan before it starts, rather than discovered after. The two tranches both add to
`models/assessment.py` and will conflict there if developed in parallel — Sprint 21 claimed PR #2
and PR #3 touched different files and merged cleanly in either order, and that was simply wrong, so
this file will not make the same claim twice. Land T1 first, or branch T2 from it. And T1 touches
the two places in this codebase where a mistake is not recoverable by re-running anything: the
migration, which rewrites the only copy of a record whose whole value proposition is immutability,
and the seal payload, which every finalized assessment is verified against.
Next (not started), unchanged from Sprint 21 and not claimed by either tranche above. R-9, no
reproducible environment bootstrap, rated High likelihood and already occurred once — the strongest
candidate for a third tranche or a substitute first one if the charter decision above comes back
no. R-33, OCR-recovered text is approximate and nothing downstream of ingestion flags a citation
drawn from an OCR'd page. R-34, ADR-0057's scoring correction can lower a number already given to a
stakeholder and the platform cannot tell anyone it changed. Backups remain on demand, with no
schedule, rotation or off-machine copy. The retrieval precision ceiling R-16/R-23 and the recall
finding the Sprint 17 audit surfaced and deliberately did not act on. The copyright-limited
transcriptions R-28/R-30/R-32. The local frontend test runner still drops a file on roughly two runs
in five after its Sprint 21 reinstall; AGENTS.md carries the measurements and CI remains the
authority.
Also open and unchanged. Upload retention is not retroactive, so the 6 of 30 documents whose
originals were discarded before ADR-0056 stay permanently un-re-ingestible; 27 of 30 stored
documents predate the registry (ADR-0039) and carry no `content_hash`; and assessments finalized
before ADR-0060 carry no seal, report `unsealed` rather than `verified`, and are deliberately not
sealed retroactively.
Explicitly out of scope this sprint and not begun: authentication, RBAC and per-user permissions;
cloud deployment; organisation deletion, merge, or reassignment of an existing assessment; moving
documents between organisations; new frameworks; continuous monitoring; retrieval precision work;
score-change notification; and legacy registry backfill.
Charter: PROJECT_CHARTER.md
Constraint: local-first by default. Evidence content must not be sent
to a cloud API unless explicitly opted in (see PROJECT_CHARTER.md Section 7).
Data rule: only public framework documentation or synthetic sample
evidence belongs anywhere under data/ (see data/sample_evidence/README.md).
