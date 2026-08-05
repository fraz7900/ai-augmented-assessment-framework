"""Chunking and metadata tagging for ingested documents.

Implements the chunking strategy required by the data-cleaning skill:
prefer structure-aware chunking when the source has structural markup
(headings), fall back to fixed-window chunking otherwise, and always
retain enough metadata (char offsets, section reference) to satisfy the
evidence-extraction skill's citation requirement downstream.
"""

from __future__ import annotations

import re
import uuid

from compliance_platform.core.config import Settings
from compliance_platform.models.schemas import ChunkingStrategy, EvidenceChunk

# services/document_parsers.py injects "# Heading" lines for DOCX heading
# styles; plain text and PDF extraction generally do not produce this
# markup, which is exactly the structure-aware-vs-fixed-window signal.
_HEADING_RE = re.compile(r"^# (.+)$", re.MULTILINE)


def _has_structural_markup(text: str) -> bool:
    return bool(_HEADING_RE.search(text))


# How far a window edge may move to land on whitespace. A cut is only
# worth shifting if the word it splits is nearby; beyond this the text
# has no usable boundary (a long URL, a base64 blob, an unspaced table
# row) and the hard cut is kept rather than distorting the window size.
_MAX_BOUNDARY_SHIFT_CHARS = 40


def _snap_start_to_word(text: str, pos: int) -> int:
    """Move `pos` forward to the start of the next whole word, so a chunk
    never opens mid-word. The skipped characters are not lost: they belong
    to the preceding window, which now ends on that same word boundary.
    """
    if pos <= 0 or pos >= len(text):
        return pos
    if text[pos - 1].isspace():
        return pos  # already sitting at the start of a word

    limit = min(pos + _MAX_BOUNDARY_SHIFT_CHARS, len(text))
    cursor = pos
    while cursor < limit and not text[cursor].isspace():
        cursor += 1
    if cursor >= limit:
        return pos  # no boundary within budget -- keep the hard cut
    while cursor < len(text) and text[cursor].isspace():
        cursor += 1
    return cursor


def _snap_end_to_word(text: str, pos: int) -> int:
    """Move `pos` backward to the end of the previous whole word, so a
    chunk never closes mid-word. Never called with pos == len(text) as a
    shift candidate: the end of the document is already a clean boundary.
    """
    if pos <= 0 or pos >= len(text):
        return pos
    if text[pos].isspace() or text[pos - 1].isspace():
        return pos  # already sitting at the end of a word

    limit = max(pos - _MAX_BOUNDARY_SHIFT_CHARS, 0)
    cursor = pos
    while cursor > limit and not text[cursor - 1].isspace():
        cursor -= 1
    if cursor <= limit:
        return pos  # no boundary within budget -- keep the hard cut
    return cursor


def _fixed_window_chunks(
    text: str, target_chars: int, overlap_chars: int, min_chars: int
) -> list[tuple[str, int, int]]:
    """Return (chunk_text, char_start, char_end) tuples via a sliding window
    over `text`. Offsets are relative to `text`, not necessarily the whole
    document — callers that pass a section substring must add the
    section's own offset back in (see _structure_aware_chunks).

    Both edges of each emitted window are snapped to the nearest word
    boundary. A raw character window splits words at both ends ("esponse
    Plan 9", "…a limited numb"), which costs little in retrieval but a
    great deal in citation credibility: these chunks are quoted verbatim
    to a reviewer verifying a gap (ADR-0051 renders them on the
    Dashboard), and a quotation that begins mid-word reads as a bug in
    the evidence rather than an artifact of chunking.

    The *nominal* grid (`start`, and therefore `step`, iteration count,
    and termination) is deliberately left unsnapped — only the emitted
    offsets move. Advancing by a snapped position instead would let
    rounding accumulate across a long document and drift the effective
    overlap away from the configured value.
    """
    chunks: list[tuple[str, int, int]] = []
    if not text.strip():
        return chunks

    step = max(target_chars - overlap_chars, 1)
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + target_chars, text_len)

        snapped_start = _snap_start_to_word(text, start)
        snapped_end = _snap_end_to_word(text, end)
        if snapped_end <= snapped_start:
            # Degenerate: a single unbroken token longer than the window
            # swallowed both edges. Emit the hard cut rather than nothing.
            snapped_start, snapped_end = start, end

        chunk_text = text[snapped_start:snapped_end].strip()
        if len(chunk_text) >= min_chars:
            chunks.append((chunk_text, snapped_start, snapped_end))
        if end == text_len:
            break
        start += step
    return chunks


def _structure_aware_chunks(
    text: str, target_chars: int, overlap_chars: int, min_chars: int
) -> list[tuple[str, int, int, str | None]]:
    """Split by '# Heading' markers, then fixed-window chunk within each
    section so a single long section doesn't become one oversized chunk.
    Returns (chunk_text, char_start, char_end, heading) tuples.
    """
    matches = list(_HEADING_RE.finditer(text))
    sections: list[tuple[str | None, int, int]] = []  # (heading, start, end)

    if not matches or matches[0].start() > 0:
        preamble_end = matches[0].start() if matches else len(text)
        if text[:preamble_end].strip():
            sections.append((None, 0, preamble_end))

    for i, match in enumerate(matches):
        section_start = match.start()
        section_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((match.group(1).strip(), section_start, section_end))

    results: list[tuple[str, int, int, str | None]] = []
    for heading, start, end in sections:
        section_text = text[start:end]
        for chunk_text, rel_start, rel_end in _fixed_window_chunks(
            section_text, target_chars, overlap_chars, min_chars
        ):
            results.append((chunk_text, start + rel_start, start + rel_end, heading))
    return results


