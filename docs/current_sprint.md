Current sprint: Sprint 27 — finish telling reviewers where text came from, and make a backup provable
Objective: two independent tranches, both closing residuals this project has carried and disclosed
rather than hidden. R-33's last surface: the evidence review queue, the one screen where a reviewer
DECIDES about a proposal, still showed nothing about whether its text was recognised or read (T1).
And R-38's residual: backups exist and are checksummed, but a checksum proves the bytes, not that the
archive contains a database that opens (T2). No new frameworks, no auth, no scheduling — where a
timer lives is a deployment question this repository cannot answer for someone else's machine.
Status: **T1 and T2 are on PR #29.**
Sprint 26 closed with both tranches merged: `3d93d62` the OCR warning reaching the exports (ADR-0076)
and `d3004d5` an export that can be asked whether it is still true (ADR-0077).
T1 — provenance in the review queue (ADR-0078, accepted). R-33 has now been narrowed three times, and
this surface was left for last, which is worth stating rather than glossing. Chat is where a reviewer
READS evidence; the dashboard and exports are where they REPORT it. The queue is where they DECIDE,
and a reviewer accepting a proposal quoted from an OCR'd page had no way to know the wording was
approximate at the moment the decision was recorded.
T1, the shape. `GET /assessments/{id}/evidence` now returns `EvidenceLinkView`: every field of the
stored link plus a resolved `text_provenance`. A view rather than a column, because provenance is
computed from the vector store at read time and storing it on the row would duplicate a fact the
chunk already owns and let the two disagree. Flat rather than nested so callers read it exactly as
before — the cost of that is drift, so a test asserts the view covers every stored field and that
`text_provenance` is the only addition. Resolved in bulk, one read per cited document, because the
queue is the screen most likely to hold hundreds of rows and therefore the worst place for a per-row
lookup. Provenance survives filtering (ADR-0065), tested directly: a field present only on the
unfiltered call would be missing exactly when a reviewer had narrowed to the rows they mean to act on.
T2 — backups you can prove (ADR-0079, accepted). Sprint 21 closed R-38 and recorded the residual
plainly: no schedule, no rotation, no off-machine copy. Reading `backup.sh` again surfaced a sharper
gap it had already half-named. It writes a SHA-256 and explains why — "a backup you cannot prove is
intact is a backup you are trusting rather than verifying" — and that reasoning stops one step early.
A checksum proves the BYTES have not changed. It says nothing about whether the tarball contains a
database that opens. A half-copied SQLite file hashes perfectly consistently, so the archive is
reported as fine, which is the worst kind of green.
T2, what it does. `scripts/verify-backup.sh` opens the archive instead of hashing it: extracts to a
temp directory, checks the sidecar if present, opens `assessments.db` READ-ONLY, runs
`PRAGMA integrity_check`, confirms the tables the product depends on, counts what is in them,
confirms the vector store exists, and deletes the extraction. It needs no Docker and no running
stack — which is why, unlike `backup.sh` and `restore.sh` that `test_deployment_config.py` can only
read, its tests actually RUN it, including against a database truncated so its checksum still
matches. Four distinctions it keeps: a failed checksum stops everything, a missing sidecar is not a
failure, restorable-but-empty is said out loud, and a missing archive exits 2 rather than 1 so
"you pointed me at nothing" cannot read as "your backup is bad".
T2, rotation. `scripts/prune-backups.sh` bounds a directory that grew forever — the same shape as the
ingestionjob table ADR-0064 bounded, with a worse ending when the disk fills mid-write. It follows
`restore.sh`'s posture rather than `backup.sh`'s, because deleting a backup is the second most
destructive act in this repository: it does nothing by default, `--apply` is required, `--keep` has
no default because how many copies of an audit record you are willing to lose is not a decision a
default should make, and `--keep 0` is refused. Sorting is by the UTC timestamp in the filename
rather than mtime, which survives being copied to another disk — which is what an off-machine copy
does.
What Sprint 27 does not do. Scheduling and off-machine copies stay open and stay deployment-specific;
what this offers is a command worth scheduling. `verify-backup.sh` confirms the vector store is
present but does not open it, because doing so properly would mean importing the application's own
dependencies into a script that deliberately needs almost nothing — a database that opens plus a
vector store that exists is the honest limit of a cheap check, and it catches the failure that
actually occurs. And R-33 stays open: OCR output is still approximate, which was never a defect to
fix, only an uncertainty to make visible.
Still open and not claimed here, unchanged. R-9 is narrowed but interpreters still come from the
machine and nothing is hash-pinned. R-34, a score already reported to a stakeholder can change with
no way to tell them — and R-34's own entry says revisit push notification only if this platform gains
point-in-time or recurring reporting, which it has not. R-40, client separation is enforced by the
product and not against a caller that bypasses it. R-35's in-memory upload queue. The
copyright-limited transcriptions R-28/R-30/R-32. R-16's precision ceiling, measured and partly
reduced but not closed, and the labelled real corpus that would take it further — which by policy
cannot live in this repository at all.
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
