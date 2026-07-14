"""Vector storage repository (LanceDB), per ADR-0005.

Per the Repository pattern described in repositories/README.md,
services/ must never import lancedb directly — only this module's
interface. That boundary is what makes ADR-0005 reversible if a future
sprint needs to switch vector stores.
"""

from __future__ import annotations

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
            ]
        )

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
        try:
            return self._db.open_table(_TABLE_NAME)
        except ValueError:
            return None

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
            }
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        table.add(rows)

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
        table = self._open_existing_table()
        if table is None:
            return []
        df = table.to_pandas()
        matched = df[df["document_id"] == document_id]
        return matched.drop(columns=["vector"]).to_dict(orient="records")
