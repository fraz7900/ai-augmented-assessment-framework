from __future__ import annotations

import math

import pytest

from compliance_platform.ai.embeddings import LocalHashingEmbedder, get_embedder


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
