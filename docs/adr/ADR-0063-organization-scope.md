# ADR-0063: An organization owns assessments and documents

**Status:** Accepted
**Sprint:** 22
**Deciders:** Fraz Ahmed
**Related:** ADR-0062 (the association this completes, and which named this decision as deferred),
ADR-0039 (the document registry, and the 27 of 30 documents that predate it), ADR-0060 (the
finalization seal, now at payload version 3, and the in-transaction guard this copies), ADR-0061
(attribution, and the perimeter assumption this shares), ADR-0059 (asynchronous ingestion, whose job
queue is scoped for reading but not for capacity), ADR-0007 (SQLite, no migration tool),
PROJECT_CHARTER.md Section 12

## Context

R-39, open since Sprint 21 and the only entry in the register carrying High impact: scoping documents
to assessments narrowed the evidence chooser but separated nothing. The attach flow still called
`GET /documents`, which listed every document on the instance, so one organisation's policy could be
attached to another organisation's assessment deliberately. ADR-0062 said so itself, and named this
decision as the deferred one: *"Scope documents by organisation instead. This is what the underlying
problem actually calls for, and it is deferred: an organisation concept is multi-tenancy, explicitly
'Won't (for MVP)'."*

That charter line has now been reopened, narrowly, by direct project-owner instruction — the same way
Section 12's OCR exclusion was reopened in Sprint 19. What is reopened is the **data-model half**:
assessments and documents gain an owner, enforced server-side. The identity half — authentication,
RBAC, per-user permissions, cloud deployment — stays exactly where it was, unbuilt and out of scope.

## Decision

1. **An `Organization` table** (`id`, unique `name`, `created_at`). `Assessment.organization_id` and
   `Document.organization_id` are non-null foreign keys, set at creation and never reassignable.
2. **Omitting the organisation is allowed only while exactly one exists.** `resolve_organization_id`
   supplies the single organisation when one is not named, and raises `OrganizationRequired` (400)
   once a second exists. It is not a default.
3. **Every list a person reads is scoped**: `GET /documents`, `GET /assessments`, `GET /ingest/jobs`.
   `list_documents` and `list_assessments` have no unscoped form at the repository at all.
4. **Cross-organisation attach is refused twice** — in `AssessmentService` before any work is done
   (409), and again in `AssessmentRepository._assert_same_organization`, re-reading both rows inside
   the transaction that performs the attach, logging at error level.
5. **`organization_id` joins the seal payload at version 3.** A finalized assessment cannot be moved
   between organisations without the seal reporting it.
6. **`GET/POST /organizations` and `PATCH /organizations/{id}`** — create, list, rename. No delete, no
   merge, no reassignment.
7. **A migration bootstraps one organisation and carries every existing row onto it**, in one
   `ALTER TABLE ... ADD COLUMN organization_id TEXT NOT NULL DEFAULT 'org_default'` per table.

## Rationale

**Why `Document` gains an `organization_id` when ADR-0062 refused it an `assessment_id`.** This looks
like a reversal and is not. ADR-0062's argument was about *frameworks*: one policy PDF serves a C2M2
assessment and a NIST CSF one over the same corpus, so owning it by one assessment would force the
same file to be parsed, chunked and embedded once per framework. That argument is silent about
clients — and ADR-0062's own docstring says "several assessments **of the same organisation**". A
document serves many assessments; it belongs to exactly one client. Single-owner here and
many-to-many there are the same decision seen from two angles.

**Why omission is conditional rather than a default.** A default organisation would make the
dangerous case silent: two clients on one instance, a reviewer who forgets to choose, and one
client's work filed under another — which is R-39 restated. With exactly one organisation there is
exactly one honest answer, so omission is not a guess; with two there is no honest answer, so it is
an error. This is the reasoning ADR-0059 applied to upload size, where the boundary case is where
being wrong costs most, and it is why the rule is a condition rather than a number nobody can see.

