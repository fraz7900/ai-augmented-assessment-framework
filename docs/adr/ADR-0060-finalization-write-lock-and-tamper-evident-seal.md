# ADR-0060: Enforce the finalized-assessment lock where the write happens, and seal the record so alteration is detectable

**Status:** Accepted
**Sprint:** 21
**Deciders:** Fraz Ahmed
**Closes:** R-12 in `docs/product/risk_register.md`, open since Sprint 2
**Related:** ADR-0058 (the finalization gate that rests on this enforcement), ADR-0030
(`PracticeFinding` and its append-only history), ADR-0007 (SQLite via SQLModel; no migration tool),
ADR-0011 (the R-18 fix establishing `rowid` as this repository's authority on insertion order),
ADR-0039 (`Document.content_hash` — the existing hashing precedent), ADR-0013 (PDF/XLSX exports, and
their `Generated:` staleness signal), ADR-0032 (sanitized-export approval), ADR-0015 (centralized
exception→HTTP mapping)

## Context

R-12 has read, since Sprint 2: *"nothing outside `AssessmentService` currently prevents a
hypothetical direct-repository call from bypassing the finalized-assessment evidence lock."* It was
carried honestly through eighteen sprints on the reasoning that no code path did this. ADR-0058's
finalization gate has since been built on top of that same single layer of enforcement, so the entry
stopped describing a hypothetical and started describing the foundation.

Investigating it found **a second defect the entry had never named, on the sanctioned path rather
than around it**:

```python
assessment = self.get_assessment(assessment_id)      # session A - opened, read, closed
if assessment.status == AssessmentStatus.FINALIZED:
    raise AssessmentFinalizedError(assessment_id)
...
created = self._assessments.add_evidence_link(link)  # session B - a separate transaction
```

An assessment finalized between those two moments was written to anyway. That is R-11's
check-then-act bug class, landing on the one guarantee meant to be absolute.

And a third thing, which no amount of application-layer locking addresses: `assessments.db` is a
SQLite file. The `sqlite3` CLI rewrites a finding in it without leaving a trace. To an auditor,
*"our code will not do that"* is a weaker claim than *"here is how you check that nothing did"* — and
the second is what a compliance record is supposed to support.

## Decision

### Prevention

1. **`AssessmentRepository._assert_writable`** re-reads the assessment's status **inside the
   transaction that performs the write**, on the five write methods `AssessmentService` already
   guards: `add_evidence_link`, `update_evidence_link_review`, `set_practice_finding`,
   `create_evidence_request`, `resolve_evidence_request`.
2. **`update_status` is excluded** — it must be able to reach `FINALIZED`, and the state machine
   already makes that state terminal. **`create_sanitization_approval` is excluded** because the
   service does not block it either: approving a sanitized export adds no claim to the record.
3. **The service checks stay.** They produce the 409 before any work is done and can name the refused
   operation. Reaching the repository check means a caller skipped the service, so it logs at error
   level.
4. **A missing assessment is not an error here** — there is no lock to enforce on a record that does
   not exist, and the service raises `AssessmentNotFoundError` long before this point.
5. **`AssessmentFinalizedError` moves to `core/errors.py`** so the repository can raise it without
   importing from `services/`; the service re-exports it.

### Detection

6. **`services/audit_seal.py`** canonicalises the whole record — assessment, evidence links, practice
   findings, both append-only history trails, evidence requests — into one SHA-256, written to
   `Assessment.sealed_digest` at finalization alongside `sealed_at` and `seal_version`.
7. **`GET /assessments/{id}/verify`** recomputes the digest from the current database and returns
   `verified` / `altered` / `unsealed` / `unverifiable`, with both digests.
8. **The seal is printed into every PDF and XLSX export** and carried on
   `DashboardReport.situation.finalization_seal`.
9. **`store_finalization_seal` refuses to overwrite an existing seal.**
10. **Assessments finalized before this existed report `unsealed`** and are not sealed retroactively.

## Rationale

**Why the check moved into the write's transaction, not merely into a second place.** It closes the
check-then-act window as well as the bypass. On SQLite's default rollback journal the shared lock
taken by the in-transaction read is held until the write commits, so a concurrent finalize cannot land
in between. This was **verified, not assumed**: `journal_mode=delete` on the real database, and no
WAL or `isolation_level` configuration anywhere in the codebase.

**Why not `BEGIN IMMEDIATE`.** Given the above it would only convert a possible lock-upgrade
`SQLITE_BUSY` into a clean wait. It is a defensible robustness change on its own merits, but it alters
transaction handling for every write in the application, and bundling it here would mean shipping a
broad behavioural change under a narrow justification.

**Why the guarded set is derived from the service, not chosen.** Two layers enforcing subtly
different rules is worse than one, and the service's existing checks are the specification. That is
precisely why `create_sanitization_approval` is absent — sharing a finished assessment externally is
a normal thing to do with one.

**Why detection at all, given prevention.** Prevention is application code. It does not survive a text
editor. Detection is what changes the claim the product can make.

**Why one digest and not a per-row hash chain.** A chain would additionally localise *where* a
pre-finalization history was altered. The claim being defended is about the finalized record, which
one digest covers completely — and a chain is a second mechanism to keep correct on every single
write, forever, for localisation nobody has asked for.

**Why the seal is printed into exports.** A digest stored beside the record it protects proves nothing
against someone who edits the record and recomputes the digest over the edited version. It becomes
evidence only once a copy exists outside the database, and this product already hands people copies. A
reader holding last quarter's PDF can compare its printed seal against `/verify` today. No notary, no
network, nothing in tension with local-first.

**Why four verification states and not a boolean.** "No seal exists" and "the seal does not match" are
opposite situations, and a boolean collapses both into the same `false`. An unsealed record is
unverified, which is not the same as untrustworthy. A seal written by a build that knows a payload
shape this one does not is `unverifiable`, not `altered`: the record may be perfectly intact and this
build simply cannot say. `/verify` returns **200 for every outcome including `altered`**, because a
detected alteration is this endpoint working, not failing.

**Three canonicalisation decisions, each of which would otherwise have shipped a feature that lies.**

- *Timestamps are normalised to UTC, written without an offset, at fixed microsecond precision.* The
  models default to timezone-aware UTC; SQLite stores no offset. Sealing from in-memory objects and
  verifying from the database would otherwise disagree about a record nobody touched. **A false
  "altered" is worse than no seal at all**, because the one time it matters, nobody will believe it.
- *`Assessment.updated_at` and the seal columns are excluded from the payload.* Storing the seal
  updates the row; including either would mean no seal could ever verify against the record it sealed.
- *Fields are listed explicitly per seal version, never dumped from the models, and the version in
  force is stored beside the digest.* Adding a column later must not invalidate every seal ever
  written.

Collections with no inherent order (links, findings, requests) are sorted by id so a query-plan change
cannot alter the digest; the two history lists keep `rowid` order, because for an append-only trail
the order **is** part of what is being attested (ADR-0011).

**Why a seal is written once and never replaced.** A record that can be re-sealed is one where an edit
can be covered up by recomputing the digest over the edited version, leaving the seal looking valid
and meaning nothing.

**Why no retroactive sealing.** A seal written today over a record that may already have been altered
would attest only that it has not changed since today, while looking like it attested to something
more.

## Consequences

- R-12 is closed after eighteen sprints, with one residual disclosed in the register: the mechanism's
  strength depends on a copy of the seal existing outside the database.
- ADR-0058's finalization gate now rests on enforcement that holds for callers that never reach the
  service.
- Finalization does slightly more work — one extra read of the record and a hash — on an operation
  that happens once per assessment.
- Every export gained a line. The PDF prints it in 7pt Courier under the header; the XLSX adds a
  Situation row. Both appear only once an assessment is finalized.
- Three new nullable columns on `assessment`, added through the existing `_add_missing_columns` helper
  (ADR-0007 has no migration tool by design), so an existing local database picks them up on next
  start.
- Sealed records are not portable across a canonicalisation change unless the old version's builder is
  kept. That is the explicit contract of `seal_version`, and old builders must not be deleted.
- **No frontend surface yet.** Nothing displays the seal or offers a verify action; the mechanism is
  reachable via the API and the exports only.

## Alternatives considered

**SQLite triggers (`BEFORE INSERT ... RAISE(ABORT)`).** Rejected as the primary answer. They enforce
below every Python path, which is genuinely attractive — but they can be dropped as easily as added,
so they are not tamper-evidence either; they are invisible to anyone reading the Python; ADR-0007
keeps the schema deliberately plain; and they would need re-expressing on the PostgreSQL path R-18
contemplates. Prevention in the repository plus detection by seal covers the same ground more
honestly.

**Per-row hash chain over the history tables.** Rejected — see Rationale. Revisit only if localisation
inside a pre-finalization history is ever actually asked for.

**Sign the seal with a private key rather than hashing.** Rejected for this deployment: a signing key
stored on the same single trusted machine as the database is available to anyone who can edit the
database, so it adds ceremony rather than assurance. Revisit if this product ever gains an operator
identity distinct from the machine — it would pair naturally with per-actor attribution, which this
audit trail also still lacks.

**Publish the seal to an external notary or timestamping service.** Rejected: it would be the first
network call in the assessment path, against the charter's local-first constraint (Section 7), for a
guarantee the printed-in-exports approach already approximates at zero cost.

**Seal every status transition, not just finalization.** Rejected as scope without a claim behind it.
A draft assessment is expected to change; the record that must be defensible is the finalized one.
