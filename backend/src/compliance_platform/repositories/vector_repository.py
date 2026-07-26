"""Vector storage repository (LanceDB), per ADR-0005.

Per the Repository pattern described in repositories/README.md,
services/ must never import lancedb directly — only this module's
interface. That boundary is what makes ADR-0005 reversible if a future
sprint needs to switch vector stores.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import lancedb
import pyarrow as pa

from compliance_platform.models.schemas import EvidenceChunk

_TABLE_NAME = "evidence_chunks"


class VectorRepository:
    def __init__(self, store_dir: Path, dimensions: int) -> None:
        store_dir.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(store_dir))
        self._dimensions = dimensions
        # Cached read-path table handle (ADR-0037) -- None until the
        # table first exists. Guarded by _cache_lock only while
        # populating the cache; the cached handle's own thread-safety
        # under concurrent checkout_latest()/search() calls was verified
        # directly, not assumed (see ADR-0037).
        self._cached_table = None
        self._cache_lock = threading.Lock()
        self._migrate_schema()

    def _schema(self) -> pa.Schema:
        return pa.schema(
            [
                pa.field("chunk_id", pa.string()),
                pa.field("document_id", pa.string()),
                pa.field("chunk_index", pa.int32()),
                pa.field("text", pa.string()),
                pa.field("chunking_strategy", pa.string()),
                pa.field("section_reference", pa.string()),
                pa.field("char_start", pa.int32()),
                pa.field("char_end", pa.int32()),
                pa.field("vector", pa.list_(pa.float32(), self._dimensions)),
                pa.field("page_number", pa.int32()),
            ]
        )

    def _migrate_schema(self) -> None:
        # LanceDB's own schema-evolution primitive (Table.add_columns) --
        # this project's equivalent of assessment_repository.py's SQLite
        # _add_missing_columns() ALTER TABLE helper. create_table(...,
        # exist_ok=True) does NOT retroactively add a new field to an
        # already-created on-disk table (confirmed empirically, not
        # assumed), so a pre-existing store from before page_number
        # (ADR-0042) existed would otherwise have every existing chunk's
        # add() call fail on a schema mismatch the moment this repository
        # tries to write a row with the new field. No-op if the table
        # doesn't exist yet (a fresh create_table() call will use the
        # current schema, nothing to migrate) or already has the column.
        try:
            table = self._db.open_table(_TABLE_NAME)
        except ValueError:
            return
        existing_fields = {field.name for field in table.schema}
        if "page_number" not in existing_fields:
            table.add_columns({"page_number": "CAST(NULL AS INT)"})

    def _ensure_table(self):
        # Deliberately not implemented as "check list_tables(), then
        # create or open" — that check-then-act pattern raced against
        # itself in testing: list_tables() did not reliably reflect a
        # table created moments earlier on this filesystem (this project
        # runs on a OneDrive-synced Windows drive mounted into WSL,
        # accessed here via /mnt/c; directory-listing consistency
        # immediately after a write is not guaranteed on that path). Using
        # create_table(..., exist_ok=True) makes table creation
        # idempotent and avoids depending on listing consistency at all.
        # Caught by actually running the ingestion-twice integration test,
        # not assumed safe from reading the lancedb API alone.
        return self._db.create_table(_TABLE_NAME, schema=self._schema(), exist_ok=True)

    def _open_existing_table(self):
        # Caches the opened Table handle across calls instead of
        # re-opening from disk every time (ADR-0033 measured ~40-120ms
        # of pure re-open overhead per call, multiplied by ~350 calls in
        # a single propose-mappings request). Safe under concurrent
        # writes made through a *different* handle (e.g. add_chunks's
        # _ensure_table(), which is intentionally NOT cached and keeps
        # opening fresh) only because every read here calls
        # checkout_latest() first -- confirmed empirically, not assumed:
        # a held Table handle does NOT see another handle's writes on
        # its own, but checkout_latest() reliably refreshes it to the
        # newest version, and doing so is measurably cheaper than a full
        # open_table() re-open. See ADR-0037 for the verification.
        if self._cached_table is not None:
            self._cached_table.checkout_latest()
            return self._cached_table
        with self._cache_lock:
            if self._cached_table is not None:
                self._cached_table.checkout_latest()
                return self._cached_table
            try:
                self._cached_table = self._db.open_table(_TABLE_NAME)
            except ValueError:
                return None
            return self._cached_table

    def add_chunks(self, chunks: list[EvidenceChunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError(
                f"chunks ({len(chunks)}) and vectors ({len(vectors)}) must be the same length"
            )
        if not chunks:
            return
        table = self._ensure_table()
        rows = [
            {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "chunking_strategy": chunk.chunking_strategy.value,
                "section_reference": chunk.section_reference or "",
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
                "vector": vector,
                "page_number": chunk.page_number,
            }
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        table.add(rows)

    def delete_chunks_for_document(self, document_id: str) -> None:
        """Deletes every chunk belonging to one document. A compensating
        action for services/ingestion_service.py.ingest() (ADR-0046): if
        the Document registry write fails AFTER chunks were already
        written here, this removes them so the failed ingest doesn't
        leave orphaned-but-functional chunks behind with no Document row
        — see ADR-0044's originally-disclosed finding and ADR-0046 for
        the fix. Not used on any other path. A no-op if the table
        doesn't exist yet or the document has no chunks (LanceDB's
        delete on a predicate matching zero rows).
        """
        table = self._ensure_table()
        escaped_id = document_id.replace("'", "''")
        table.delete(f"document_id = '{escaped_id}'")

    def count(self) -> int:
        table = self._open_existing_table()
        return table.count_rows() if table is not None else 0

    def search(self, query_vector: list[float], limit: int = 5) -> list[dict[str, Any]]:
        """Nearest-neighbor search. Returns rows including a `_distance`
        field; callers needing a citation (see the evidence-extraction
        skill) should use document_id/chunk_id/char_start/char_end from
        the result, not the text alone.
        """
        table = self._open_existing_table()
        if table is None:
            return []
        return table.search(query_vector).limit(limit).to_list()

    def chunks_for_document(self, document_id: str) -> list[dict[str, Any]]:
        """Filtered read of one document's own chunks — deliberately a
        native LanceDB filter (`search().where(...)`), NOT
        `table.to_pandas()` + a Python-side dataframe filter. The
        to_pandas() approach materializes and copies EVERY row in the
        entire vector store (all documents, all vectors) into memory on
        every single call, an O(total corpus size) cost for what should
        be an O(this document's own chunk count) lookup — confirmed as
        a real, measured bottleneck via
        backend/scripts/benchmark_scalability.py (evidence-linking
        latency degraded ~7x, 207ms to 1.4s per link, going from 100 to
        1000 documents in the vector store; this method is on that
        call's hot path via services/assessment_service.py.link_evidence's
        existence check). See docs/architecture/
        02-controlled-pilot-readiness-audit.md §F.6 and ADR-0033.
        """
        table = self._open_existing_table()
        if table is None:
            return []
        escaped_id = document_id.replace("'", "''")
        rows = table.search().where(f"document_id = '{escaped_id}'").to_list()
        for row in rows:
            row.pop("vector", None)
        return rows

    def search_within_documents(
        self, query_vector: list[float], document_ids: list[str], limit: int = 5
    ) -> list[dict[str, Any]]:
        """Nearest-neighbor search restricted to chunks from a given set
        of documents — used by services/mapping_service.py (Sprint 5) to
        propose evidence only from documents already associated with the
        assessment being scored, not the entire global vector store.

        document_ids are expected to be server-generated UUIDs (see
        services/document_parsers.py) that already passed the
        document-exists check in services/assessment_service.py before
        reaching here; the quote-escaping below is defense-in-depth, not
        the only thing standing between this and injection.
        """
        table = self._open_existing_table()
        if table is None or not document_ids:
            return []
        escaped_ids = [doc_id.replace("'", "''") for doc_id in document_ids]
        ids_sql = ", ".join(f"'{doc_id}'" for doc_id in escaped_ids)
        return (
            table.search(query_vector)
            .where(f"document_id IN ({ids_sql})")
            .limit(limit)
            .to_list()
        )
