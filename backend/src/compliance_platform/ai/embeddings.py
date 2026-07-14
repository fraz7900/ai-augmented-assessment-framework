"""Local embedding generation.

See ADR-0006: the MVP default is a classical hashed vectorizer, not a
neural model, for dependency-weight and environment reasons that are
explicitly interim. This module's job is to make the backend swappable
without touching services/ingestion_service.py or
repositories/vector_repository.py, both of which depend only on the
Embedder protocol below.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sklearn.feature_extraction.text import HashingVectorizer


@runtime_checkable
class Embedder(Protocol):
    """Interface every embedding backend must satisfy.

    No fit() method by design: services/ingestion_service.py calls
    embed() once per ingested document, independently, with no
    guarantee another document exists yet. A backend that requires
    fitting a shared vocabulary across the whole corpus before it
    produces comparable vectors does not satisfy this interface — see
    ADR-0006's rejection of TfidfVectorizer for exactly this reason.

    See the privacy-protection skill: any future implementation of this
    protocol that calls a cloud API must make that explicit and opt-in
    at the call site, never silently.
    """

    def embed(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def backend_name(self) -> str: ...

    @property
    def dimensions(self) -> int: ...


class LocalHashingEmbedder:
    """Fully local, no-network, no-fit embedding backend (ADR-0006).

    Terms are mapped into a fixed-size hash space, so any two documents
    embedded independently, at any time (including before any other
    document has ever been ingested), produce directly comparable
    vectors. This is the property TfidfVectorizer does not have and
    HashingVectorizer does, which is the whole reason it was chosen —
    see ADR-0006 Rationale #2.
    """

    def __init__(self, n_features: int = 4096) -> None:
        self._n_features = n_features
        self._vectorizer = HashingVectorizer(
            n_features=n_features,
            norm="l2",
            alternate_sign=False,
            stop_words="english",
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        matrix = self._vectorizer.transform(texts)
        return matrix.toarray().astype("float32").tolist()

    @property
    def backend_name(self) -> str:
        return "hashing_local"

    @property
    def dimensions(self) -> int:
        return self._n_features


def get_embedder(backend: str = "hashing_local", n_features: int = 4096) -> Embedder:
    """Factory. The single place a future neural backend gets registered,
    per ADR-0006's stated upgrade path (Ollama or sentence-transformers).
    """
    if backend == "hashing_local":
        return LocalHashingEmbedder(n_features=n_features)
    raise ValueError(f"Unknown embedding backend: {backend!r}")
