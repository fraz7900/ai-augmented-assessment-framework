# ADR-0064: A retention window for ingestion job rows

**Status:** Accepted
**Sprint:** 22
**Deciders:** Fraz Ahmed
**Related:** ADR-0059 (asynchronous ingestion, which created this table and disclosed this gap rather
than solving it), ADR-0063 (the organisation on the job row, and the reasoning about instance-wide
versus scoped that this reuses), ADR-0007 (SQLite, no migration tool, no scheduler), ADR-0056 (upload
retention, the other place this project decided how long to keep something), R-35

## Context

`ingestionjob` rows accumulate with no bound. ADR-0059 created the table and said so in its own
consequences — *"Jobs accumulate. There is no retention policy for the table yet"* — and its
alternatives section deferred the fix in these terms: a retention rule invented then would be a
guess, so revisit *"when a real corpus makes the number concrete, consistent with this project's
practice of fixing measured problems rather than hypothetical ones (R-13, R-20)."*

That deferral was right about the discipline and wrong about the trigger it named, which is why this
ADR exists now rather than after a measurement.

The measurement it was waiting for is not coming. This is a local-first, single-process deployment
that a small team uploads evidence to by hand; the number of ingestions per week is bounded by how
fast a person can find documents, and no volume threshold that would make the table's size *itself*
alarming is reachable on the deployment the charter scopes. Waiting for one is waiting forever, and
"forever" is how the row count is currently bounded.

What is available instead is an argument the volume measurement was standing in for, and it does not
depend on volume at all: **how long a job row is useful is a property of the question it answers, not
of how many rows there are.** That argument was available in Sprint 21. ADR-0059 did not make it
because it was reaching for a threshold, not because the reasoning was missing.

## The question a job row answers, and for how long

A job row has exactly two jobs in its life.

While ingestion runs, the browser polls it. That is the reason the table exists at all (ADR-0059):
the upload response no longer carries the outcome, so the row is the outcome. This use has a horizon
of minutes.

Afterwards, it answers *"what happened to that upload?"* — an operator returning to a queue, or
someone reconciling a document list against what they remember sending. This is the use that decides
retention, and its horizon is **weeks, not months**, for a reason specific to this platform: the
result is visible elsewhere either way. A successful ingestion produces a Document that appears in
the document list permanently and carries its own provenance (ADR-0039, ADR-0055). A failed one
produces nothing, and the absence is what the person is looking at. The job row adds the *reason* —
which failure category, which warning — and that detail stops being actionable once nobody is going
to retry the upload it describes.

**30 days for terminal jobs is defensible on that reasoning, and nothing longer is.** A month covers
an operator coming back from leave to a queue they left running, which is the longest realistic gap
between an upload failing and someone asking why. Beyond that the row is answering a question nobody
is still asking, about a file whose fate is already visible in the document list. A quarter would not
be wrong so much as unargued — and this file's own convention is that a number nobody has evidence
for is worse than a disclosure.

The window is a default, not a constant: `COMPLIANCE_PLATFORM_INGESTION_JOB_RETENTION_DAYS`
configures it, and **0 disables the sweep entirely**. An operator reconstructing a full upload
history for an audit should not have to patch code to stop rows being deleted; a deletion policy with
no way to turn it off is a worse default than one with an escape hatch.

## Decision

Delete terminal ingestion jobs whose `finished_at` is older than the retention window. Two
conditions carry the whole guarantee, and both are enforced in
`AssessmentRepository.delete_expired_ingestion_jobs` rather than in the service that calls it:

**Terminal only.** `SUCCEEDED` and `FAILED`. A `QUEUED` or `RUNNING` row is live work and is never
swept, however old the clock says it is. A job stranded on `RUNNING` by a crash belongs to
`fail_interrupted_ingestion_jobs`, which converts it to `FAILED` at the next startup — after which
it is dated and retention applies to it honestly. Deleting it here instead would erase an upload
that silently never happened, and afterwards nothing distinguishes that from an upload nobody ever
submitted.

**Dated only.** `finished_at IS NOT NULL`. This is redundant against today's code, since every
terminal transition sets it, and it is kept because the alternative when it is null is to fall back
to `created_at` — deleting on a timestamp that means "when the upload was accepted" rather than "when
it stopped mattering". An undateable row survives instead. Keeping a row too long is a disk-space
problem; deleting one early is not recoverable.

