"""Stage 3: retrieval-quality metrics -- recall@k, MRR, nDCG.

See backend/eval/README.md for why these three and not others: recall@k
alone can't distinguish "one relevant chunk at rank 1" from "one
relevant chunk at rank 5"; MRR and nDCG together cover that gap from two
different angles (first-hit rank vs. whole-ranking quality).

is_relevant() implements the span-overlap relevance rule (README.md,
"Relevance rule: span overlap, not chunk_id"): a retrieved chunk counts
as relevant to a practice if it's from the gold document and its own
[char_start, char_end) overlaps any gold span labelled for that
practice in that document.

recall_at_k/reciprocal_rank/ndcg_at_k take a plain `list[bool]` of
per-rank relevance flags, not RankedChunk/RelevanceLabel objects --
kept decoupled so these functions are unit-testable against
hand-computed synthetic fixtures with no document, embedder, or vector
store involved at all (backend/eval/CLAUDE.md: "Metric functions are
unit-tested against hand-computed synthetic fixtures, not against the
live run").
"""

from __future__ import annotations

import math


def spans_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """Half-open range overlap: does [a_start, a_end) intersect [b_start, b_end)?"""
    return a_start < b_end and b_start < a_end


def is_relevant(
    document_id: str,
    char_start: int,
    char_end: int,
    gold_document_id: str,
    gold_spans: list[tuple[int, int]],
) -> bool:
    if document_id != gold_document_id:
        return False
    return any(
        spans_overlap(char_start, char_end, gold_start, gold_end)
        for gold_start, gold_end in gold_spans
    )


def recall_at_k(relevant_flags: list[bool], num_relevant: int, k: int) -> float:
    """Fraction of the num_relevant gold-relevant chunks that appear in
    the top k ranked results.

    0.0 (not undefined/NaN) when num_relevant is 0 -- a defensive floor,
    not a case run_eval.py is expected to hit: it only scores a practice
    that has at least one gold span (see run_eval.py).
    """
    if num_relevant <= 0:
        return 0.0
    found = sum(1 for flag in relevant_flags[:k] if flag)
    return found / num_relevant


def reciprocal_rank(relevant_flags: list[bool]) -> float:
    """1/rank (1-indexed) of the first relevant result; 0.0 if none of
    the ranked results are relevant."""
    for i, flag in enumerate(relevant_flags, start=1):
        if flag:
            return 1.0 / i
    return 0.0


def ndcg_at_k(relevant_flags: list[bool], num_relevant: int, k: int) -> float:
    """Binary-relevance normalised DCG at k.

    Rewards a relevant chunk ranking higher over the same chunk ranking
    lower, normalised against the ideal ordering (every relevant chunk
    first) so scores are comparable across queries with different
    numbers of gold-relevant chunks. 0.0 when num_relevant is 0, same
    reasoning as recall_at_k.
    """
    if num_relevant <= 0:
        return 0.0
    dcg = sum(
        (1.0 if flag else 0.0) / math.log2(i + 1)
        for i, flag in enumerate(relevant_flags[:k], start=1)
    )
    ideal_hits = min(num_relevant, k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    if idcg == 0.0:
        return 0.0
    return dcg / idcg
