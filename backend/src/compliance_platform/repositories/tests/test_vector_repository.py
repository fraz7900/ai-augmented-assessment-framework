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
import time
from pathlib import Path

import lancedb
import pyarrow as pa

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

    threads = [threading.Thread(target=writer)] + [
        threading.Thread(target=reader) for _ in range(4)
    ]
    for t in threads:
        t.start()
    writes_done.wait(timeout=30)
    stop.set()
    for t in threads:
        t.join(timeout=10)

    assert errors == []
    assert repo.count() == write_count + 1


# --- page_number schema migration (Sprint 18, ADR-0042) ---


def test_pre_existing_store_without_page_number_is_migrated_on_open(tmp_path: Path) -> None:
    # A hand-built "legacy" store on the OLD schema (no page_number
    # column at all) -- the exact shape any real pre-ADR-0042 local
    # vector store is in. Constructing VectorRepository against it must
    # not fail on a schema mismatch, and pre-existing rows must survive
    # with page_number=None, not be dropped or corrupted.
    store_dir = tmp_path / "lancedb"
    store_dir.mkdir()
    db = lancedb.connect(str(store_dir))
    old_schema = pa.schema(
        [
            pa.field("chunk_id", pa.string()),
            pa.field("document_id", pa.string()),
            pa.field("chunk_index", pa.int32()),
            pa.field("text", pa.string()),
            pa.field("chunking_strategy", pa.string()),
            pa.field("section_reference", pa.string()),
            pa.field("char_start", pa.int32()),
            pa.field("char_end", pa.int32()),
            pa.field("vector", pa.list_(pa.float32(), _DIMENSIONS)),
        ]
    )
    table = db.create_table("evidence_chunks", schema=old_schema)
    table.add(
        [
            {
                "chunk_id": "legacy-1",
                "document_id": "doc-legacy",
                "chunk_index": 0,
                "text": "pre-existing chunk from before page_number existed",
                "chunking_strategy": "fixed_window",
                "section_reference": "",
                "char_start": 0,
                "char_end": 10,
                "vector": [0.0] * _DIMENSIONS,
            }
        ]
    )

    repo = VectorRepository(store_dir, _DIMENSIONS)
    assert repo.count() == 1
    legacy_chunks = repo.chunks_for_document("doc-legacy")
    assert legacy_chunks[0]["chunk_id"] == "legacy-1"
    assert legacy_chunks[0]["page_number"] is None

    # A NEW chunk with a real page_number must also write successfully
    # against the now-migrated table.
    new_chunk = EvidenceChunk(
        chunk_id="new-1",
        document_id="doc-new",
        chunk_index=0,
        text="a fresh chunk on page 3",
        chunking_strategy=ChunkingStrategy.FIXED_WINDOW,
        char_start=0,
        char_end=24,
        page_number=3,
    )
    repo.add_chunks([new_chunk], [[1.0, 0.0, 0.0, 0.0]])
    new_chunks = repo.chunks_for_document("doc-new")
    assert new_chunks[0]["page_number"] == 3


# --- row_number/sheet_name schema migration (Sprint 18, ADR-0052) ---


def test_pre_existing_store_without_row_number_or_sheet_name_is_migrated_on_open(
    tmp_path: Path,
) -> None:
    # A hand-built "legacy" store on the post-ADR-0042 schema (has
    # page_number, predates row_number/sheet_name) -- the realistic shape
    # of any real pre-ADR-0052 local vector store. Same discipline as the
    # page_number migration test above: must not fail on the schema
    # mismatch, and pre-existing rows must survive with row_number/
    # sheet_name=None, not be dropped or corrupted.
    store_dir = tmp_path / "lancedb"
    store_dir.mkdir()
    db = lancedb.connect(str(store_dir))
    old_schema = pa.schema(
        [
            pa.field("chunk_id", pa.string()),
            pa.field("document_id", pa.string()),
            pa.field("chunk_index", pa.int32()),
            pa.field("text", pa.string()),
            pa.field("chunking_strategy", pa.string()),
            pa.field("section_reference", pa.string()),
            pa.field("char_start", pa.int32()),
            pa.field("char_end", pa.int32()),
            pa.field("vector", pa.list_(pa.float32(), _DIMENSIONS)),
            pa.field("page_number", pa.int32()),
        ]
    )
    table = db.create_table("evidence_chunks", schema=old_schema)
    table.add(
        [
            {
                "chunk_id": "legacy-1",
                "document_id": "doc-legacy",
                "chunk_index": 0,
                "text": "pre-existing chunk from before row_number/sheet_name existed",
                "chunking_strategy": "fixed_window",
                "section_reference": "",
                "char_start": 0,
                "char_end": 10,
                "vector": [0.0] * _DIMENSIONS,
                "page_number": None,
            }
        ]
    )

    repo = VectorRepository(store_dir, _DIMENSIONS)
    assert repo.count() == 1
    legacy_chunks = repo.chunks_for_document("doc-legacy")
    assert legacy_chunks[0]["chunk_id"] == "legacy-1"
    assert legacy_chunks[0]["row_number"] is None
    assert legacy_chunks[0]["sheet_name"] is None

    # A NEW chunk with real row_number/sheet_name must also write
    # successfully against the now-migrated table.
    new_chunk = EvidenceChunk(
        chunk_id="new-1",
        document_id="doc-new",
        chunk_index=0,
        text="Row 2: Name: Firewall-01",
        chunking_strategy=ChunkingStrategy.STRUCTURE_AWARE,
        section_reference="Assets",
        char_start=0,
        char_end=25,
        row_number=2,
        sheet_name="Assets",
    )
    repo.add_chunks([new_chunk], [[1.0, 0.0, 0.0, 0.0]])
    new_chunks = repo.chunks_for_document("doc-new")
    assert new_chunks[0]["row_number"] == 2
    assert new_chunks[0]["sheet_name"] == "Assets"


