"""Tests for the Stage 3 metric functions.

Every expected value below is hand-computed (either a value derivable
by inspection, or the recall/DCG/IDCG arithmetic spelled out in a
comment) against a synthetic list[bool] fixture -- never against a live
retrieval run, per backend/eval/CLAUDE.md's requirement that metric
functions be verified independent of whatever the harness itself
retrieves.
"""

from __future__ import annotations

import math

import pytest

from eval.metrics.ranking import is_relevant, ndcg_at_k, recall_at_k, reciprocal_rank, spans_overlap

# --- spans_overlap / is_relevant ---------------------------------------


def test_spans_overlap_true_for_overlapping_ranges() -> None:
    assert spans_overlap(0, 10, 5, 15) is True


def test_spans_overlap_false_for_adjacent_half_open_ranges() -> None:
    # [0, 10) and [10, 20) touch at 10 but do not overlap -- half-open.
    assert spans_overlap(0, 10, 10, 20) is False


def test_spans_overlap_false_for_disjoint_ranges() -> None:
    assert spans_overlap(0, 5, 100, 200) is False


def test_spans_overlap_true_when_one_span_contains_the_other() -> None:
    assert spans_overlap(0, 100, 40, 60) is True


def test_is_relevant_false_for_a_different_document() -> None:
    assert is_relevant("doc-2", 0, 10, "doc-1", [(0, 10)]) is False


def test_is_relevant_true_for_same_document_overlapping_span() -> None:
    assert is_relevant("doc-1", 5, 15, "doc-1", [(0, 10)]) is True


def test_is_relevant_true_when_any_of_several_gold_spans_overlaps() -> None:
    assert is_relevant("doc-1", 500, 510, "doc-1", [(0, 10), (490, 520)]) is True


def test_is_relevant_false_when_same_document_but_no_span_overlaps() -> None:
    assert is_relevant("doc-1", 1000, 1010, "doc-1", [(0, 10), (490, 520)]) is False


# --- recall_at_k ---------------------------------------------------------


def test_recall_at_k_perfect_ranking() -> None:
    flags = [True, True, False]  # 2 relevant chunks, both in the top 2
    assert recall_at_k(flags, num_relevant=2, k=2) == pytest.approx(1.0)
    assert recall_at_k(flags, num_relevant=2, k=1) == pytest.approx(0.5)


def test_recall_at_k_finds_none_in_window() -> None:
    flags = [False, False, True]  # the only relevant chunk is at rank 3
    assert recall_at_k(flags, num_relevant=1, k=2) == pytest.approx(0.0)
    assert recall_at_k(flags, num_relevant=1, k=3) == pytest.approx(1.0)


def test_recall_at_k_zero_relevant_is_a_defensive_zero_not_nan() -> None:
    assert recall_at_k([False, False], num_relevant=0, k=2) == 0.0


# --- reciprocal_rank -------------------------------------------------------


def test_reciprocal_rank_first_hit_at_rank_one() -> None:
    assert reciprocal_rank([True, False, False]) == pytest.approx(1.0)


def test_reciprocal_rank_first_hit_at_rank_three() -> None:
    assert reciprocal_rank([False, False, True]) == pytest.approx(1.0 / 3.0)


def test_reciprocal_rank_no_hit_is_zero() -> None:
    assert reciprocal_rank([False, False, False]) == 0.0


# --- ndcg_at_k -------------------------------------------------------------


def test_ndcg_at_k_perfect_ranking_is_one() -> None:
    # Both relevant chunks (num_relevant=2) occupy the top 2 ranks --
    # the ranking IS the ideal ranking, so DCG == IDCG == 1 + 1/log2(3).
    flags = [True, True, False]
    assert ndcg_at_k(flags, num_relevant=2, k=3) == pytest.approx(1.0)


def test_ndcg_at_k_no_hits_is_zero() -> None:
    assert ndcg_at_k([False, False, False], num_relevant=2, k=3) == 0.0


def test_ndcg_at_k_worst_ordering_hand_computed() -> None:
    # One relevant chunk (num_relevant=1), found at rank 3 of 3.
    # DCG@3   = 1/log2(3+1) = 1/2 = 0.5
    # IDCG@3  = ideal places the single relevant chunk at rank 1:
    #           1/log2(1+1) = 1/1 = 1.0
    # nDCG@3  = 0.5 / 1.0 = 0.5
    flags = [False, False, True]
    expected_dcg = 1.0 / math.log2(4)
    expected_idcg = 1.0 / math.log2(2)
    assert ndcg_at_k(flags, num_relevant=1, k=3) == pytest.approx(expected_dcg / expected_idcg)
    assert ndcg_at_k(flags, num_relevant=1, k=3) == pytest.approx(0.5)


def test_ndcg_at_k_rewards_earlier_hits_over_later_ones() -> None:
    # Same single relevant chunk, found at rank 1 instead of rank 3 --
    # nDCG must be strictly higher.
    earlier = ndcg_at_k([True, False, False], num_relevant=1, k=3)
    later = ndcg_at_k([False, False, True], num_relevant=1, k=3)
    assert earlier == pytest.approx(1.0)
    assert earlier > later


def test_ndcg_at_k_two_relevant_out_of_order_hand_computed() -> None:
    # num_relevant=2, hits at ranks 2 and 4 of 4.
    # DCG@4  = 1/log2(3) + 1/log2(5)
    # IDCG@4 = ideal places both relevant chunks first: 1/log2(2) + 1/log2(3)
    flags = [False, True, False, True]
    expected_dcg = 1.0 / math.log2(3) + 1.0 / math.log2(5)
    expected_idcg = 1.0 / math.log2(2) + 1.0 / math.log2(3)
    assert ndcg_at_k(flags, num_relevant=2, k=4) == pytest.approx(expected_dcg / expected_idcg)


def test_ndcg_at_k_zero_relevant_is_a_defensive_zero_not_nan() -> None:
    assert ndcg_at_k([False, False], num_relevant=0, k=2) == 0.0
