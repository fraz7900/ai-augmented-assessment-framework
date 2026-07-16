"""Retrieval-only Q&A over an assessment's reviewed evidence (Sprint 8).

Given a free-text question, ranks the assessment's own reviewed
(accepted/edited) evidence links by similarity to the question and
returns them as the answer — no generated prose, no LLM in the loop.
This mirrors Sprint 5's mapping engine (ADR-0011): nothing here is
generated, so there is nothing to hallucinate, and no
citation-verification step is needed because the "answer" IS the
literal, already human-reviewed evidence text. See ADR-0014 for why
Sprint 8 stayed retrieval-only (a sudo-free Ollama path was confirmed
technically viable this time, unlike Sprint 5, but was deliberately not
taken) and for the empirical basis of the similarity threshold.
"""

from __future__ import annotations

from typing import Protocol

from compliance_platform.ai.embeddings import Embedder
from compliance_platform.models.assessment import EvidenceLink, EvidenceReviewStatus

_ANSWERABLE_STATUSES = (EvidenceReviewStatus.ACCEPTED, EvidenceReviewStatus.EDITED)


class VectorRepositoryProtocol(Protocol):
    def chunks_for_document(self, document_id: str) -> list[dict]: ...


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Direct dot product, not distance_to_confidence's L2-distance
    conversion — that formula translates LanceDB's returned `_distance`
    metric; here, both vectors come straight from Embedder.embed(), so
    a direct cosine (dot product, since embeddings are L2-normalized —
    see ai/embeddings.py) is the natural metric. Clamped defensively,
    same reasoning as distance_to_confidence's clamp.
    """
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return max(0.0, min(1.0, dot))


class ChatHit:
    """One ranked evidence-link result — a return-value shape, not a
    persisted model, mirroring MappingProposal's role in
    mapping_service.py.
    """

    __slots__ = ("practice_reference", "document_id", "chunk_id", "similarity", "chunk_text")

    def __init__(
        self,
        practice_reference: str,
        document_id: str,
        chunk_id: str,
        similarity: float,
        chunk_text: str,
    ) -> None:
        self.practice_reference = practice_reference
        self.document_id = document_id
        self.chunk_id = chunk_id
        self.similarity = similarity
        self.chunk_text = chunk_text


def answer_question(
    question: str,
    evidence_links: list[EvidenceLink],
    embedder: Embedder,
    vector_repository: VectorRepositoryProtocol,
    similarity_threshold: float,
    limit: int,
) -> list[ChatHit]:
    """Pure function over its inputs (no assessment-repository lookups),
    same testability shape as mapping_service.find_mapping_candidates.

    Only ACCEPTED/EDITED links with a concrete chunk_id are searchable:
    a link with no chunk_id (a coarse, document-level manual link) has
    no specific source text to compare a question against or quote
    back — see ADR-0014's disclosed limitation. Ranking is computed
    directly over this assessment's own reviewed evidence chunks, not
    via a global/document-scoped vector-index search, so a result can
    never be evidence this assessment hasn't actually had reviewed —
    the same document-scoping discipline ADR-0011 established for
    mapping, applied here one level stricter (evidence-link-scoped, not
    just document-scoped).
    """
    if not question.strip():
        return []

    reviewed = [
        link
        for link in evidence_links
        if link.review_status in _ANSWERABLE_STATUSES and link.chunk_id is not None
    ]
    if not reviewed:
        return []

    chunk_text_by_key: dict[tuple[str, str], str] = {}
    for document_id in {link.document_id for link in reviewed}:
        for row in vector_repository.chunks_for_document(document_id):
            chunk_text_by_key[(document_id, row["chunk_id"])] = row["text"]

    candidates = [
        link for link in reviewed if (link.document_id, link.chunk_id) in chunk_text_by_key
    ]
    if not candidates:
        return []

    texts = [chunk_text_by_key[(link.document_id, link.chunk_id)] for link in candidates]
    vectors = embedder.embed([question, *texts])
    question_vector, chunk_vectors = vectors[0], vectors[1:]

    hits = [
        ChatHit(
            practice_reference=link.practice_reference,
            document_id=link.document_id,
            chunk_id=link.chunk_id,
            similarity=cosine_similarity(question_vector, chunk_vector),
            chunk_text=chunk_text_by_key[(link.document_id, link.chunk_id)],
        )
        for link, chunk_vector in zip(candidates, chunk_vectors, strict=True)
    ]
    hits = [hit for hit in hits if hit.similarity >= similarity_threshold]
    hits.sort(key=lambda hit: hit.similarity, reverse=True)
    return hits[:limit]
