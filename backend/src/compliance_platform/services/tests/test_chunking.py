from __future__ import annotations

from compliance_platform.core.config import Settings
from compliance_platform.models.schemas import ChunkingStrategy
from compliance_platform.services import chunking


def _settings(**overrides: object) -> Settings:
    return Settings(**overrides)  # type: ignore[arg-type]


def test_fixed_window_chunking_used_when_no_headings() -> None:
    text = "Sentence one. " * 200  # long enough to require multiple windows
    settings = _settings(chunk_target_chars=200, chunk_overlap_chars=20, chunk_min_chars=10)
    chunks = chunking.chunk_document("doc-1", text, settings)
    assert len(chunks) > 1
    assert all(c.chunking_strategy == ChunkingStrategy.FIXED_WINDOW for c in chunks)
    assert all(c.section_reference is None for c in chunks)


def test_structure_aware_chunking_used_when_headings_present() -> None:
    text = "# First Section\nSome body text.\n# Second Section\nMore body text."
    settings = _settings(chunk_target_chars=1000, chunk_overlap_chars=50, chunk_min_chars=5)
    chunks = chunking.chunk_document("doc-2", text, settings)
    assert all(c.chunking_strategy == ChunkingStrategy.STRUCTURE_AWARE for c in chunks)
    headings = {c.section_reference for c in chunks}
    assert "First Section" in headings
    assert "Second Section" in headings


def test_chunk_offsets_map_back_into_original_text() -> None:
    text = "# Heading\nExact body text to verify offsets."
    settings = _settings(chunk_target_chars=1000, chunk_overlap_chars=0, chunk_min_chars=5)
    chunks = chunking.chunk_document("doc-3", text, settings)
    assert chunks
    for chunk in chunks:
        substring = text[chunk.char_start : chunk.char_end]
        assert chunk.text == substring.strip()


def test_short_fragments_below_min_chars_are_dropped() -> None:
    text = "hi"
    settings = _settings(chunk_target_chars=1000, chunk_overlap_chars=0, chunk_min_chars=50)
    chunks = chunking.chunk_document("doc-4", text, settings)
    assert chunks == []


def test_chunk_ids_are_unique_within_a_document() -> None:
    text = "Sentence one. " * 200
    settings = _settings(chunk_target_chars=200, chunk_overlap_chars=20, chunk_min_chars=10)
    chunks = chunking.chunk_document("doc-5", text, settings)
    assert len({c.chunk_id for c in chunks}) == len(chunks)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


# --- page_number (Sprint 18, ADR-0042) ---


def test_page_number_is_none_when_no_page_boundaries_supplied() -> None:
    text = "Sentence one. " * 20
    settings = _settings(chunk_target_chars=1000, chunk_overlap_chars=0, chunk_min_chars=10)
    chunks = chunking.chunk_document("doc-6", text, settings)
    assert all(c.page_number is None for c in chunks)


def test_page_number_tags_each_chunk_with_its_starting_page() -> None:
    page_one = "First page content. " * 5
    page_two = "Second page content. " * 5
    text = page_one + page_two
    page_boundaries = [(0, len(page_one)), (len(page_one), len(text))]
    # Small enough that each ~105-char page becomes its own chunk,
    # rather than both landing in one chunk together (the spans-a-page-
    # boundary case the next test covers).
    settings = _settings(chunk_target_chars=110, chunk_overlap_chars=0, chunk_min_chars=10)

    chunks = chunking.chunk_document("doc-7", text, settings, page_boundaries=page_boundaries)
    assert len(chunks) == 2
    assert chunks[0].page_number == 1
    assert chunks[1].page_number == 2


def test_page_number_uses_a_chunks_starting_offset_when_it_spans_a_page_boundary() -> None:
    # Fixed-window chunking doesn't respect page boundaries -- a chunk
    # that starts on page 1 and runs into page 2's text is still
    # attributed to page 1 (its starting page), a disclosed
    # simplification, not full multi-page provenance.
    page_one = "A" * 50
    page_two = "B" * 50
    text = page_one + page_two
    page_boundaries = [(0, 50), (50, 100)]
    settings = _settings(chunk_target_chars=70, chunk_overlap_chars=0, chunk_min_chars=10)

    chunks = chunking.chunk_document("doc-8", text, settings, page_boundaries=page_boundaries)
    first_chunk = chunks[0]
    assert first_chunk.char_start < 50 < first_chunk.char_end  # genuinely spans the page break
    assert first_chunk.page_number == 1