def _page_number_for_offset(
    page_boundaries: list[tuple[int, int]] | None, char_start: int
) -> int | None:
    """1-indexed page number for a chunk starting at char_start, or None
    if page_boundaries wasn't supplied (every non-PDF format) or the
    offset falls outside every known boundary (defensive; shouldn't
    happen given page_boundaries always spans the full parsed text).
    A chunk spanning a page break (fixed-window chunking doesn't respect
    page boundaries) is attributed to its starting page only -- see
    models/schemas.py EvidenceChunk.page_number's docstring.
    """
    if not page_boundaries:
        return None
    for page_index, (start, end) in enumerate(page_boundaries, start=1):
        if start <= char_start < end:
            return page_index
    return None


def _row_info_for_offset(
    row_boundaries: list[tuple[int, int, int, str | None]] | None,
    char_start: int,
    char_end: int,
) -> tuple[int | None, str | None]:
    """(row_number, sheet_name) for the FIRST row a chunk (char_start,
    char_end) actually overlaps -- deliberately not "the row containing
    char_start" the way _page_number_for_offset works for pages. XLSX/CSV
    chunks commonly start on a "# Sheet Name" heading line (structure-aware
    chunking's own section boundaries include the heading), which sits
    BEFORE any row's own (start, end) range -- matching char_start alone
    would report row_number=None for most sheets' opening chunk despite it
    plainly containing real row data. Overlap-matching instead picks up
    the first row the chunk's range genuinely reaches into. row_boundaries
    entries are built in increasing char order (document_parsers.py), so
    the first overlap found is the first row in document order, not an
    arbitrary one. None, None if row_boundaries wasn't supplied (every
    non-tabular format) or the chunk's range contains no row at all
    (shouldn't happen given every section has at least one row -- parse_xlsx
    skips sheets with zero rendered rows entirely).
    """
    if not row_boundaries:
        return None, None
    for row_start, row_end, row_number, sheet_name in row_boundaries:
        if row_start < char_end and row_end > char_start:
            return row_number, sheet_name
    return None, None


def chunk_document(
    document_id: str,
    text: str,
    settings: Settings,
    page_boundaries: list[tuple[int, int]] | None = None,
    row_boundaries: list[tuple[int, int, int, str | None]] | None = None,
) -> list[EvidenceChunk]:
    """Chunk a parsed document's raw text into EvidenceChunks.

    The strategy actually used is recorded on every resulting chunk
    (chunking_strategy field), so downstream consumers and debugging can
    always tell which path produced a given chunk rather than assuming.
    page_boundaries (Sprint 18, ADR-0042), when supplied (PDF only),
    tags every chunk with the page it starts on. row_boundaries (Sprint
    18, ADR-0052), when supplied (XLSX/CSV only), tags every chunk with
    the first spreadsheet row (and, for XLSX, sheet) it actually contains.
    """
    if _has_structural_markup(text):
        raw_chunks = _structure_aware_chunks(
            text,
            settings.chunk_target_chars,
            settings.chunk_overlap_chars,
            settings.chunk_min_chars,
        )
        chunks = []
        for idx, (chunk_text, start, end, heading) in enumerate(raw_chunks):
            row_number, sheet_name = _row_info_for_offset(row_boundaries, start, end)
            chunks.append(
                EvidenceChunk(
                    chunk_id=str(uuid.uuid4()),
                    document_id=document_id,
                    chunk_index=idx,
                    text=chunk_text,
                    chunking_strategy=ChunkingStrategy.STRUCTURE_AWARE,
                    section_reference=heading,
                    char_start=start,
                    char_end=end,
                    page_number=_page_number_for_offset(page_boundaries, start),
                    row_number=row_number,
                    sheet_name=sheet_name,
                )
            )
        return chunks

    raw_chunks = _fixed_window_chunks(
        text, settings.chunk_target_chars, settings.chunk_overlap_chars, settings.chunk_min_chars
    )
    chunks = []
    for idx, (chunk_text, start, end) in enumerate(raw_chunks):
        row_number, sheet_name = _row_info_for_offset(row_boundaries, start, end)
        chunks.append(
            EvidenceChunk(
                chunk_id=str(uuid.uuid4()),
                document_id=document_id,
                chunk_index=idx,
                text=chunk_text,
                chunking_strategy=ChunkingStrategy.FIXED_WINDOW,
                section_reference=None,
                char_start=start,
                char_end=end,
                page_number=_page_number_for_offset(page_boundaries, start),
                row_number=row_number,
                sheet_name=sheet_name,
            )
        )
    return chunks