def test_row_number_and_sheet_name_round_trip_through_a_fresh_store(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    chunk = EvidenceChunk(
        chunk_id="c1",
        document_id="doc-1",
        chunk_index=0,
        text="Row 3: Owner: NetOps",
        chunking_strategy=ChunkingStrategy.STRUCTURE_AWARE,
        section_reference="Assets",
        char_start=0,
        char_end=20,
        row_number=3,
        sheet_name="Assets",
    )
    repo.add_chunks([chunk], [[1.0, 0.0, 0.0, 0.0]])
    chunks = repo.chunks_for_document("doc-1")
    assert chunks[0]["row_number"] == 3
    assert chunks[0]["sheet_name"] == "Assets"


def test_page_number_round_trips_through_a_fresh_store(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    chunk = EvidenceChunk(
        chunk_id="c1",
        document_id="doc-1",
        chunk_index=0,
        text="chunk on page 2",
        chunking_strategy=ChunkingStrategy.FIXED_WINDOW,
        char_start=0,
        char_end=15,
        page_number=2,
    )
    repo.add_chunks([chunk], [[1.0, 0.0, 0.0, 0.0]])
    assert repo.chunks_for_document("doc-1")[0]["page_number"] == 2


# --- Performance regression (Sprint 18, ADR-0044) ---
#
# Complexity-SCALING guards, not absolute wall-clock thresholds. This
# project's own WSL2/OneDrive-mounted-filesystem environment is
# documented as too noisy for reliable absolute timing assertions (see
# AGENTS.md, and ADR-0033/ADR-0037's own disclosed timing caveats) --
# but the RATIO between a small-corpus and large-corpus measurement of
# the same lookup is far more robust to that noise, and is exactly the
# shape of the real bug ADR-0033 found and fixed:
# chunks_for_document() used to load the ENTIRE vector store
# (table.to_pandas()) before filtering in Python -- an O(total corpus
# size) cost for what should be O(this document's own chunk count). A
# regression back to that pattern would show a dramatic ratio increase
# proportional to corpus growth; this test would fail long before
# reaching anywhere near that magnitude.


def _bulk_chunks(prefix: str, document_id: str, count: int) -> list[EvidenceChunk]:
    return [
        EvidenceChunk(
            chunk_id=f"{prefix}-{i}",
            document_id=document_id,
            chunk_index=i,
            text="bulk chunk text",
            chunking_strategy=ChunkingStrategy.FIXED_WINDOW,
            char_start=0,
            char_end=16,
        )
        for i in range(count)
    ]


def _measure_chunks_for_document(
    repo: VectorRepository, document_id: str, samples: int = 50
) -> float:
    for _ in range(10):  # warm-up: excludes cold-open/first-query overhead from the measurement
        repo.chunks_for_document(document_id)
    start = time.perf_counter()
    for _ in range(samples):
        repo.chunks_for_document(document_id)
    return time.perf_counter() - start


def test_chunks_for_document_latency_does_not_scale_with_unrelated_document_count(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    repo.add_chunks(_bulk_chunks("target", "target-doc", 5), [[0.0] * _DIMENSIONS] * 5)
    baseline = _measure_chunks_for_document(repo, "target-doc")

    # 30 unrelated documents x 20 chunks = 600 unrelated rows added --
    # corpus grows >100x from this point.
    for batch in range(30):
        repo.add_chunks(
            _bulk_chunks(f"other-{batch}", f"other-doc-{batch}", 20), [[0.0] * _DIMENSIONS] * 20
        )
    assert repo.count() == 605

    after = _measure_chunks_for_document(repo, "target-doc")

    # An O(total corpus) regression would show a slowdown proportional
    # to the >100x corpus growth; empirically, the real fixed
    # implementation's ratio is consistently ~1.5-2x across repeated
    # runs in this environment. 8x leaves generous headroom above that
    # noise band while still catching a real regression long before it
    # reaches 100x.
    assert after < baseline * 8 + 0.5  # +0.5s floor absorbs noise when baseline is near-zero


def test_search_within_documents_latency_does_not_scale_with_unrelated_document_count(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    repo.add_chunks(_bulk_chunks("target", "target-doc", 5), [[1.0, 0.0, 0.0, 0.0]] * 5)

    def _measure() -> float:
        for _ in range(10):
            repo.search_within_documents([1.0, 0.0, 0.0, 0.0], ["target-doc"])
        start = time.perf_counter()
        for _ in range(50):
            repo.search_within_documents([1.0, 0.0, 0.0, 0.0], ["target-doc"])
        return time.perf_counter() - start

    baseline = _measure()
    for batch in range(30):
        repo.add_chunks(
            _bulk_chunks(f"other-{batch}", f"other-doc-{batch}", 20), [[0.0] * _DIMENSIONS] * 20
        )
    after = _measure()

    assert after < baseline * 8 + 0.5
