"""Tests for the label <-> QueryResult scoring aggregation layer.

Uses hand-built RankedChunk/QueryResult/RelevanceLabel fixtures -- no
retrieval, embedding, or vector store involved -- so these tests check
the wiring between "what was retrieved" and "what was labeled gold"
without depending on ranking.py's own correctness (that is
test_ranking.py's job).
"""

from __future__ import annotations

from eval.labels.schema import RelevanceLabel
from eval.metrics.scoring import score_query_results
from eval.retrieval.query import QueryResult, RankedChunk


def _chunk(chunk_id: str, document_id: str, char_start: int, char_end: int) -> RankedChunk:
    return RankedChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        char_start=char_start,
        char_end=char_end,
        distance=0.1,
    )


def test_score_query_results_scores_a_hit_at_rank_one() -> None:
    labels = [RelevanceLabel("ACCESS-1h", "c2m2_v2_1", "doc.md", 0, 10)]
    query_results = [
        QueryResult(
            practice_id="ACCESS-1h",
            framework="c2m2_v2_1",
            query_text="...",
            ranked_chunks=[_chunk("c1", "doc-1", 0, 10), _chunk("c2", "doc-1", 50, 60)],
        )
    ]

    aggregate = score_query_results(
        query_results, labels, {"doc.md": "doc-1"}, k_values=[1, 2]
    )

    assert aggregate.num_queries == 1
    assert aggregate.mean_recall_at_k == {1: 1.0, 2: 1.0}
    assert aggregate.mean_reciprocal_rank == 1.0


def test_score_query_results_scores_a_miss() -> None:
    labels = [RelevanceLabel("ACCESS-1h", "c2m2_v2_1", "doc.md", 0, 10)]
    query_results = [
        QueryResult(
            practice_id="ACCESS-1h",
            framework="c2m2_v2_1",
            query_text="...",
            ranked_chunks=[_chunk("c1", "doc-1", 500, 510)],
        )
    ]

    aggregate = score_query_results(query_results, labels, {"doc.md": "doc-1"}, k_values=[1])

    assert aggregate.mean_recall_at_k == {1: 0.0}
    assert aggregate.mean_reciprocal_rank == 0.0


def test_score_query_results_a_chunk_from_a_different_document_is_not_relevant() -> None:
    # Same char range, but a DIFFERENT document_id -- must not count as
    # a hit, even though the offsets alone would overlap.
    labels = [RelevanceLabel("ACCESS-1h", "c2m2_v2_1", "doc.md", 0, 10)]
    query_results = [
        QueryResult(
            practice_id="ACCESS-1h",
            framework="c2m2_v2_1",
            query_text="...",
            ranked_chunks=[_chunk("c1", "some-other-doc", 0, 10)],
        )
    ]

    aggregate = score_query_results(query_results, labels, {"doc.md": "doc-1"}, k_values=[1])

    assert aggregate.mean_recall_at_k == {1: 0.0}


def test_score_query_results_skips_a_query_with_no_matching_label() -> None:
    labels: list[RelevanceLabel] = []
    query_results = [
        QueryResult(
            practice_id="ACCESS-1h",
            framework="c2m2_v2_1",
            query_text="...",
            ranked_chunks=[_chunk("c1", "doc-1", 0, 10)],
        )
    ]

    aggregate = score_query_results(query_results, labels, {}, k_values=[1])

    assert aggregate.num_queries == 0
    assert aggregate.mean_recall_at_k == {1: 0.0}
    assert aggregate.per_query == []


def test_score_query_results_averages_across_multiple_queries() -> None:
    labels = [
        RelevanceLabel("ACCESS-1h", "c2m2_v2_1", "a.md", 0, 10),
        RelevanceLabel("RESPONSE-1a", "c2m2_v2_1", "b.md", 0, 10),
    ]
    query_results = [
        QueryResult(
            practice_id="ACCESS-1h",
            framework="c2m2_v2_1",
            query_text="...",
            ranked_chunks=[_chunk("c1", "doc-a", 0, 10)],  # hit
        ),
        QueryResult(
            practice_id="RESPONSE-1a",
            framework="c2m2_v2_1",
            query_text="...",
            ranked_chunks=[_chunk("c2", "doc-b", 500, 510)],  # miss
        ),
    ]

    aggregate = score_query_results(
        query_results, labels, {"a.md": "doc-a", "b.md": "doc-b"}, k_values=[1]
    )

    assert aggregate.num_queries == 2
    assert aggregate.mean_recall_at_k == {1: 0.5}
    assert aggregate.mean_reciprocal_rank == 0.5
