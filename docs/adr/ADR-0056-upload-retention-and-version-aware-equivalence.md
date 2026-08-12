# ADR-0056: Retain original uploads, and make cross-framework equivalence version-aware

**Status:** Accepted, live-verified
**Sprint:** 19 (follow-up to ADR-0055, project-owner directive: "work on 1 and 2 worth my attention")
**Deciders:** Fraz Ahmed
**Related:** ADR-0055 (surfaced both of these as its own disclosed limitations), ADR-0054 (declined to
migrate stored chunks — the reason retention matters), ADR-0053 (multi-version registry; disclosed
the version-blind equivalence index as an untested risk), ADR-0042 (`content_hash`, `parser_version`),
ADR-0039 (`Document` registry), ADR-0019/0023–0029 (every prior equivalence pairing, all produced by
this project's own similarity-then-human-review process)

## Context

ADR-0055 closed a set of disclosed follow-ups and, in doing so, produced two findings it recorded as
limitations rather than fixing. Both are addressed here.

1. **Originals were never retained.** `IngestionService.ingest()` took bytes, stored chunks, and
   discarded the source. `Settings.data_raw_dir` existed and pointed at `data/raw/`, but nothing ever
   wrote to it. This only became visible when re-ingestion tooling was built: correcting chunks
   produced by an older chunker requires re-chunking, re-chunking requires the document, and the
   document was gone. **6 of the 30 documents in this repo's own store are permanently
   un-re-ingestible** for exactly that reason.
2. **Equivalence resolution was version-blind.** `_build_practice_text_index` indexed each
   framework's *latest* version only. ADR-0053 disclosed the risk; ADR-0055 made it real by adding
   NIST CSF 1.1 alongside 2.0. The two versions share **no** practice ids (`ID.AM-1` vs `ID.AM-01`),
   so a 1.1-pinned assessment resolved **0** cross-framework equivalents against 2.0's 186. ADR-0055
   asserted that in a test rather than fixing it, on the grounds that mechanically remapping ids
   across versions would fabricate equivalence review no human performed.

## Decision

### 1. Ingestion retains the original upload

`services/original_store.py` writes each upload to
`<data_raw_dir>/<document_id>__<sanitised filename>`. The document-id prefix makes lookup exact; the
filename suffix keeps the directory legible to an operator. Filenames are sanitised as a **security
boundary, not tidiness** — `filename` arrives from an upload, and `../../etc/passwd` must not escape
the directory.

**The write happens after the `Document` registry write succeeds**, which is the one ordering
decision here that matters. Writing earlier would leave a stray file on every failure path above it,
including ADR-0046's compensating-delete path, which has no way to know a file had been written. By
that point nothing remains that can fail and orphan it.

**A failed retention write is logged and swallowed, not raised.** The document is fully ingested and
usable at that point, and losing the ability to re-ingest it later must not turn a successful upload
into a failed one. It is not silent either: `scripts/reingest_documents.py` reports every document
lacking a retained original.

`retain_original_uploads` defaults to true and can be turned off for a deployment unwilling to keep a
second copy of every upload, at the cost of re-ingestion depending on the operator still holding the
originals.

Re-ingestion now prefers the retained original, keyed by document id — no content matching, so
nothing can be matched wrongly — and **verifies it against `Document.content_hash` before rebuilding
anything from it**, refusing rather than proceeding if it does not match. The ADR-0055 content-matched
`--source-dir` fallback remains, for documents ingested before retention existed.

### 2. The practice-text index covers every version, keyed by each file's own declared name

Two things were wrong, and only fixing both works. The index covered latest-only, *and* it was keyed
by this registry's key for a framework rather than the name the YAML file declares for itself.

Keying by the declared name is what makes indexing every version safe rather than ambiguous: each
version declares a distinct name (`NIST CSF 1.1` vs `NIST CSF 2.0`), so two versions cannot collide,
and equivalence entries — which already reference frameworks by exactly that declared name — keep
resolving unchanged for every single-version framework. Verified: C2M2 153, NERC CIP 481, CIS
Controls 84, SOC 2 60, PCI DSS 61, ISO 27001 95 — all identical to before.

### 3. CSF 1.1 gets real equivalents from NIST's own published crosswalk

A version-aware index alone would still have left 1.1 with nothing to resolve, because no equivalence
entry referenced it. Rather than remap ids, the mapping is **transcribed from NIST**: every CSF 2.0
Subcategory in NIST's CSF 2.0 Reference Tool export carries Informative References naming the CSF 1.1
Subcategories it derives from (`CSF v1.1: ID.BE-2, ID.BE-3`).

This is the only pairing in `cross_framework_equivalence.yaml` not produced by this project's own
similarity-then-review process, and it is *stronger* provenance, not weaker: it is the mapping
published by the standard's own author. `framework-mapping.mdc` forbids equivalence "inferred by
embedding similarity alone" — transcribing an authoritative crosswalk is the opposite of inference.
Every rationale cites NIST rather than paraphrasing a judgment nobody made. Similarity is still
computed with this project's own embedder because the file's schema carries it and its header
requires real scores, but it is disclosed context, not the basis for acceptance.

## Consequences

- **155 entries added**, covering **106 of 108** CSF 1.1 subcategories. A 1.1-pinned assessment now
  resolves 155 equivalents where it resolved 0; CSF 2.0 goes 186 → 341 (it gains the reverse
  direction). Whole-file total 560 → 715.
- Coverage is partial *because NIST's own mapping is partial*: only 90 of 106 CSF 2.0 subcategories
  cite a 1.1 predecessor, since concepts new in 2.0 (most of GOVERN) have none. That is a real
  property of the standards, not a gap in transcription.
- **One reference dropped, with its reason stated**: NIST cites `PR.DS` — a *Category*, not a
  Subcategory — as a source for `ID.AM-08`. A category is not a Practice in this schema, so there is
  no practice-to-practice equivalence to record. Dropped rather than "resolved" by inventing a leaf.
- Re-ingestion no longer requires the operator to supply anything for documents ingested after this
  change. Verified end to end in an isolated store: ingest → original retained → `reingest_documents.py`
  with **no** `--source-dir` located it by document id. The corruption guard was verified by tampering
  with a retained file, which was refused even under `--apply`.
- `data/raw/` is now written by the application, not just by developers. `privacy-protection.mdc` was
  updated to say so explicitly. No new class of exposure: the same content already persists as chunk
  text under `data/processed/`, and nothing in this path transmits anything.
- **The 6 pre-existing un-re-ingestible documents stay un-re-ingestible.** Retention is not
  retroactive and nothing can make it so. This fixes the problem going forward only, which is stated
  here rather than left for someone to discover.
- 12 new backend tests: 7 in `test_original_store.py` (round-trip, retention disabled, nothing
  retained, the path-traversal guard, filename collision between two documents, hash agreement with
  the parser's own `_content_hash`, delete), 3 in `test_ingestion_service.py` (retained on ingest,
  not retained when disabled, and a rejected upload leaving nothing behind), and a net 2 in
  `test_framework_loader.py`, where the test asserting "a pinned older version resolves no
  equivalents" was replaced by tests asserting that it now does and that latest still does.
  Full suite **449 passed** (was 437), ruff clean.

## Alternatives considered

**Store originals in SQLite as a BLOB alongside the `Document` row.** Genuinely tempting: it makes
retention transactional with the registry write, removing the ordering question entirely. Rejected on
size — uploads are bounded at 25MB each, and a SQLite file holding every upload becomes the backup,
copy, and vacuum problem for a store whose other rows are tiny. The filesystem is the right place for
file-shaped data; the ordering question is answered in three lines of comment instead.

**Raise on a failed retention write.** Rejected: it converts a fully successful ingestion into a
failure over a maintenance convenience. The document is already chunked, embedded, and linkable.

**Record retention status on the `Document` row.** Rejected as redundant — the path is derivable from
the document id, and a boolean column could disagree with the filesystem, which is worse than having
no column at all.

**Make the index version-aware by adding a `version` field to every equivalence entry.** The obvious
schema change. Rejected as unnecessary: each version's YAML already declares a unique name, and
entries already reference frameworks by that name, so the version distinction was *already expressible*
— the index simply was not reading it. Adding a field would have required editing all 560 existing
entries to say something they already implied.

**Mechanically remap `ID.AM-1 → ID.AM-01` to give 1.1 the 2.0 equivalents.** Rejected in ADR-0055 and
still rejected: it asserts human review that never happened, and the versions are not merely
renumbered — 2.0 adds the GOVERN function, and several 2.0 subcategories draw on multiple 1.1
predecessors (156 references across 90 subcategories, not a 1:1 correspondence).

**Leave 1.1 with no equivalents and keep the limitation documented.** The status quo ADR-0055 shipped.
Rejected once it was established that an authoritative published crosswalk exists — the limitation was
only defensible while the alternative was fabrication.
