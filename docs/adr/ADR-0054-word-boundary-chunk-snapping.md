# ADR-0054: Snap fixed-window chunk edges to word boundaries

**Status:** Accepted, live-verified
**Sprint:** 19
**Deciders:** Fraz Ahmed ("fix the chunker")
**Related:** ADR-0051 (Dashboard citation rendering — the surface where this defect was visible to a
reviewer), ADR-0042 (`page_number` — chunk `char_start` as citation provenance, the invariant this
ADR had to preserve), ADR-0011 (mapping engine — the retrieval path chunks feed)

## Context

`_fixed_window_chunks` slid a pure character window over the parsed text: `text[start:end].strip()`,
with `start` advancing by `target_chars - overlap_chars`. Nothing aligned those edges to anything in
the text, so a window boundary landed wherever the character count happened to fall — almost always
inside a word.

Structure-aware chunking only engages when `# Heading` markers are present, which
`document_parsers.py` injects for DOCX heading styles and for XLSX/CSV sheet names. PDF and plain-text
extraction produce no such markup, so **PDF — the dominant real evidence format — always took the
fixed-window path**, and therefore always split words.

Measured across four real policy PDFs ingested during Sprint 19 API testing, 140 of 148 chunks began
or ended mid-word. Chunks were quoted back verbatim in exactly the places that matter most:

```
'ms \nthat support the operation and assets of the State…'   (syste|ms)
'ther designated agency officials at the senior…'            (o|ther)
'rocess, store, receive, transmit or otherwise…'             (p|rocess)
'esponse Plan 9'                                             (R|esponse)
```

The retrieval cost of this is mild — a partial leading token adds some noise to an embedding but
rarely changes ranking. The citation cost is not mild. ADR-0051 renders these chunks on the Dashboard
as the evidence a reviewer reads when verifying a gap, and `chat_service.py` returns them as the
literal answer text (ADR-0014: "the 'answer' IS the literal, already human-reviewed evidence text").
A quotation that opens mid-word reads as corrupted evidence, undermining the credibility of the one
feature whose entire value is that it quotes source material rather than generating it.

## Decision

Both edges of every emitted fixed-window chunk are snapped to the nearest word boundary, by two
helpers in `chunking.py`:

- `_snap_start_to_word(text, pos)` — moves `pos` **forward** to the start of the next whole word.
- `_snap_end_to_word(text, pos)` — moves `pos` **backward** to the end of the previous whole word.

Three constraints shape the implementation:

1. **The offsets move, not just the text.** `char_start`/`char_end` are citation provenance
   (ADR-0042) and `test_chunk_offsets_map_back_into_original_text` asserts
   `chunk.text == text[char_start:char_end].strip()`. Trimming only the rendered text would have
   silently broken that contract, leaving offsets pointing at a range that no longer matches what was
   quoted. The snapped positions are what gets recorded.

2. **The nominal grid stays unsnapped.** Iteration still advances `start += step` from the
   *unshifted* position; only the emitted offsets move. See Rationale #2.

3. **The shift is bounded, with a hard-cut fallback.** An edge moves at most
   `_MAX_BOUNDARY_SHIFT_CHARS` (40). Beyond that the text has no usable boundary and the raw cut is
   kept. See Rationale #3.

A guard covers the degenerate case where snapping inverts the window (`snapped_end <= snapped_start`,
reachable when a single token longer than the whole window swallows both edges): the hard cut is
emitted rather than dropping the chunk.

Structure-aware chunking inherits the fix for free — `_structure_aware_chunks` fixed-window-chunks
*within* each section, so both paths now produce word-aligned edges.

## Rationale

**1. Why snap the start forward but the end backward.** The two directions are chosen so consecutive
windows still meet: window N's end moves back to a boundary, and window N+1's start moves forward past
that same partial word. Characters skipped by the forward-snapped start are not lost — they belong to
the previous window, which now terminates cleanly on that word. A test
(`test_snapping_does_not_lose_text_between_consecutive_chunks`) asserts
`previous.char_end >= following.char_start` holds across a long document, which is what makes "no text
is lost" a checked property rather than an argument.

