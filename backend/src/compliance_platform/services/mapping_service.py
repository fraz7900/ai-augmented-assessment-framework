"""Framework mapping engine (Sprint 5): retrieval-based AI-proposed
evidence linking.

Given an assessment, proposes evidence links for practices not yet
covered, by semantically matching each uncovered practice's text
against chunks from documents already associated with the assessment
(via any existing evidence link, of any review status except
rejected — see services/assessment_service.py.propose_mappings). The
whole global vector store is deliberately NOT searched: an assessment
should only be offered evidence from documents someone has already
connected to it, not evidence uploaded for an unrelated assessment.

This is explicitly retrieval-only, not generative: no LLM produces a
claim or a quote here, so the evidence-extraction skill's
citation-verification-of-a-generated-quote step does not apply in this
sprint — the "citation" is the literal retrieved chunk itself, not a
possibly-inexact paraphrase of it. See ADR-0011 for why this is the
current, honest scope, and what a future generative extraction layer
(via Ollama) would add on top of this, not instead of it.
"""

from __future__ import annotations

from typing import Protocol

from compliance_platform.ai.embeddings import Embedder
from compliance_platform.models.framework import FrameworkDefinition


class VectorRepositoryProtocol(Protocol):
    def search_within_documents(
        self, query_vector: list[float], document_ids: list[str], limit: int = 5
    ) -> list[dict]: ...


def distance_to_confidence(distance: float) -> float:
    """Converts LanceDB's L2 distance (over L2-normalized vectors, see
    ai/embeddings.py) to an approximate cosine similarity in [0, 1]: for
    unit vectors, ||a-b||^2 = 2 - 2*cos_sim, so cos_sim = 1 - distance^2/2.
    Clamped defensively. This is a similarity heuristic, not a
    calibrated probability — the evidence-extraction skill requires
    confidence to come from retrieval signal, never a model's
    self-reported confidence, and this is that signal, nothing more.
    """
    cosine_similarity = 1.0 - (distance**2) / 2.0
    return max(0.0, min(1.0, cosine_similarity))


class MappingProposal:
    """Return-value shape for find_mapping_candidates, not a persisted
    model — services/assessment_service.py turns these into real
    EvidenceLink rows. Kept separate so this module has no dependency on
    SQLModel or the database (repositories/README.md's boundary).
    """

    __slots__ = ("practice_id", "document_id", "chunk_id", "confidence", "chunk_text")

    def __init__(
        self,
        practice_id: str,
        document_id: str,
        chunk_id: str,
        confidence: float,
        chunk_text: str,
    ) -> None:
        self.practice_id = practice_id
        self.document_id = document_id
        self.chunk_id = chunk_id
        self.confidence = confidence
        self.chunk_text = chunk_text


def find_mapping_candidates(
    framework: FrameworkDefinition,
    document_ids: list[str],
    already_covered_practice_ids: set[str],
    embedder: Embedder,
    vector_repository: VectorRepositoryProtocol,
    similarity_threshold: float,
    candidates_per_practice: int,
) -> list[MappingProposal]:
    """Pure function over its inputs (no assessment/repository lookups),
    so this is unit-testable without a real database or a real
    assessment — see services/tests/test_mapping_service.py.

    Practice text for every not-yet-covered practice in the framework's
    populated domains is embedded in a single batched call (not one
    embed() call per practice) before any retrieval happens — cheap and
    avoids N separate model invocations for what is otherwise an
    embarrassingly parallel batch operation.
    """
    if not document_ids:
        return []

    target_practices = [
        practice
        for domain in framework.domains
        if domain.practices_populated
        for practice in domain.all_practices()
        if practice.id not in already_covered_practice_ids
    ]
    if not target_practices:
        return []

    practice_vectors = embedder.embed([practice.text for practice in target_practices])

    proposals: list[MappingProposal] = []
    for practice, vector in zip(target_practices, practice_vectors, strict=True):
        results = vector_repository.search_within_documents(
            vector, document_ids, limit=candidates_per_practice
        )
        for result in results:
            confidence = distance_to_confidence(result["_distance"])
            if confidence < similarity_threshold:
                continue
            proposals.append(
                MappingProposal(
                    practice_id=practice.id,
                    document_id=result["document_id"],
                    chunk_id=result["chunk_id"],
                    confidence=confidence,
                    chunk_text=result["text"],
                )
            )
    return proposals
