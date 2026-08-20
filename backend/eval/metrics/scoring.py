"""Aggregation layer: turns a run's Stage 2 QueryResults + the labels
they were scored against into per-query and mean recall@k/MRR/nDCG.

Kept separate from ranking.py's pure list[bool]-in functions (which
stay independently hand-fixture-tested, see metrics/tests/
test_ranking.py) and from retrieval/query.py's QueryResult (which knows
nothing about labels). This is the one place that connects "what was
retrieved" to "what was labeled gold" via the span-overlap rule -- used
by both a single default run (run_eval.py) and every point in the
Stage 4 ablation grid (ablation/grid.py), so the scoring logic lives in
exactly one place rather than once per caller.
"""

from __future__ import annotations

from dataclasses import dataclass

from eval.labels.schema import RelevanceLabel
from eval.metrics.ranking import is_relevant, ndcg_at_k, recall_at_k, reciprocal_rank
from eval.retrieval.query import QueryResult


@dataclass(frozen=True)
class QueryScore:
    practice_id: str
    framework: str
    num_gold_spans: int
    num_retrieved: int
    recall_at_k: dict[int, float]
    ndcg_at_k: dict[int, float]
    reciprocal_rank: float


@dataclass(frozen=True)
class AggregateScore:
    num_queries: int
    mean_recall_at_k: dict[int, float]
    mean_ndcg_at_k: dict[int, float]
    mean_reciprocal_rank: float
    per_query: list[QueryScore]


def score_query_results(
    query_results: list[QueryResult],
    labels: list[RelevanceLabel],
    doc_ref_to_document_id: dict[str, str],
    k_values: list[int],
) -> AggregateScore:
    """Scores each QueryResult against the label rows sharing its
    (practice_id, framework). A practice with no gold label rows in
    `labels` is silently skipped (its QueryResult contributes nothing to
    the mean) -- run_queries() only ever produces a QueryResult for a
    practice a label actually named, so this only fires if `labels`
    passed here is a subset of the labels `run_queries` was given, which
    callers should avoid.

    doc_ref_to_document_id resolves each label's gold doc_ref (a repo
    path) to the document_id its chunks were actually indexed under
    (see retrieval/runner.py::build_eval_index) -- required so
    is_relevant can compare a retrieved chunk's document_id against the
    right gold document.
    """
    gold_by_query: dict[tuple[str, str], list[tuple[str, int, int]]] = {}
    for label in labels:
        key = (label.practice_id, label.framework)
        gold_by_query.setdefault(key, []).append(
            (doc_ref_to_document_id[label.doc_ref], label.char_start, label.char_end)
        )

    per_query: list[QueryScore] = []
    for result in query_results:
        gold_rows = gold_by_query.get((result.practice_id, result.framework), [])
        if not gold_rows:
            continue
        flags = [
            any(
                is_relevant(
                    chunk.document_id, chunk.char_start, chunk.char_end, gold_doc, [(gs, ge)]
                )
                for gold_doc, gs, ge in gold_rows
            )
            for chunk in result.ranked_chunks
        ]
        num_relevant = len(gold_rows)
        per_query.append(
            QueryScore(
                practice_id=result.practice_id,
                framework=result.framework,
                num_gold_spans=num_relevant,
                num_retrieved=len(result.ranked_chunks),
                recall_at_k={k: recall_at_k(flags, num_relevant, k) for k in k_values},
                ndcg_at_k={k: ndcg_at_k(flags, num_relevant, k) for k in k_values},
                reciprocal_rank=reciprocal_rank(flags),
            )
        )

    if not per_query:
        return AggregateScore(
            num_queries=0,
            mean_recall_at_k=dict.fromkeys(k_values, 0.0),
            mean_ndcg_at_k=dict.fromkeys(k_values, 0.0),
            mean_reciprocal_rank=0.0,
            per_query=[],
        )

    n = len(per_query)
    return AggregateScore(
        num_queries=n,
        mean_recall_at_k={k: sum(q.recall_at_k[k] for q in per_query) / n for k in k_values},
        mean_ndcg_at_k={k: sum(q.ndcg_at_k[k] for q in per_query) / n for k in k_values},
        mean_reciprocal_rank=sum(q.reciprocal_rank for q in per_query) / n,
        per_query=per_query,
    )