**Why the repository checks the boundary again, inside the write's own transaction.** Exactly the two
reasons ADR-0060 gave for the finalization lock. It closes the check-then-act window between the
service's read and the repository's write (R-11's bug class), and it applies to callers that never
went through the service at all. R-39 is a confidentiality risk, so it gets the same treatment the
audit-immutability guarantee got rather than a weaker one. The service check stays because it is what
produces a 409 before any work happens; the repository check logs at error level because a backstop
that fires silently stops being a backstop.

**Why the seal moves to version 3, when ADR-0062 declined to spend a version on attachments.**
ADR-0062 was right: an attachment is a working-set fact, not a claim the assessment makes. Whose
record it is *is* a claim, and the most consequential one on the page — a finalized assessment quietly
moved to another organisation would misattribute an entire audit record. Attachments still do not
ride along, even though version 3 is now being spent anyway, because the reason to exclude them was
never the cost of a version bump. ADR-0060's per-version field lists make this ordinary: version 2
seals keep verifying under version 2 rules, and a version 3 seal read by a build that knows only
version 2 reports `unverifiable`, never `altered`.

**Why the seal covers the organisation's id and not its name.** So renaming stays a label change. An
instance that starts as "Unassigned" and is later given its real client's name must not thereby
invalidate every seal it holds.

**Why the migration adds the column and the value in one statement.** SQLite permits `NOT NULL` with a
default on `ADD COLUMN`, so there is no window in which the column exists holding NULLs that the model
refuses to load. It follows the existing `_add_missing_columns` helper rather than introducing a
second migration mechanism (ADR-0007 has no Alembic).

**Why a fresh database also gets an organisation.** So the single-organisation deployment the charter
scopes works without anyone having to create something first, and so rule 2 has something to resolve
to.

**Why a document with no registry row is still attachable.** 27 of 30 documents in the original corpus
predate ADR-0039 and have no `Document` row to carry an organisation. Refusing them would break real,
valid assessments in order to enforce a boundary the data cannot express. The honest fix is a registry
backfill, which is not this sprint; the gap is disclosed here and as R-40 rather than closed by a
guess.

**Why the ingestion queue is scoped for reading but not for capacity.** "Recent uploads" is a list a
person reads, and one client's filenames are not another's to see. The backpressure count behind it
still counts every pending job on the instance, because the queue is a machine-wide resource — scoping
that count would give each organisation the full queue depth and the bound would mean nothing.

## Consequences

- The attach flow can no longer reach another organisation's documents. R-39 is **narrowed, not
  closed** — see the limitation below and R-40.
- Every existing install migrates onto one organisation named "Unassigned", renameable.
- Assessments and documents cannot be moved between organisations at all. For a single-organisation
  install this is invisible; for an install that has already mixed two clients it means the mixing is
  permanent and the records must be re-created to separate them.
- Seal payload version 3. Assessments sealed at version 2 keep verifying under version 2.
- `GET /assessments` and `GET /documents` gain an `organization_id` query parameter, and answer 400
  rather than guessing once a second organisation exists.

## The limitation, stated as plainly as ADR-0062 stated its own

**This is not multi-tenancy and does not pretend to be.** There is still no authentication. Anything
able to reach the API directly can pass any `organization_id` and read any organisation's data — the
same perimeter assumption ADR-0061's attribution already rests on, and the same reason the deployment
stack must not be exposed to a network. What this removes is the ability to cross the boundary
*through the product*, which is the scenario R-39 actually describes and the one a reviewer can reach
by accident. Recorded as R-40 rather than left implicit.

## Alternatives considered

**Require `organization_id` on every call, with no resolution rule.** Rejected: it would have churned
roughly 140 existing call sites to no benefit for the single-organisation deployment the charter
scopes, while the conditional rule refuses exactly the case that is actually dangerous.

**A default organisation that new records fall into silently.** Rejected — see Rationale. It makes the
multi-client failure quiet, which is the failure this ADR exists to make loud.

**Enforce the boundary only in the service.** Rejected for the reasons ADR-0060 already established;
a single layer of enforcement is what R-12 spent eighteen sprints disclosing.

**Deleting or merging organisations.** Deliberately unbuilt. An organisation owns assessments,
documents and seals, and what happens to those is a data-loss decision that deserves its own ADR.

**Backfilling existing rows into more than one organisation by guessing.** Rejected: nothing in the
data distinguishes two clients' documents, and a guess would produce a separation that looks real and
is not — worse than the honest statement that the migration separates nothing retroactively.

**Authentication in the same sprint.** Out of scope, and deliberately so: the charter line was
reopened for the data model only. Whether identity follows is a separate decision.
