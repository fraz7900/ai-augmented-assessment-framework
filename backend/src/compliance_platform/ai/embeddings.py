"""Local embedding generation.

Default backend as of ADR-0008 is a small local ONNX semantic embedding
model (fastembed / BAAI/bge-small-en-v1.5). The original ADR-0006
hashed-vectorizer backend remains available (`hashing_local`) as a
zero-network-ever, zero-dependency-weight fallback, but is no longer the
default — see ADR-0008 for why. This module's job is to keep the
backend swappable without touching services/ingestion_service.py or
repositories/vector_repository.py, both of which depend only on the
Embedder protocol below.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from fastembed import TextEmbedding
from sklearn.feature_extraction.text import HashingVectorizer


@runtime_checkable
class Embedder(Protocol):
    """Interface every embedding backend must satisfy.

    No fit() method by design: services/ingestion_service.py calls
    embed() once per ingested document, independently, with no
    guarantee another document exists yet. A backend that requires
    fitting a shared vocabulary across the whole corpus before it
    produces comparable vectors does not satisfy this interface — see
    ADR-0006's rejection of TfidfVectorizer for exactly this reason,
    which applies equally to any future backend choice.

    See the privacy-protection skill: any future implementation of this
    protocol that sends evidence content to a cloud API must make that
    explicit and opt-in at the call site, never silently. Downloading
    public, non-evidence model weights on first use (see
    LocalSemanticEmbedder) is a different category of network access and
    does not violate this rule — see ADR-0008.
    """

    def embed(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def backend_name(self) -> str: ...

    @property
    def dimensions(self) -> int: ...


class LocalHashingEmbedder:
    """Fully local, zero-network-ever, no-fit embedding backend (ADR-0006).

    Terms are mapped into a fixed-size hash space, so any two documents
    embedded independently, at any time (including before any other
    document has ever been ingested), produce directly comparable
    vectors. Captures lexical similarity only, not semantic similarity
    — see ADR-0008 for why this is no longer the default. Kept available
    as the lightest-weight option with the strongest possible network
    guarantee (not even a one-time model download).
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


class LocalSemanticEmbedder:
    """Local semantic embedding backend using a small ONNX sentence
    embedding model, via fastembed. Default as of ADR-0008.

    Inference is fully local (ONNX Runtime, no PyTorch, no CUDA) and no
    evidence content is ever sent over the network. Model weights
    (public, not evidence) are downloaded once on first use and cached
    at `cache_dir` thereafter — see ADR-0008 for why this one-time,
    non-evidence download is compatible with the project's local-first
    privacy constraint.

    No fit() method, same as LocalHashingEmbedder and for the same
    reason: a pretrained model produces directly comparable vectors
    across independent embed() calls with no shared-corpus step
    required, which is the load-bearing correctness property ADR-0006
    identified and which must hold for any backend behind this
    interface.
    """

    _DIMENSIONS = 384  # BAAI/bge-small-en-v1.5's actual output width

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        cache_dir: Path | None = None,
    ) -> None:
        kwargs: dict[str, str] = {"model_name": model_name}
        if cache_dir is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)
            kwargs["cache_dir"] = str(cache_dir)
        self._model = TextEmbedding(**kwargs)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [vector.tolist() for vector in self._model.embed(texts)]

    @property
    def backend_name(self) -> str:
        return "semantic_local_onnx"

    @property
    def dimensions(self) -> int:
        return self._DIMENSIONS


def get_embedder(
    backend: str,
    *,
    n_features: int = 4096,
    model_name: str = "BAAI/bge-small-en-v1.5",
    cache_dir: Path | None = None,
) -> Embedder:
    """Factory. The single place a new embedding backend gets registered."""
    if backend == "hashing_local":
        return LocalHashingEmbedder(n_features=n_features)
    if backend == "semantic_local_onnx":
        return LocalSemanticEmbedder(model_name=model_name, cache_dir=cache_dir)
    raise ValueError(f"Unknown embedding backend: {backend!r}")
