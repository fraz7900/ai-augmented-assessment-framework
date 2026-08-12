# ADR-0055: Local OCR, PDF text normalisation, sentence-boundary chunking, a real second framework version, and chunk re-ingestion

**Status:** Accepted, live-verified — two limitations disclosed below were closed in ADR-0056 (same
sprint): originals are now retained at ingest, and the version-blind equivalence index plus CSF 1.1's
"resolves 0 equivalents" finding are both fixed. Read ADR-0056 before acting on either.
**Sprint:** 19
**Deciders:** Fraz Ahmed ("work on item 2,3,4 of tier 1 and then the whole of tier 2")
**Related:** ADR-0054 (word-boundary snapping — this ADR completes the two follow-ups it disclosed
and left undone), ADR-0053 (multi-version registry — built the mechanism and disclosed it had never
run against real data; this ADR supplies that data), ADR-0042 (`page_number`/`parser_version`
provenance and the offsets-map-back invariant every change here had to preserve), ADR-0039
(`Document` registry), ADR-0031 (framework version pinning), ADR-0013 (the
pure-Python-no-system-binary dependency precedent OCR follows), ADR-0002 (framework-as-data)

## Context

Five items, taken together because they are the disclosed-but-undone tail of Sprints 18–19 rather
than five independent features. Four came from ADRs that named them as their own limitations; the
fifth (OCR) was a charter-level scope reversal.

1. **PDF page furniture.** ADR-0054 fixed chunk *edges* and explicitly recorded that the text
   between them was still full of running headers/footers and long blank-line runs (`'Plan 9'`
   followed by ~30 newlines), calling it a `document_parsers.py` normalisation concern rather than a
   chunking one.
2. **Sentence alignment.** ADR-0054 considered it, declined it, and said why: it needs either a
   sentence tokenizer (a new dependency, poorly suited to heading fragments, table cells and bullet
   lists) or a regex that mishandles abbreviations and numbered clauses.
