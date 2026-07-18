"""Unit tests for VectorRepository (Sprint 9). No dedicated test file
existed for this repository before — it was only exercised indirectly
through ingestion/assessment integration tests, which meant its own
input-validation and "table not created yet" branches had no direct
coverage. Uses a real LanceDB store at tmp_path (per
repositories/README.md's boundary: services/ never imports lancedb
directly, but a repository test legitimately exercises the real
dependency it wraps, not a fake of it).
"""

from __future__ import annotations

from pathlib import Path

from compliance_platform.models.schemas import ChunkingStrategy, EvidenceChunk
from compliance_platform.repositories.vector_repository import VectorRepository

_DIMENSIONS = 4


def _repo(tmp_path: Path) -> VectorRepository:
    return VectorRepository(tmp_path / "lancedb", _DIMENSIONS)


def _chunk(chunk_id: str, document_id: str, text: str = "chunk text") -> EvidenceChunk:
    return EvidenceChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        chunk_index=0,
        text=text,
        chunking_strategy=ChunkingStrategy.FIXED_WINDOW,
        char_start=0,
        char_end=len(text),
    )


def test_count_is_zero_before_any_table_exists(tmp_path: Path) -> None:
    assert _repo(tmp_path).count() == 0


def test_search_returns_empty_before_any_table_exists(tmp_path: Path) -> None:
    assert _repo(tmp_path).search([0.0] * _DIMENSIONS) == []


def test_search_within_documents_returns_empty_before_any_table_exists(tmp_path: Path) -> None:
    assert _repo(tmp_path).search_within_documents([0.0] * _DIMENSIONS, ["doc-1"]) == []


def test_search_within_documents_returns_empty_with_no_document_ids(tmp_path: Path) -> None:
    """Distinct from the no-table-yet case above: a table exists (a
    chunk was added), but the caller passed an empty document_ids list.
    """
    repo = _repo(tmp_path)
    repo.add_chunks([_chunk("c1", "doc-1")], [[0.0] * _DIMENSIONS])
    assert repo.search_within_documents([0.0] * _DIMENSIONS, []) == []


def test_add_chunks_rejects_mismatched_chunks_and_vectors_length(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    try:
        repo.add_chunks([_chunk("c1", "doc-1")], [])
        raise AssertionError("expected ValueError for mismatched lengths")
    except ValueError as exc:
        assert "must be the same length" in str(exc)


def test_add_chunks_with_empty_list_is_a_no_op(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.add_chunks([], [])
    assert repo.count() == 0


def test_add_and_search_round_trip(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.add_chunks(
        [_chunk("c1", "doc-1", text="alpha"), _chunk("c2", "doc-2", text="beta")],
        [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]],
    )
    assert repo.count() == 2

    results = repo.search([1.0, 0.0, 0.0, 0.0], limit=1)
    assert len(results) == 1
    assert results[0]["chunk_id"] == "c1"
    assert results[0]["text"] == "alpha"
    assert "_distance" in results[0]


def test_chunks_for_document_filters_by_document_id(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.add_chunks(
        [_chunk("c1", "doc-1"), _chunk("c2", "doc-2")],
        [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]],
    )
    doc_1_chunks = repo.chunks_for_document("doc-1")
    assert [c["chunk_id"] for c in doc_1_chunks] == ["c1"]
    assert "vector" not in doc_1_chunks[0]  # citation fields only, never the raw vector


def test_search_within_documents_excludes_other_documents(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.add_chunks(
        [_chunk("c1", "doc-1"), _chunk("c2", "doc-2")],
        [[1.0, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]],  # identical vectors on purpose
    )
    results = repo.search_within_documents([1.0, 0.0, 0.0, 0.0], ["doc-1"])
    assert [r["chunk_id"] for r in results] == ["c1"]
