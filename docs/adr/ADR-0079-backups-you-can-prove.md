# ADR-0079: A checksum proves the bytes, not the backup

**Status:** Accepted
**Sprint:** 27
**Deciders:** Fraz Ahmed
**Related:** ADR-0064 (bounding a table that grew forever — the same shape, applied to a directory),
ADR-0060 (proving a record rather than trusting it), R-38

## Context

Sprint 21 built `scripts/backup.sh` and `scripts/restore.sh` and closed R-38, leaving a residual
recorded plainly: *no schedule, no rotation, and no off-machine copy.* Two of those three are
deployment questions this repository cannot answer for someone else's machine.

Reading the backup script again surfaced a sharper gap it had already half-named. It writes a SHA-256
beside every archive, with a comment explaining why: *"a backup you cannot prove is intact is a backup
you are trusting rather than verifying."*

That reasoning is right and it stops one step early. **A checksum proves the bytes have not changed
since the tarball was written.** It says nothing about whether the tarball contains a database that
opens, or a vector store the citations in it point into. A half-copied SQLite file hashes perfectly
consistently. An archive can be intact and useless, and the checksum reports it as fine — which is
the worst kind of green.

For a product whose central claim is an immutable audit record, "we have backups" that nobody has
ever opened is precisely the failure that bites at the moment it must not.

## Decision

**`scripts/verify-backup.sh` opens the archive instead of hashing it.**

It extracts to a temporary directory, checks the checksum if a sidecar exists, opens
`assessments.db` **read-only**, runs `PRAGMA integrity_check`, confirms the tables the product
depends on are present, counts what is in them, and confirms the vector store directory exists —
then deletes the extraction. Nothing is written near the live volume, and a test asserts the archive
is byte-identical afterwards.

It needs no Docker and no running stack, which is why — unlike `backup.sh` and `restore.sh`, which
`test_deployment_config.py` can only *read* — its tests actually **run** it, including against an
archive corrupted in the exact way a checksum cannot detect.

Distinctions it keeps, because collapsing them would make the answer useless:

- **A failed checksum stops everything.** If the bytes moved, nothing else the script could report
  would be trustworthy, so it does not pretend to check.
- **A missing sidecar is not a failure.** "No checksum" and "checksum failed" are different findings,
  and an archive copied without its sidecar is still worth opening.
- **Restorable-but-empty is said out loud.** A valid archive of nothing is a real outcome and not one
  to report quietly to someone checking a backup of real work.
- **A missing archive exits 2, not 1.** "You pointed me at nothing" must not read like "your backup
  is bad."

**`scripts/prune-backups.sh` bounds the directory**, which grew without limit — the same shape as the
`ingestionjob` table ADR-0064 bounded, with a worse ending when the disk fills mid-write.

It follows `restore.sh`'s posture rather than `backup.sh`'s, because deleting a backup is the second
most destructive act in this repository. **It does nothing by default**: a dry run prints exactly what
would go, and `--apply` is required. `--keep` has no default, because how many copies of an audit
record someone is willing to lose is not a decision a default should make quietly. `--keep 0` is
refused: that is not pruning. Sorting is by the UTC timestamp in the filename rather than mtime,
which survives being copied to another disk — which is exactly what an off-machine copy does.

## Consequences

- A backup can be *proved* rather than trusted, by a command that takes seconds and needs nothing
  running.
- The rotation half of R-38's residual is closed. Scheduling and off-machine copies remain open and
  remain deployment-specific.
- 17 new tests that execute the scripts, including the one that matters most: a truncated database
  whose checksum still matches, reported as unusable.

## What this does not do

**It does not schedule anything.** Where a timer lives — cron, systemd, Task Scheduler, a CI job — is
a property of the deployment, and this repository does not know which. What it can now offer is a
command worth scheduling.

**It does not make an off-machine copy.** Same reason. `prune-backups.sh` sorting by filename rather
than mtime is a small nod to it: copying archives elsewhere does not disturb their order.

**It does not verify the vector store's contents**, only that it is present. Opening LanceDB properly
would mean importing the application's own dependencies into a script that deliberately needs almost
nothing. A database that opens plus a vector store that exists is the honest limit of a cheap check,
and it catches the failure mode that actually occurs — a half-copied volume.

**It does not run automatically after a backup.** Tempting, and rejected: `backup.sh` stops the stack,
and lengthening that window to verify would trade availability for a check that can be run any time
afterwards.

## Alternatives considered

**Trust the checksum.** The status quo, and the thing this ADR is about. A hash is a statement about
bytes, not about usability.

**Do a full restore drill into a scratch volume.** The strongest possible verification, and rejected
for needing Docker, a stopped stack, and minutes rather than seconds — which means it would not be
run. A check nobody runs verifies nothing.

**Make pruning automatic inside `backup.sh`.** Rejected on ADR-0064's own reasoning about
lock-regeneration: an operation that silently deletes as a side effect of an unrelated command is how
someone loses the copy they needed. Backing up and forgetting are separate decisions.

**Default `--keep` to something sensible like 7.** Rejected. Every default here is a guess about
someone else's retention obligations, and this is the one script where being wrong is unrecoverable.
