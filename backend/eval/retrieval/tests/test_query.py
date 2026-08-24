"""Tests for the Stage 2 query runner.

Uses a fake Embedder and a fake VectorRepository (same pattern as
services/tests/test_ingestion_service.py) so these tests stay fast and
hermetic, but loads the REAL framework_mapping/c2m2_v2_1.yaml -- that
parse is cheap (no ML involved) and it is the one thing worth testing
for real: that a label's (practice_id, framework) actually resolves
against the genuine framework file, not a hand-rolled fixture that
could silently drift from it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from compliance_platform.services.framework_loader import load_framework_file
from eval.labels.schema import RelevanceLabel
from eval.retrieval.query import PracticeNotFoundError, find_practice, run_queries

REPO_ROOT = Path(__file__).resolve().parents[4]
FRAMEWORK_MAPPING_DIR = REPO_ROOT / "framework_mapping"


class _FakeEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t))] for t in texts]


class _FakeVectorRepository:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def search_within_documents(
        self, query_vector, document_ids: list[str], limit: int = 5
    ) -> list[dict]:
        self.last_call = (query_vector, document_ids, limit)
        return self._rows[:limit]


def test_find_practice_resolves_a_real_practice_id() -> None:
    framework_def = load_framework_file(FRAMEWORK_MAPPING_DIR / "c2m2_v2_1.yaml")

    practice = find_practice(framework_def, "ACCESS-1h")

    assert practice.id == "ACCESS-1h"
    assert "multifactor" in practice.text.lower() or "multi-factor" in practice.text.lower() \
        or "single use credentials" in practice.text.lower()


def test_find_practice_raises_for_unknown_id() -> None:
    framework_def = load_framework_file(FRAMEWORK_MAPPING_DIR / "c2m2_v2_1.yaml")

    with pytest.raises(PracticeNotFoundError, match="NOT-A-REAL-ID"):
        find_practice(framework_def, "NOT-A-REAL-ID")


def test_run_queries_dedupes_by_practice_and_framework() -> None:
    labels = [
        RelevanceLabel("ACCESS-1h", "c2m2_v2_1", "d.md", 0, 5),
        RelevanceLabel("ACCESS-1h", "c2m2_v2_1", "d.md", 10, 15),  # same practice, 2nd gold span
        RelevanceLabel("RESPONSE-1a", "c2m2_v2_1", "d.md", 20, 25),
    ]
    rows = [
        {"chunk_id": "c1", "document_id": "doc-1", "char_start": 0, "char_end": 5, "_distance": 0.1}
    ]

    results = run_queries(
        labels=labels,
        embedder=_FakeEmbedder(),
        vector_repository=_FakeVectorRepository(rows),
        document_ids=["doc-1"],
        framework_mapping_dir=FRAMEWORK_MAPPING_DIR,
        limit=5,
    )

    assert sorted(r.practice_id for r in results) == ["ACCESS-1h", "RESPONSE-1a"]


def test_run_queries_returns_ranked_chunks_in_search_order() -> None:
    labels = [RelevanceLabel("ACCESS-1h", "c2m2_v2_1", "d.md", 0, 5)]
    rows = [
        {
            "chunk_id": "c1",
            "document_id": "doc-1",
            "char_start": 0,
            "char_end": 5,
            "_distance": 0.05,
        },
        {
            "chunk_id": "c2",
            "document_id": "doc-2",
            "char_start": 5,
            "char_end": 10,
            "_distance": 0.3,
        },
    ]

    [result] = run_queries(
        labels=labels,
        embedder=_FakeEmbedder(),
        vector_repository=_FakeVectorRepository(rows),
        document_ids=["doc-1", "doc-2"],
        framework_mapping_dir=FRAMEWORK_MAPPING_DIR,
        limit=5,
    )

    assert [c.chunk_id for c in result.ranked_chunks] == ["c1", "c2"]
    assert result.ranked_chunks[0].distance == 0.05


def test_run_queries_raises_for_a_labeled_practice_missing_from_the_framework() -> None:
    labels = [RelevanceLabel("NOT-A-REAL-ID", "c2m2_v2_1", "d.md", 0, 5)]

    with pytest.raises(PracticeNotFoundError):
        run_queries(
            labels=labels,
            embedder=_FakeEmbedder(),
            vector_repository=_FakeVectorRepository([]),
            document_ids=["doc-1"],
            framework_mapping_dir=FRAMEWORK_MAPPING_DIR,
            limit=5,
        )
