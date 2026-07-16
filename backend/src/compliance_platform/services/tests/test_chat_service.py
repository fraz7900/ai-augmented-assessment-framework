"""Unit tests for retrieval-only chat (Sprint 8), using a fake embedder
keyed by exact input text (not the mapping-service fake's call-order
index, since chat embeds a question and several chunk texts in one
batched call and needs controllable, meaningful similarity between
specific pairs) — real-model behavior is exercised separately, against
real data, in backend/tests/test_assessment_api_integration.py.
"""

from __future__ import annotations

from compliance_platform.models.assessment import EvidenceLink, EvidenceReviewStatus
from compliance_platform.services.chat_service import answer_question, cosine_similarity


class _FakeEmbedder:
    """Vectors keyed by exact text match; unknown text falls back to a
    fixed "unrelated" vector, orthogonal to every known text's vector.
    """

    def __init__(self, vectors_by_text: dict[str, list[float]]) -> None:
        self._vectors_by_text = vectors_by_text

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vectors_by_text.get(text, [0.0, 0.0, 1.0]) for text in texts]

    @property
    def backend_name(self) -> str:
        return "fake"

    @property
    def dimensions(self) -> int:
        return 3


class _FakeVectorRepository:
    def __init__(self, chunks_by_document: dict[str, list[dict]]) -> None:
        self._chunks_by_document = chunks_by_document

    def chunks_for_document(self, document_id: str) -> list[dict]:
        return self._chunks_by_document.get(document_id, [])


def _link(
    practice_reference: str,
    document_id: str = "doc-1",
    chunk_id: str | None = "c1",
    review_status: EvidenceReviewStatus = EvidenceReviewStatus.ACCEPTED,
) -> EvidenceLink:
    return EvidenceLink(
        assessment_id="a1",
        document_id=document_id,
        chunk_id=chunk_id,
        practice_reference=practice_reference,
        review_status=review_status,
    )


def test_cosine_similarity_is_one_for_identical_unit_vectors() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_cosine_similarity_is_zero_for_orthogonal_vectors() -> None:
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_similarity_clamps_negative_to_zero() -> None:
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == 0.0


def test_answer_question_returns_empty_for_blank_question() -> None:
    links = [_link("ACCESS-1a")]
    result = answer_question("   ", links, _FakeEmbedder({}), _FakeVectorRepository({}), 0.0, 5)
    assert result == []


def test_answer_question_returns_empty_with_no_evidence_links() -> None:
    result = answer_question(
        "any question", [], _FakeEmbedder({}), _FakeVectorRepository({}), 0.0, 5
    )
    assert result == []


def test_answer_question_excludes_pending_and_rejected_links() -> None:
    links = [
        _link("ACCESS-1a", review_status=EvidenceReviewStatus.PENDING),
        _link("ACCESS-1b", review_status=EvidenceReviewStatus.REJECTED),
    ]
    repo = _FakeVectorRepository({"doc-1": [{"chunk_id": "c1", "text": "policy text"}]})
    result = answer_question("question", links, _FakeEmbedder({}), repo, 0.0, 5)
    assert result == []


def test_answer_question_excludes_links_with_no_chunk_id() -> None:
    links = [_link("ACCESS-1a", chunk_id=None)]
    repo = _FakeVectorRepository({"doc-1": [{"chunk_id": "c1", "text": "policy text"}]})
    result = answer_question("question", links, _FakeEmbedder({}), repo, 0.0, 5)
    assert result == []


def test_answer_question_filters_below_similarity_threshold() -> None:
    links = [_link("ACCESS-1a")]
    repo = _FakeVectorRepository({"doc-1": [{"chunk_id": "c1", "text": "unrelated text"}]})
    embedder = _FakeEmbedder({"question": [1.0, 0.0, 0.0], "unrelated text": [0.0, 1.0, 0.0]})
    result = answer_question("question", links, embedder, repo, similarity_threshold=0.5, limit=5)
    assert result == []


def test_answer_question_includes_match_above_threshold_with_correct_fields() -> None:
    links = [_link("ACCESS-1a", document_id="doc-1", chunk_id="c1")]
    repo = _FakeVectorRepository(
        {"doc-1": [{"chunk_id": "c1", "text": "multi-factor authentication policy"}]}
    )
    embedder = _FakeEmbedder(
        {
            "which practices cover MFA": [1.0, 0.0, 0.0],
            "multi-factor authentication policy": [1.0, 0.0, 0.0],
        }
    )
    result = answer_question(
        "which practices cover MFA", links, embedder, repo, similarity_threshold=0.5, limit=5
    )
    assert len(result) == 1
    hit = result[0]
    assert hit.practice_reference == "ACCESS-1a"
    assert hit.document_id == "doc-1"
    assert hit.chunk_id == "c1"
    assert hit.chunk_text == "multi-factor authentication policy"
    assert hit.similarity == 1.0


def test_answer_question_ranks_by_similarity_descending() -> None:
    links = [
        _link("ACCESS-1a", document_id="doc-1", chunk_id="c1"),
        _link("ACCESS-1b", document_id="doc-1", chunk_id="c2"),
    ]
    repo = _FakeVectorRepository(
        {
            "doc-1": [
                {"chunk_id": "c1", "text": "weak match"},
                {"chunk_id": "c2", "text": "strong match"},
            ]
        }
    )
    embedder = _FakeEmbedder(
        {
            "question": [1.0, 0.0, 0.0],
            "weak match": [0.6, 0.8, 0.0],
            "strong match": [1.0, 0.0, 0.0],
        }
    )
    result = answer_question("question", links, embedder, repo, similarity_threshold=0.0, limit=5)
    assert [hit.practice_reference for hit in result] == ["ACCESS-1b", "ACCESS-1a"]


def test_answer_question_respects_limit() -> None:
    links = [
        _link("ACCESS-1a", document_id="doc-1", chunk_id="c1"),
        _link("ACCESS-1b", document_id="doc-1", chunk_id="c2"),
    ]
    repo = _FakeVectorRepository(
        {
            "doc-1": [
                {"chunk_id": "c1", "text": "match one"},
                {"chunk_id": "c2", "text": "match two"},
            ]
        }
    )
    embedder = _FakeEmbedder(
        {
            "question": [1.0, 0.0, 0.0],
            "match one": [1.0, 0.0, 0.0],
            "match two": [1.0, 0.0, 0.0],
        }
    )
    result = answer_question("question", links, embedder, repo, similarity_threshold=0.0, limit=1)
    assert len(result) == 1
