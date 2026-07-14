from __future__ import annotations

import math

import pytest

from compliance_platform.ai.embeddings import (
    LocalHashingEmbedder,
    LocalSemanticEmbedder,
    get_embedder,
)
from compliance_platform.core.config import get_settings


def test_embed_returns_correct_dimensions() -> None:
    embedder = LocalHashingEmbedder(n_features=256)
    vectors = embedder.embed(["hello world", "a different sentence entirely"])
    assert len(vectors) == 2
    assert all(len(v) == 256 for v in vectors)


def test_embed_empty_list_returns_empty() -> None:
    embedder = LocalHashingEmbedder()
    assert embedder.embed([]) == []


def test_vectors_are_comparable_across_independent_calls() -> None:
    """The entire reason ADR-0006 chose HashingVectorizer over
    TfidfVectorizer: two independent embed() calls, with no shared fit
    step and no guarantee a second document exists yet, must still be
    comparable in the same vector space.
    """
    embedder = LocalHashingEmbedder(n_features=512)
    v1 = embedder.embed(["access control policy for critical systems"])[0]
    v2 = embedder.embed(["access control policy for critical systems"])[0]
    assert v1 == v2


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def test_similar_text_is_closer_than_dissimilar_text() -> None:
    embedder = LocalHashingEmbedder(n_features=1024)
    base, similar, different = embedder.embed(
        [
            "multi factor authentication is required for remote access",
            "remote access requires multi factor authentication",
            "quarterly financial statements were filed with the regulator",
        ]
    )
    assert _cosine(base, similar) > _cosine(base, different)


def test_get_embedder_factory_returns_hashing_backend() -> None:
    embedder = get_embedder("hashing_local", n_features=128)
    assert embedder.backend_name == "hashing_local"
    assert embedder.dimensions == 128


def test_get_embedder_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError):
        get_embedder("some_unknown_backend")


# --- LocalSemanticEmbedder (ADR-0008) ---
# Uses a module-scoped fixture so the ONNX model loads once per test
# session, not once per test — model loading (even from a warm local
# cache) is not free.


@pytest.fixture(scope="module")
def semantic_embedder() -> LocalSemanticEmbedder:
    settings = get_settings()
    return LocalSemanticEmbedder(
        model_name=settings.embedding_model_name, cache_dir=settings.embedding_model_cache_dir
    )


def test_semantic_embedder_returns_correct_dimensions(
    semantic_embedder: LocalSemanticEmbedder,
) -> None:
    vectors = semantic_embedder.embed(["hello world", "a different sentence entirely"])
    assert len(vectors) == 2
    assert all(len(v) == 384 for v in vectors)


def test_semantic_embedder_empty_list_returns_empty(
    semantic_embedder: LocalSemanticEmbedder,
) -> None:
    assert semantic_embedder.embed([]) == []


def test_semantic_vectors_are_comparable_across_independent_calls(
    semantic_embedder: LocalSemanticEmbedder,
) -> None:
    v1 = semantic_embedder.embed(["access control policy for critical systems"])[0]
    v2 = semantic_embedder.embed(["access control policy for critical systems"])[0]
    assert v1 == pytest.approx(v2)


def test_semantic_embedder_captures_meaning_not_just_word_overlap(
    semantic_embedder: LocalSemanticEmbedder,
) -> None:
    """The exact property the hashing backend (ADR-0006) could not
    provide, and the reason ADR-0008 exists: a sentence sharing almost
    no exact words but the same meaning as the base sentence must score
    more similar than a sentence sharing a literal word with the base
    but describing something unrelated.
    """
    base = semantic_embedder.embed(["multi factor authentication is required for remote access"])[
        0
    ]
    same_meaning_different_words, literal_overlap_different_meaning = semantic_embedder.embed(
        [
            "two factor login is mandatory when connecting remotely",
            "the quarterly report on remote work policy was filed with HR",
        ]
    )
    assert _cosine(base, same_meaning_different_words) > _cosine(
        base, literal_overlap_different_meaning
    )


def test_get_embedder_factory_returns_semantic_backend_by_name() -> None:
    embedder = get_embedder("semantic_local_onnx")
    assert embedder.backend_name == "semantic_local_onnx"
    assert embedder.dimensions == 384
