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
