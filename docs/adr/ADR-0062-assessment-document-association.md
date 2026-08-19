# ADR-0062: Documents belong to assessments through an association, not by ownership

**Status:** Accepted
**Sprint:** 21
**Deciders:** Fraz Ahmed
**Related:** ADR-0039 (the document registry, and the 27 of 30 documents that predate it), ADR-0019
(cross-framework equivalence — why one document must serve several assessments), ADR-0011
(`propose_mappings`, whose implicit association this replaces), ADR-0050 (supersession flagging),
ADR-0061 (attribution, recorded on the association), ADR-0007 (SQLite, no migration tool)

## Context

`Document` had no `assessment_id` while eight other tables did. The Evidence tab's chooser called
`GET /documents`, which lists every document on the instance, so a reviewer picking evidence for one
organisation's assessment was shown another organisation's policies — and could link them, because
nothing downstream objected.

An association already existed, undeclared. `propose_mappings` computed "documents associated with
this assessment" as `{link.document_id for link in evidence_links}` and searched only those. That
derivation was invisible to the UI, and could not express a document attached but not yet cited —
which is the state a reviewer is in *before* the mapping engine has run. Proposing mappings over a
freshly uploaded document was therefore impossible until they had already linked it by hand, which
is the wrong way round.

## Decision

1. **A many-to-many `AssessmentDocument` table** (`assessment_id`, `document_id`, `attached_at`,
   `attached_by`), unique on the pair. `Document` gains no `assessment_id`.
2. **`GET /assessments/{id}/documents`** returns the attached documents; the Evidence chooser uses it.
   `GET /documents` still lists everything and is what the attach flow browses.
3. **`POST /assessments/{id}/documents`** attaches, idempotently, refusing a document that was never
   ingested. **`DELETE /assessments/{id}/documents/{document_id}`** detaches.
4. **Linking evidence attaches implicitly.** Citing a document from an assessment says it belongs to
   it.
5. **Detaching is refused while any evidence link still cites the document** (409).
6. **`propose_mappings` searches attached documents**, not just cited ones.
7. **Existing evidence links are backfilled into associations** at repository construction, in raw
   SQL.
8. **Attach and detach go through the finalized-write guard** (ADR-0060), so a frozen assessment's
   document set cannot change.

## Rationale

**Why not simply give `Document` an `assessment_id`.** One policy PDF legitimately serves several
assessments of the same organisation — a C2M2 assessment and a NIST CSF one over the same evidence
corpus is the cross-framework workflow this product is built around (ADR-0019). Ownership would force
the same file to be uploaded, parsed, chunked and embedded once per framework, would make
`content_hash` (ADR-0039) report duplicates that are not mistakes, and would quietly punish the
workflow the product exists to support. The relation is genuinely many-to-many, and this repo's own
backlog has called it "assessment-document association" for several sprints.

**What this does and does not achieve, stated plainly.** It stops one assessment's chooser from
offering another's documents, and makes "which documents does this assessment rest on" a real
question with a real answer. It is **not** multi-tenancy: the attach flow still browses every
document on the instance, so a determined user can still pull one organisation's document into
another's assessment. Actual client separation needs a tenant concept, which is charter "Won't (for
MVP)" scope. Calling this change client separation would overstate it.

**Why attaching is idempotent.** Linking evidence attaches implicitly, so a reviewer who attaches
first and links second — the sensible order — would otherwise hit a conflict for doing things the
right way round.

**Why detaching is refused while citations exist.** It would leave an evidence link pointing at a
document the assessment no longer claims: a dangling reference, which is exactly what the core
invariant ("no score exists without a linked evidence trail") exists to prevent. Rejecting or
removing the links first is an explicit, recorded act; a silent cascade would not be.

**Why detaching never deletes the document.** The same file may be attached to other assessments, and
ingestion is expensive enough that discarding it as a side effect of tidying one assessment would be
a poor trade. Document deletion remains deliberately unbuilt.

**Why the backfill is raw SQL.** A migration must not depend on the *current* ORM mapping being able
to deserialize *old* rows — and this one would not: a pre-ADR-0030 database holds `evidencelink` rows
whose `source` today's `EvidenceSource` enum refuses to load, so reading them through SQLModel raises
on exactly the databases the backfill exists to rescue. It needs two opaque id columns; raw SQL reads
them without opinions. This was found by an existing test, not by inspection.

**Why backfill at all.** Every (assessment, document) pair on an evidence link *is* an association by
definition, so inserting them records what the data already said. Without it, every existing
assessment would open with an empty document list and appear to have lost its evidence.

**Why an association whose document has no registry row is skipped in the list but kept in the ids.**
27 of 30 documents in the original corpus predate ADR-0039 and have no `Document` row, while their
evidence links are perfectly valid. The chooser skips them — a placeholder in a list whose whole job
is recognisability helps nobody — but `attached_document_ids` returns them, because the mapping
engine searches the vector store, which knows nothing about the registry.

**Why attachments are not in the sealed payload.** ADR-0060 seals what a finalized assessment
*claims*: its evidence links, findings and history. An attachment is a working-set fact, not a claim,
and every cited document already appears in the sealed links. Sealing it would have forced payload
version 3 for no gain in what the seal attests. Attach and detach are blocked on a finalized
assessment regardless.

## Consequences

- The Evidence chooser shows only this assessment's documents. Uploading a document no longer makes
  it appear in every assessment on the instance.
- `propose_mappings` can now run over an attached-but-uncited document, which is the ordinary case
  after an upload. This is a behaviour change: previously it silently searched nothing until a manual
  link existed.
- One new table and a backfill that runs once per engine construction and is a no-op afterwards.
- The attach control browses all documents, so cross-organisation attachment remains possible by
  hand. Disclosed in the risk register rather than implied to be solved.
- Detaching a cited document is a 409 the UI has to handle. The Evidence tab offers detach beside the
  document picker, acting on the current selection, and shows the server's refusal verbatim — it
  names the citation count and what to do about it, which is more use than anything the client could
  say instead. No confirmation dialog: detaching is fully reversible via the attach control, and the
  genuinely destructive case is the one the server already refuses.

## Alternatives considered

**`Document.assessment_id`, one document one assessment.** Rejected — see Rationale. It breaks the
cross-framework workflow and duplicates ingestion work per framework.

**Keep deriving the association from evidence links.** Rejected: it cannot express attached-but-not-
yet-cited, which is the state that makes the mapping engine useful right after an upload.

**Scope documents by organisation instead.** This is what the underlying problem actually calls for,
and it is deferred: an organisation concept is multi-tenancy, explicitly "Won't (for MVP)". The
association is the part that can be built honestly now without pretending to deliver tenancy.

**Cascade-detach, removing citing evidence links automatically.** Rejected: silently deleting a
reviewer's recorded decisions to make a tidy-up succeed is the opposite of this project's discipline
around explicit human review.

**Seal the attachment set (payload version 3).** Rejected — see Rationale.