**When it runs.** At startup, immediately after the interrupted-job sweep, and again after each job
finishes. The ordering at startup is load-bearing: sweeping interrupted jobs first stamps each with
a `finished_at` of now, so a job stranded a year ago gets its full retention window as a readable
`FAILED` row rather than being converted and deleted in the same second. The per-job sweep is what
stops a long-lived process from growing between restarts — without it, an instance that never
restarts never sweeps, which is the deployment most likely to have the problem.

There is no scheduler, and adding one for a table this small would be a larger change than the
feature (ADR-0007 has no background-task infrastructure and this ADR does not introduce one). The
sweep is a single indexed-ish scan of a table with hundreds of rows; running it after each ingestion
costs nothing next to the parse/embed pass it follows.

**Housekeeping never costs an upload.** The sweep runs in a `finally` after every branch has
persisted its outcome, and its exceptions are logged and swallowed. Failing an ingestion the user was
waiting on in order to report that a cleanup did not run would be the wrong trade.

The sweep is instance-wide and deliberately not scoped to an organisation — the same reasoning
ADR-0063 used to leave the backpressure count unscoped. Retention is a property of the table; a
per-organisation sweep would leave every other organisation growing exactly as before.

## Consequences

- `ingestionjob` is bounded by time rather than unbounded. R-35's table half is closed.
- "Recent uploads" stops showing entries older than the window. This is the intended behaviour and
  is worth stating plainly rather than discovering: an operator who expects to scroll back three
  months will not be able to, and the document list is where that history actually lives.
- Swept rows are gone. There is no soft delete and no archive, because a retention policy whose rows
  are still on disk under another name has not retained anything less.
- The document a swept job produced is untouched, and there is no cascade from job to document —
  deliberately, and pinned by a test, so that a future relationship cannot quietly acquire one. The
  job row records that an upload happened; the Document *is* the upload.
- A job stranded by a crash now survives its first startup after that crash, which it would not have
  under a naive ordering. That is a small behavioural guarantee with a test of its own.
- 15 new tests: 7 at the repository, where the deletion happens, and 8 at the service, where the
  window and the timing do.

## The limitation, stated as plainly as ADR-0063 stated its own

**This closes one half of R-35 and not the other, and the other half is the one with a memory cost.**
Queued uploads are still held in memory until a worker frees up, bounded at
`max_pending_ingestions × max_upload_bytes` (250MB at the defaults). Nothing in this ADR changes
that. Spooling them to disk changes the queue's failure model — orphaned spool files after a crash,
which ADR-0059 weighed and rejected — rather than extending a retention sweep, so it is a different
decision and stays open and disclosed.

**The window is argued, not measured.** The reasoning above is about the purpose of a job row, and it
is honest reasoning, but it is not the volume measurement ADR-0059 asked for and it should not be
read as one. If a deployment ever does produce a corpus large enough to make the number concrete, the
number should be revisited against that evidence rather than defended on this argument.

## Alternatives considered

**Cap the row count instead of the age** — keep the most recent N jobs. Rejected: it makes retention
depend on how busy the instance is rather than on how long the information stays useful, so a busy
week silently discards the record of a failure from that same week, which is precisely when someone
is most likely to ask about it.

**Sweep on a timer.** Rejected: it needs a scheduler this process does not have, for a table whose
growth is driven entirely by ingestion — so the ingestion itself is a more accurate trigger than a
clock, and startup covers the instance that sits idle.

**Delete on the job's `created_at`.** Rejected: it dates a row by when the upload was accepted, which
for a long OCR pass can be far from when it stopped being interesting, and it is the timestamp a live
`QUEUED` row also carries — inviting exactly the deletion of live work this ADR forbids.

**Soft delete, or archive to a file.** Rejected: it keeps the rows, so it does not solve the growth
it claims to, and it adds a second place where upload history lives with no one asking for it.

**Keep deferring, per ADR-0059.** Rejected on the grounds in Context: the trigger that deferral named
is not reachable on this deployment, so deferring on it is a decision to never decide — and the
argument that was actually needed does not depend on the trigger at all.