3. **OCR.** `PROJECT_CHARTER.md` Section 12 listed OCR as explicitly out of MVP scope, and
   `.cursor/rules/document-parsing.mdc` encoded that as a hard rule ("detect and surface as
   unsupported, never OCR"). Scanned PDFs are nevertheless ordinary real-world compliance evidence,
   which made this the largest practical gap in ingestion.
4. **Multi-version registry against real data.** ADR-0053 built version pinning, `?version=`, and
   `GET /frameworks/{name}/versions`, then disclosed two limitations: no UI reached any of it, and
   no real framework had a second version, so coexistence was proven only against a hand-built
   synthetic fixture.
5. **Chunk migration.** ADR-0054 declined to migrate existing chunks because re-chunking invalidates
   every `chunk_id` a reviewed `EvidenceLink` points at.

## Decision

### 1. PDF running headers/footers and blank runs are normalised out

`_normalise_page_texts` detects lines recurring in the *edge region* (first/last three non-blank
lines) of at least 60% of pages, across documents of at least three pages, and drops them; blank-line
runs collapse to a single blank line. Detection is digit-insensitive, so "Incident Response Plan 9"
and "…Plan 10" share one signature — without which a page-numbered footer never looks repeated.

Two guards bound the damage this can do, both of which exist because the failure mode is *deleting
real evidence*:

- Lines longer than 120 characters are never candidates. Repeated boilerplate that is genuinely long
  is content, not furniture.
- **Normalisation may never empty a page.** On a short page every line is an edge line, so a document
  whose pages legitimately repeat (a form, a signature sheet) could otherwise have whole pages
  deleted. If stripping would empty a page, nothing is stripped. This guard was added because the
  first version of the tests caught the algorithm doing exactly that.

Normalisation runs *before* `page_boundaries` are computed, from the same list that gets joined, so
ADR-0042's offsets-describe-the-stored-text invariant holds by construction.

### 2. Chunk edges snap to sentence boundaries, falling back to words

`_snap_start_to_sentence`/`_snap_end_to_sentence` are tried first; ADR-0054's word snapping is the
fallback; the bounded hard cut remains the last resort. The worst case is therefore exactly
ADR-0054's behaviour, never worse.

The regex path ADR-0054 was wary of is handled explicitly. A terminator does not end a sentence when
it is not followed by whitespace (`9.2.1`, version strings, decimals), when the preceding token
contains an internal period (`U.S.`, `e.g.`), when that token is a single letter (`J. Smith`), when
it is a listed abbreviation, or when the next non-space character is lowercase — that last rule being
the general catch for abbreviations nobody listed.

**The shift budget is derived, not chosen.** ADR-0054's no-text-lost property is
`previous.char_end >= following.char_start`, and consecutive nominal windows overlap by exactly
`chunk_overlap_chars`. The property therefore survives only while (backward end shift) + (forward
start shift) ≤ overlap. `_sentence_shift_budget` returns `min(75, overlap // 2)`, which keeps that
true for *any* configured overlap rather than only for the default 150 that ships today.

### 3. OCR for scanned PDFs, local by construction

A PDF whose text layer falls below `_MIN_CHARS_PER_PAGE` is rasterised with **pypdfium2** and read
with **rapidocr-onnxruntime**. Chosen to preserve this project's existing posture rather than for
raw accuracy: pypdfium2 bundles pdfium (no poppler, no system binary — ADR-0013's precedent),
rapidocr ships its ONNX weights *inside the wheel* (~16MB, so nothing is downloaded at runtime), and
inference runs on `onnxruntime`, already a dependency via fastembed (ADR-0008), not PyTorch. **No
code path in `services/ocr.py` can transmit anything**, which is how the Section 7 local-first
guarantee is preserved — by construction, not by configuration.

OCR-derived text gets its own `ParseStatus.SUCCESS_OCR` rather than being folded into `SUCCESS`, and
its `parser_version` names pypdfium2 and rapidocr *instead of* pypdf, because pypdf did not produce
that text and saying it did would be wrong rather than merely incomplete. `ocr_enabled` defaults on;
`ocr_max_pages` (50) bounds wall-clock and warns about what it skipped.

### 4. NIST CSF 1.1 as a real second version

`framework_mapping/nist_csf_1_1.yaml` is generated by `scripts/generate_nist_csf_1_1_yaml.py` from
two directly-fetched official sources: the CSF 1.1 Core spreadsheet (Categories/Subcategories) and
the CSF 1.1 publication (the five Function definitions, which the spreadsheet does not contain).
Counts are asserted against NIST's published totals and the generator fails loudly on disagreement:
**5 Functions, 23 Categories, 108 Subcategories**.

CSF 1.1 was chosen because it is the only candidate with *no copyright constraint* — NIST
publications are US Government works in the public domain, so full Subcategory text can be
transcribed verbatim. Every other framework's earlier version (ISO 27001, SOC 2, PCI DSS) is as
copyrighted as its current one and would have forced another titles-only compromise.

**A modelling error surfaced doing this.** The registry key was `"NIST CSF 2.0"` — a *name* with the
version baked into it, which is precisely why this framework could never hold two versions and why
ADR-0053's mechanism had nothing real to operate on. The registry now holds
`"NIST CSF": {"1.1", "2.0"}`, with `"NIST CSF 2.0"` retained as a single-version legacy alias:
`Assessment.framework_name` is stored text resolved through no alias table, so renaming the entry
would orphan every pre-existing assessment.

### 5. Re-ingestion with evidence-link remapping

`scripts/reingest_documents.py` re-chunks stored documents and **remaps** reviewed evidence links
rather than breaking them. ADR-0054's objection was correct but not permanent: chunks record
`char_start`/`char_end` (ADR-0042), so a link on an old chunk moves to the new chunk whose span
overlaps it most — a principled remap, not a guess, because edges move by at most a bounded shift.
Remapping is computed *before* the old chunks are deleted, so a failure leaves the store untouched.

## Consequences

- **PDF normalisation**: running footers no longer reach the chunker; `page_boundaries` still
  reconstruct the stored text exactly (re-asserted by test). PDF `parser_version` becomes
  `pypdf==X+cp_pdf_normalizer==N`, since this module now shapes the stored text.
- **Sentence alignment**, measured the way ADR-0054 measured its own change — across this repo's
  sample evidence plus a synthetic policy body, chunks beginning mid-sentence fell from **12 to 2**,
  with chunk counts **identical** (1, 8, 4, 11) before and after, confirming only the edges moved.
  The 2 survivors are headings and bullets with no sentence boundary within budget.
- **OCR**: verified end to end on a generated image-only PDF (no text layer at all) — recovered text,
  `SUCCESS_OCR`, correct provenance. Roughly 1.3s of one-time model load plus ~4s per page. A first
  observed characteristic, disclosed rather than hidden: wide letter-spaced headings can lose their
  spaces (`ACCESSCONTROLPOLICY`), which is one more reason OCR text is surfaced as approximate.
- **`ParseStatus.SUCCESS_OCR` forced two downstream decisions to be explicit**, which was the point
  of not reusing `SUCCESS`: `IngestionService`'s accept-gate now names both statuses, and the
  frontend's exhaustive status map failed to typecheck until OCR got its own copy — it is deliberately
  `warn`, not `ok`.
- **Real multi-version coexistence now proven on real data**, and it immediately produced the finding
  ADR-0053 said it could not test. CSF 1.1 numbers subcategories `ID.AM-1`; CSF 2.0 zero-pads to
  `ID.AM-01`. **The two versions share zero practice ids**, so a 1.1-pinned assessment resolves **0**
  cross-framework equivalents where 2.0 resolves 186. Asserted in a test rather than "fixed":
  remapping ids across versions would fabricate equivalence review no human performed, which
  `framework-mapping.mdc` forbids. Live-verified through the API: pinning to 1.1 works, omitting the
  version resolves to 2.0, an unknown version is a 422.
- **Frontend** now reaches the registry: `useFrameworkVersions`, and a `FrameworkVersionSelect` that
  renders three distinct states — a real `<select>` for a genuine choice, a plain label when only one
  version exists (a one-option dropdown would imply a decision that does not exist), and nothing at
  all for an unrecognised framework. 22 frontend tests passing (17 + 5), `tsc -b` clean.
- **Migration, run for real** against this repo's dev store: 30 documents, 24 matched to their source
  files, **276 evidence links relinked, 0 unmappable, 0 dangling afterwards**; chunk counts unchanged
  per document. A backup of the vector store and database was taken first.
- **Two structural facts the migration exposed, both disclosed rather than papered over:**
  1. **Original uploads are never retained.** Ingestion takes bytes, stores chunks, discards the
     source; `data_raw_dir` is configured but nothing writes to it. Re-ingestion is therefore
     impossible without the operator supplying the originals — **6 of 30 documents could not be
     re-ingested at all** because theirs are gone. Reconstructing a source from its own overlapping,
     individually-stripped chunks was rejected: it would be a lossy fabrication stored under a
     content_hash that never existed.
  2. **27 of 30 stored documents have no `Document` registry row**, predating ADR-0039. The tool
     drives from the vector store for that reason, and matches documents to sources by chunk content
     rather than filename.
- `VectorRepository.document_ids()` added for the migration, documented as an O(total corpus) scan
  that must stay off request paths — the exact cost ADR-0033 removed from `chunks_for_document`.
- **Not live-verified:** the `libgl1`/`libglib2.0-0` addition to `backend.Dockerfile` (opencv, pulled
  in by rapidocr, links against them at import and `python:3.12-slim` ships neither). Docker is not
  available in this environment, so this is statically reasoned only — the same disclosure ADR-0017
  made before Docker Desktop was installed.

## Alternatives considered

**Sentence tokenizer (nltk/spacy/pysbd) instead of a regex.** Rejected on ADR-0054's own reasoning:
a heavy dependency trained on prose, for text that is mostly headings, numbered clauses and table
cells. The explicit abbreviation/numbered-clause rules here are testable and cost nothing.

**Let the sentence shift be a tunable constant.** Rejected. A constant larger than `overlap // 2`
silently breaks the no-text-lost property for any non-default overlap. Deriving it from the overlap
makes that class of bug unrepresentable.

**Fold OCR results into `ParseStatus.SUCCESS`.** Smallest diff, no downstream changes. Rejected
precisely *because* it required no downstream changes: approximate text would have become
indistinguishable from a real text layer at every layer above the parser, including in citations a
reviewer quotes.

**`opencv-python-headless` instead of system libs in the image.** Rejected: rapidocr declares
`opencv-python` by name, so the headless distribution would be installed *alongside* it, putting two
providers of the same `cv2` module in one environment.

**Rename `"NIST CSF 2.0"` to `"NIST CSF"` outright.** Cleaner registry. Rejected: it orphans every
existing assessment, whose `framework_name` is stored text.

**Remap practice ids between CSF 1.1 and 2.0 so a 1.1 assessment gets equivalents.** Rejected as
fabrication — cross-framework equivalence in this project is human-reviewed by rule, and a
mechanical `ID.AM-1 → ID.AM-01` mapping would assert review that never happened. 1.1 and 2.0 are also
not merely renumbered; 2.0 adds the Govern function.

**Reconstruct lost originals from stored chunks to re-ingest all 30 documents.** Rejected — see
Consequences; a fabricated source is worse than an honestly unmigrated document.
