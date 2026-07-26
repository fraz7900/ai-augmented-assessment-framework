"""Unit tests for VectorRepository (Sprint 9). No dedicated test file
existed for this repository before — it was only exercised indirectly
through ingestion/assessment integration tests, which meant its own
input-validation and "table not created yet" branches had no direct
coverage. Uses a real LanceDB store at tmp_path (per
repositories/README.md's boundary: services/ never imports lancedb
directly, but a repository test legitimately exercises the real
dependency it wraps, not a fake of it).

The staleness/concurrency tests below (ADR-0037) exist because caching
the read-path table handle is only safe if a cached handle reliably
reflects writes made through a *different* handle (add_chunks's
_ensure_table() is deliberately not cached) — a real risk confirmed by
isolated testing before the fix shipped, not assumed away.
"""

from __future__ import annotations

import threading
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


def test_count_reflects_writes_made_after_the_read_cache_was_already_populated(
    tmp_path: Path,
) -> None:
    """The staleness risk ADR-0033/ADR-0037 name directly: a cached read
    handle must not keep reporting the count as of whenever it was first
    opened, once a *later* write happens through add_chunks's separate,
    deliberately-uncached handle.
    """
    repo = _repo(tmp_path)
    repo.add_chunks([_chunk("c1", "doc-1")], [[1.0, 0.0, 0.0, 0.0]])
    assert repo.count() == 1  # populates the cached handle

    repo.add_chunks([_chunk("c2", "doc-2")], [[0.0, 1.0, 0.0, 0.0]])
    assert repo.count() == 2  # must not be stuck at the cached-at-open-time value of 1


def test_chunks_for_document_reflects_a_document_added_after_the_cache_was_populated(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    repo.add_chunks([_chunk("c1", "doc-1")], [[1.0, 0.0, 0.0, 0.0]])
    assert repo.chunks_for_document("doc-2") == []  # populates the cached handle

    repo.add_chunks([_chunk("c2", "doc-2")], [[0.0, 1.0, 0.0, 0.0]])
    assert [c["chunk_id"] for c in repo.chunks_for_document("doc-2")] == ["c2"]


def test_search_within_documents_reflects_a_document_added_after_the_cache_was_populated(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    repo.add_chunks([_chunk("c1", "doc-1")], [[1.0, 0.0, 0.0, 0.0]])
    repo.search_within_documents([1.0, 0.0, 0.0, 0.0], ["doc-2"])  # populates the cached handle

    repo.add_chunks([_chunk("c2", "doc-2")], [[1.0, 0.0, 0.0, 0.0]])
    results = repo.search_within_documents([1.0, 0.0, 0.0, 0.0], ["doc-2"])
    assert [r["chunk_id"] for r in results] == ["c2"]


def test_reads_stay_correct_under_concurrent_reader_and_writer_threads(tmp_path: Path) -> None:
    """A single VectorRepository instance is shared across FastAPI's
    sync-endpoint threadpool in real deployment (get_cached_vector_repository).
    Reader threads hammer the same cached table handle this fix
    introduces while a writer thread adds chunks concurrently through a
    separate, uncached handle -- must produce no exceptions and the
    reader threads must eventually see every written chunk, not a
    handle frozen at whatever version existed when it was first cached.
    """
    repo = _repo(tmp_path)
    repo.add_chunks([_chunk("seed", "doc-seed")], [[0.0, 0.0, 0.0, 0.0]])

    write_count = 30
    errors: list[BaseException] = []
    stop = threading.Event()
    writes_done = threading.Event()

    def writer() -> None:
        for i in range(write_count):
            try:
                repo.add_chunks([_chunk(f"w{i}", f"doc-w{i}")], [[0.0, 0.0, 0.0, 1.0]])
            except BaseException as exc:  # noqa: BLE001 - captured for the assertion below
                errors.append(exc)
        writes_done.set()

    def reader() -> None:
        while not stop.is_set():
            try:
                repo.count()
                repo.search([0.0, 0.0, 0.0, 0.0], limit=3)
            except BaseException as exc:  # noqa: BLE001 - captured for the assertion below
                errors.append(exc)
                return

    threads = [threading.Thread(target=writer)] + [threading.Thread(target=reader) for _ in range(4)]
    for t in threads:
        t.start()
    writes_done.wait(timeout=30)
    stop.set()
    for t in threads:
        t.join(timeout=10)

    assert errors == []
    assert repo.count() == write_count + 1