**2. Why the iteration grid is deliberately not snapped.** The obvious implementation advances from
the snapped end (`start = snapped_end - overlap`). That compounds: each window's shift feeds the next
window's position, so across a long document the effective overlap drifts away from the configured
`chunk_overlap_chars` by an unbounded, text-dependent amount, and chunk counts stop being a function
of document length. Keeping the nominal grid fixed makes the snap a purely local, bounded adjustment —
iteration count, termination, and overlap semantics are provably identical to before. This is why
re-ingesting all eight Sprint 19 test documents produced **identical chunk counts** (1156, 50, 45, 32,
21, 20, 9, 6), which is the cheapest possible confirmation that only the edges moved.

**3. Why a bounded shift rather than always finding a boundary.** Real evidence contains long
unbroken tokens: URLs, base64 blobs, unspaced table rows. An unbounded search would let a single such
token drag a window edge arbitrarily far, distorting window size to satisfy a cosmetic property. The
40-char budget keeps the adjustment proportionate to `chunk_target_chars=1200` (≤3.3%), and the
fallback means a pathological input degrades to exactly today's behaviour rather than to something
worse.

**4. Why not sentence boundaries instead.** Sentence-aware splitting is the natural next question, and
it was not attempted here. It needs either a sentence tokenizer (a new dependency, and a poor fit for
the heading-fragment, table-cell, and bullet-list text that dominates policy PDFs) or a regex that
mishandles abbreviations and numbered clauses — both materially larger changes than the defect
warranted. Word alignment fixes the visible credibility problem; sentence alignment is a separate,
optional refinement and is disclosed here as not-done rather than silently skipped.

## Consequences

- Chunks no longer open or close mid-word on any path. Across the four Sprint 19 policy PDFs,
  mid-word boundaries fell from **140 to 2**; both survivors are the intended hard-cut fallback firing
  inside URLs with no whitespace within budget.
- Chunk counts, iteration behaviour, and overlap semantics are unchanged, verified by identical counts
  across all eight re-ingested documents.
- `char_start`/`char_end` remain a faithful citation range — the offsets-map-back invariant is
  re-asserted under snapping by a dedicated test.
- **Existing chunks are not migrated.** Unlike ADR-0052, which back-filled new columns onto
  pre-existing vector stores via `add_columns`, there is no in-place fix here: the chunk *text and
  offsets themselves* differ, so correcting a stored chunk means re-chunking and re-embedding its
  document. Documents ingested before this change keep their old boundaries until re-ingested. This is
  a disclosed limitation, not a silent one.
- A separate, pre-existing defect became more visible while verifying this one: PDF extraction emits
  page-footer fragments followed by long runs of blank lines (`'Plan 9'` plus ~30 newlines). Those
  chunks are now word-aligned but remain low-value. Not addressed here — it is a
  `document_parsers.py` text-normalisation concern, not a chunking one.
- 5 new tests in `test_chunking.py` (17 total); full backend suite 408 passed; ruff clean (ADR-0049
  gate).

## Alternatives considered

**Trim the rendered text, leave offsets alone.** Smallest possible diff, and it would have made the
quoted text look right. Rejected: it desynchronises `chunk.text` from `text[char_start:char_end]`,
breaking the invariant ADR-0042's provenance work depends on. A citation whose recorded range doesn't
reproduce the quoted text is worse than a citation that starts mid-word — it is wrong rather than
merely ugly.

**Advance the window from the snapped end.** Simpler-looking loop. Rejected for the overlap-drift
reason in Rationale #2.

**Make `_MAX_BOUNDARY_SHIFT_CHARS` a `Settings` field.** Consistent with `chunk_target_chars` and
friends. Rejected as over-configuration: it is an implementation detail of the snap with no meaningful
tuning story for an operator, and the codebase already keeps comparable internals as module constants
(`_HEADING_RE` here, `_MIN_CHARS_PER_PAGE` in `document_parsers.py`).

**Re-ingest existing documents automatically on upgrade.** Rejected as out of scope and destructive:
re-chunking every stored document would invalidate every `chunk_id` that existing evidence links
point at, silently breaking reviewed citations. Re-ingestion is left as an explicit operator action.
