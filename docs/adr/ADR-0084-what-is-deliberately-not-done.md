# ADR-0084: What is deliberately not done, in one place

**Status:** Accepted
**Sprint:** 30
**Deciders:** Fraz Ahmed
**Related:** every ADR, and `docs/product/risk_register.md`

## Context

This project's habit is to disclose rather than hide: 83 ADRs and 40 register rows record what was
built, what was refused, and why. That habit has a cost nobody notices while it accumulates — **the
limits are now spread across 83 documents.** Someone deciding whether to rely on this platform has to
read all of them to learn what it does not do, and a limitation that takes an hour to find is not
meaningfully disclosed.

This document does not decide anything new. It consolidates, and it sorts the open items into three
kinds that a reader keeps conflating:

- **Scope decisions** — deliberately out, recorded in the charter. Not gaps.
- **Blocked** — cannot be closed here, for a stated structural reason.
- **Open and honest** — could be closed, has not been, and the cost of that is real.

## Scope decisions: deliberately out

**Authentication, RBAC, per-user permissions, cloud deployment.** `PROJECT_CHARTER.md` Section 12,
partially reversed once and only once: Sprint 22 reopened it for the *data-model* half, giving
assessments and documents an owning organisation (ADR-0063). Identity stayed where ADR-0061 left it —
a username asserted by the reverse proxy. The consequence is R-40 and it is stated everywhere it
matters: **client separation is enforced by the product, not against a caller that bypasses it.**

**A generative reasoner.** Asked and refused four separate times (ADR-0011, 0014, 0020, 0036).
Mapping is retrieval-only, permanently, and that is what makes R-1 — "AI hallucinates a compliance
claim" — closeable at all. Every proposal's citation is a literal retrieved chunk.

**Score-change notification.** R-34: a score already reported to a stakeholder can legitimately drop,
and nothing tells the holder. The register says to revisit only if this platform gains point-in-time
or recurring reporting. It has not, so building a notifier would be inventing the requirement in
order to satisfy it. ADR-0077 addressed the reachable half — a report can be *asked* whether it is
still current.

**Disk-spooling the upload queue.** Considered and rejected twice (ADR-0059, ADR-0064): it trades a
bounded memory commitment for an unbounded cleanup problem — orphaned spool files after a crash.

## Blocked: cannot be closed in this repository

**Retrieval precision beyond 0.0305.** Measured, not estimated (ADR-0071, 0072, 0073). What remains
is a practice whose genuinely best chunk is genuinely its best chunk and still wrong — R-16's
ceiling, which no threshold separates, since a *confirmed* false positive sits at 0.71 inside the
0.65–0.78 band correct pairs were measured in.

Closing it needs a labelled corpus of real evidence, and **real evidence cannot enter this
repository** — it is public and frequently cloud-synced (`docs/testing-with-real-documents.md`). That
is a deliberate constraint, not an oversight, and it means the measurement has to be built on the
machine that owns the documents and produce a number that stays there.

**Complete framework transcription for three frameworks.** ISO 27001 (titles only), SOC 2 and PCI DSS
(requirement statements only). Copyright, checked per framework against the source document rather
than assumed. Disclosed per framework rather than worked around.

**An off-machine backup copy.** Depends entirely on where this is deployed. ADR-0083 got as close as
this repository honestly can: one command worth scheduling, sorting by a timestamp that survives
being copied elsewhere.

## Open and honest: could be closed, has not been

**27 of 30 stored documents predate the registry** and carry no `content_hash`; **6 of 30 predate
upload retention** and can never be re-ingested; **assessments finalized before ADR-0060 carry no
seal** and report `unsealed`. All three are consequences of features arriving after data existed, and
none is retroactively fixable without fabricating a record — which is the one thing this project will
not do.

**Existing chunks are not migrated when chunking improves.** Re-chunking invalidates the `chunk_id`s
reviewed evidence points at, so re-ingestion is an explicit operator action rather than a silent
upgrade.

**No reviewer has used this at volume for a sustained period.** Sprint 23's queue work came from one
tester's report and was measurably right. Everything since has reasoned from fixtures.
`/aqs/agreement` (ADR-0070) exists to turn real review decisions into data and **nothing has fed it
yet** — which is the single largest gap between what this platform has measured and what it claims.

**The frontend test runner loses files on this filesystem.** Measured repeatedly, environmental rather
than a code property, and `scripts/doctor.sh` can detect the incomplete-install case but not the flaky
one. CI is the authority (ADR-0075).

## The one thing this document is for

Every item above appears somewhere else in more detail. What this adds is the sorting — because the
three kinds are not equivalent, and a reader who cannot tell a scope decision from an unfixed defect
will either distrust the whole thing or trust the wrong part of it.

If any single line here is the one to read: **the platform's conclusions are traceable, and its
retrieval is not accurate.** Human review is what stands between those two facts, which is why it is
structural rather than advisory — and why every feature that touches the review queue has been built
to make a reviewer's judgement cheaper rather than to replace it.
