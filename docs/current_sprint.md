Current sprint: Sprint 21 — unblock ingestion of the documents this product is actually for, and
make the finalized record defensible rather than merely locked
Objective: two independent tranches, both merged. First, remove the hard limit that stopped a
large or scanned document being ingested at all. Second, close R-12, open in the risk register
since Sprint 2. No new frameworks, no auth/RBAC/multi-tenancy, no refactors outside the two.
Status: Everything below is merged to `main` and CI-verified there — async ingestion via PR #2
(`05efacf`, merge `147e111`), the finalization work via PR #3 (`9e8dbce` + `68e1788`, merge
`9234c39`), the audit-trail and operational pass via PR #4 (merge `ed8ed0a`), and the form fix via
PR #5 (merge `dd5138b`), and the assessment-document association as `044a54d`, with ADR-0059
through ADR-0062 recording the decisions. As of `044a54d`: **584 backend tests passing**,
`ruff check .` clean, **78 frontend tests passing** across 13 files, `tsc -b` clean, `npm run lint` clean (the same 2 pre-existing fast-refresh warnings in
`EvidenceSourceBadge.tsx`, untouched all sprint). The frontend counts are CI's, not this machine's:
the local vitest runner stopped working partway through the sprint (see Next). Nothing is left in
the working tree.
T1 — asynchronous ingestion, with selective OCR alongside it (ADR-0059). Ingestion held the HTTP
request open for the whole parse/chunk/embed pass, and nginx closes a proxied read at 300s — about
200 pages at the measured ~0.7s per chunk. Past that the browser was told "gateway timeout" about
an ingestion that was still running, with no record the work had started and no way to tell a
timeout from a rejection. That ceiling is reachable with ordinary evidence for this product (a
505-page manual, a deck needing OCR on most pages), and `deployment/frontend.nginx.conf` had
already named the fix in Sprint 18: "background ingestion with a job-status endpoint, not a bigger
number." Now: `POST /ingest/async` records an `IngestionJob` and returns 202; `GET
/ingest/jobs[/{id}]` is polled for the outcome. `IngestionService.ingest()` is called unchanged,
so ADR-0046's compensating delete and ADR-0055's retain-after-registry-write ordering keep their
exact sequence instead of being re-derived somewhere they could drift. One worker (CPU-bound work
on a machine that may also be running the browser; FIFO for free), a bounded queue
(`max_pending_ingestions`, 429 when full, restoring the backpressure that waiting on the request
used to provide), failure categories as a closed enum rather than prose, and a sweep on startup
that fails anything a restart stranded — a row reading RUNNING forever is a worse answer than one
saying it was interrupted. Selective OCR rides along because the same documents motivate it: a
part-text-layer, part-scanned PDF now OCRs only the pages pypdf found nothing on, at its own
`SUCCESS_PARTIAL_OCR` status with a composite `parser_version` naming both engines.
T1 frontend. The browser uploads exclusively through the queue and polls the job — no size
threshold, because that would put the two paths' behaviour on opposite sides of a number nobody
can see, and the boundary case (a 24MB scan that OCRs for six minutes) is where being wrong costs
most. Consequences worth naming: caches refresh when the job *succeeds*, not when the upload is
accepted, since a 202 means the work was taken and refreshing then shows a list that still lacks
the file just uploaded; Upload stays disabled for the whole job rather than the POST, because the
POST now returns in about a second while the work runs for minutes; a "Recent uploads" list exists
because the outcome no longer arrives in the upload's own response, and "is it in the document
list?" cannot separate still-running from failed; and `UploadProgress` no longer says "don't close
this tab", which was true when the work lived in the request and is false now. The unused
synchronous hook was deleted; the synchronous endpoint itself remains and is still tested.
T2 — the finalized-assessment write lock, and a tamper-evident seal (ADR-0060). R-12 said nothing
outside `AssessmentService` stopped a direct-repository call writing through the
audit-immutability guarantee; it was carried honestly for eighteen sprints on the reasoning that
no code path did this, while ADR-0058's finalization gate was built on top of that same single
layer. Investigating it found a second defect the entry had never named, on the sanctioned path
rather than around it: the service read the status through `get_assessment()` (one session, opened
and closed) and then wrote through a second session, so an assessment finalized between those two
moments was written to anyway — R-11's check-then-act bug class, on the one guarantee meant to be
absolute. `AssessmentRepository._assert_writable` now re-reads the status inside the transaction
that performs the write, on the five methods the service already guards. `update_status` is
excluded (it must reach FINALIZED) and `create_sanitization_approval` is excluded (the service
does not block it either; approving a sanitized export adds no claim to the record). The service
checks stay — they produce the 409 before any work is done — and the repository check logs at
error level, because a backstop that fires silently stops being a backstop. On the race
specifically: SQLite's default rollback journal is sufficient here, verified rather than assumed
(`journal_mode=delete`, and no WAL or `isolation_level` configuration anywhere in the codebase),
so `BEGIN IMMEDIATE` was deliberately not bundled.
T2 detection. Prevention is application code and does not survive a text editor, so the whole
record — assessment, evidence links, practice findings, both append-only history trails, evidence
requests — is canonicalised into one SHA-256 at finalization, and `GET /assessments/{id}/verify`
recomputes it against the current database. Four states, not a boolean: "no seal" and "seal does
not match" are opposite situations, an unsealed record is unverified rather than untrustworthy,
and a seal from a build that knows a payload shape this one does not is `unverifiable` rather than
`altered`. Every outcome is a 200, because a detected alteration is that endpoint working. The
seal is printed into every PDF and XLSX export, which is the part that makes it evidence: a digest
stored beside the record it protects proves nothing against someone who edits the record and
recomputes the digest, so it only bites once a copy exists elsewhere — and this product already
hands people copies. Three canonicalisation decisions each prevent a seal that reports an
untouched record as altered: timestamps normalised to UTC without an offset at fixed precision
(the models are tz-aware, SQLite stores no offset), `updated_at` and the seal columns excluded
from the payload (storing the seal updates the row), and explicit per-version field lists rather
than a model dump. A seal is written once and never replaced. A per-row hash chain was considered
and rejected: one digest covers the finalized record completely, and a chain is a second mechanism
to keep correct on every write for localisation nobody has asked for.
Tooling and documentation fixed in passing, each because this sprint hit it: the repo now carries
a `permissions.allow` list of the read-only commands it actually runs (`54183a9`), derived from
transcript frequency rather than guesswork; AGENTS.md's frontend-test troubleshooting said
`--pool=threads` is "not accepted by this vitest version" when it is accepted by 4.1.10 and is the
remedy that works (the default forks pool with `--maxWorkers=1` still lost 6 of 9 files to
worker-startup timeouts at 640s, while `--pool=threads --maxWorkers=1` ran all 10 green in 149s,
twice) — corrected with the measurements, since the wrong note sent earlier sprints chasing
reinstalls; and both test counts in AGENTS.md were stale.
Corrections to previously-stated status: this file's Sprint 20 entry said "Nothing is committed —
the work sits in the working tree for review." That was true when written and stopped being true
the same day; Sprint 20 merged via PR #1 and was pushed with CI green. Corrected in `11ae269`,
which names the commits rather than describing a state, because a SHA cannot go stale — this is
the second sprint running that this sentence has been wrong, Sprint 19's entry having made the
identical mistake. Also superseded: Sprint 20's counts of 493 backend / 41 frontend tests,
accurate then, are now 546 / 57. And one claim made during this sprint was simply wrong: PR #2 and
PR #3 were described as touching different files and merging cleanly in either order. They both
add to `models/assessment.py`, `models/schemas.py`, and `assessment_repository.py`; #3 conflicted
after #2 landed. Both conflicts were independent additions at one spot, both sides were kept,
nothing was dropped, and the combined tree was re-tested (546 passing) rather than trusted — see
`2a2aba8`.
Delivered after the two tranches above, in one pass through the pilot-readiness audit's own
findings: the seal gained a frontend surface (Overview tab shows the digest and checks it on
request, rendering all four verification states rather than a boolean); decisions are attributed
to the identity nginx already authenticates (ADR-0061), with the seal payload moving to version 2
so attribution cannot be silently rewritten; `scripts/backup.sh` and `scripts/restore.sh` give the
audit record a way home, verified by checksum and with no `--force` on the destructive one; the
risk register was brought current with R-33 through R-38; the evidence-request form stopped asking
for a name the server had started ignoring, showing `GET /identity`'s answer instead; and finally
documents gained an assessment to belong to (ADR-0062). Sprint 21 therefore ran considerably wider
than its stated objective — recorded here rather than tidied away, since the objective at the top
of this file says two tranches and the history says six merges.
On ADR-0062 specifically, because the shape of the decision matters more than the diff: the
Evidence chooser called `GET /documents` and listed every document on the instance, so a reviewer
picking evidence for one organisation's assessment saw another organisation's policies and could
link them. `Document` deliberately did NOT gain an `assessment_id` — one policy PDF legitimately
serves a C2M2 assessment and a NIST CSF one over the same corpus, which is the cross-framework
workflow this product is built around, and ownership would force the same file to be parsed,
chunked and embedded once per framework. So the relation is many-to-many, linking evidence
attaches implicitly, detaching is refused while any evidence link still cites the document, and
`propose_mappings` now searches attached documents rather than only cited ones — which is what
makes it usable on a document that was just uploaded. Existing evidence links were backfilled into
associations in raw SQL, because a migration must not depend on the current ORM mapping being able
to read old rows and this one could not: a pre-ADR-0030 database holds `evidencelink` rows whose
`source` today's enum refuses to load. An existing test caught that, the second time this sprint a
test written for one purpose found a different real defect. What this is NOT is multi-tenancy: the
attach flow still browses every document, so cross-organisation attachment remains possible by
hand, and ADR-0062 says so rather than implying the tenancy problem is solved.
Next (not started): nothing structural. The Evidence tab offers attach but not detach, so removing
a document from an assessment is API-only; ingestion job rows still accumulate with no retention
policy (ADR-0059, R-35); and the local frontend test runner remains unusable on this filesystem —
every frontend change in the back half of this sprint was verified by CI alone, and a
`node_modules` reinstall (AGENTS.md remedy 5) is the next thing to try. The older register items
are unchanged: R-8 (non-English documents untested), R-9 (no environment bootstrap), R-16/R-23
(the retrieval precision ceiling, mitigated by human review rather than by accuracy), and the
copyright-limited transcriptions R-28/R-30/R-32. Real client separation — a tenant concept —
remains charter "Won't (for MVP)" scope and is the one thing standing between this and a
multi-client pilot.
Also open and unchanged from earlier sprints: upload retention is not retroactive, so the 6 of 30
documents whose originals were discarded before ADR-0056 stay permanently un-re-ingestible; 27 of
30 stored documents have no `Document` registry row (predating ADR-0039) and therefore no
`content_hash` to verify a retained original against; and assessments finalized before ADR-0060
carry no seal, are reported `unsealed` rather than `verified`, and are deliberately not sealed
retroactively. Ingestion jobs accumulate with no retention policy, which is disclosed in ADR-0059
rather than solved.
Explicitly out of scope this sprint and not begun: new frameworks, assessment-document
association, document archival/deletion, legacy registry backfill, bulk evidence acceptance, and
authentication/RBAC/multi-tenancy/cloud deployment.
Charter: PROJECT_CHARTER.md
Constraint: local-first by default. Evidence content must not be sent
to a cloud API unless explicitly opted in (see PROJECT_CHARTER.md Section 7).
Data rule: only public framework documentation or synthetic sample
evidence belongs anywhere under data/ (see data/sample_evidence/README.md).
