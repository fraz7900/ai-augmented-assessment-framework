"""Stage 4: compares retrieval quality across embedder backends
(ai/embeddings.py::get_embedder -- `semantic_local_onnx` vs
`hashing_local`, see ADR-0008) and chunking configurations
(Settings.chunk_target_chars/chunk_overlap_chars), against the same
label set and the same isolated corpus each time.

Each grid point builds its OWN eval index in its own temp vector store
(never sharing one across configs -- a shared store would mix chunks
produced under different chunk_target_chars values together, corrupting
every config's results) and reuses retrieval/runner.py + retrieval/
query.py + metrics/scoring.py exactly as a single default run does, so
Stage 4 measures real differences in retrieval behavior, not
differences in harness code paths.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from compliance_platform.ai.embeddings import Embedder
from compliance_platform.core.config import Settings
from compliance_platform.repositories.vector_repository import VectorRepository
from eval.labels.schema import RelevanceLabel
from eval.metrics.scoring import AggregateScore, score_query_results
from eval.retrieval.query import run_queries
from eval.retrieval.runner import build_eval_index, corpus_doc_refs

# 1200/150 matches Settings' own defaults (core/config.py); 600/75 is a
# smaller-chunk alternative at the same ~8:1 target:overlap ratio, to
# see whether finer-grained chunks change which practices retrieve well
# -- not chosen from any prior measurement, since this harness is the
# thing that would produce one.
DEFAULT_CHUNK_CONFIGS: tuple[tuple[int, int], ...] = ((1200, 150), (600, 75))
DEFAULT_EMBEDDING_BACKENDS: tuple[tuple[str, int], ...] = (
    ("semantic_local_onnx", 384),
    ("hashing_local", 4096),
)


@dataclass(frozen=True)
class AblationConfig:
    name: str
    embedding_backend: str
    dimensions: int
    chunk_target_chars: int
    chunk_overlap_chars: int


def default_grid(
    chunk_configs: tuple[tuple[int, int], ...] = DEFAULT_CHUNK_CONFIGS,
    embedding_backends: tuple[tuple[str, int], ...] = DEFAULT_EMBEDDING_BACKENDS,
) -> list[AblationConfig]:
    return [
        AblationConfig(
            name=f"{backend}_chunk{target}_overlap{overlap}",
            embedding_backend=backend,
            dimensions=dimensions,
            chunk_target_chars=target,
            chunk_overlap_chars=overlap,
        )
        for backend, dimensions in embedding_backends
        for target, overlap in chunk_configs
    ]


@dataclass(frozen=True)
class AblationResult:
    config: AblationConfig
    score: AggregateScore


def run_ablation_config(
    config: AblationConfig,
    labels: list[RelevanceLabel],
    repo_root: Path,
    framework_mapping_dir: Path,
    k_values: list[int],
    embedder_factory: Callable[[AblationConfig], Embedder],
    vector_store_dir: Path,
) -> AblationResult:
    settings = Settings(
        vector_store_dir=vector_store_dir,
        chunk_target_chars=config.chunk_target_chars,
        chunk_overlap_chars=config.chunk_overlap_chars,
        chunk_min_chars=min(40, config.chunk_target_chars),
    )
    vector_repository = VectorRepository(vector_store_dir, dimensions=config.dimensions)
    embedder = embedder_factory(config)

    doc_refs = corpus_doc_refs(repo_root, labels)
    indexed = build_eval_index(settings, vector_repository, embedder, repo_root, doc_refs)
    doc_ref_to_document_id = {doc.doc_ref: doc.document_id for doc in indexed}
    document_ids = [doc.document_id for doc in indexed]

    query_results = run_queries(
        labels=labels,
        embedder=embedder,
        vector_repository=vector_repository,
        document_ids=document_ids,
        framework_mapping_dir=framework_mapping_dir,
        limit=max(k_values),
    )
    score = score_query_results(query_results, labels, doc_ref_to_document_id, k_values)
    return AblationResult(config=config, score=score)


def run_grid(
    configs: list[AblationConfig],
    labels: list[RelevanceLabel],
    repo_root: Path,
    framework_mapping_dir: Path,
    k_values: list[int],
    embedder_factory: Callable[[AblationConfig], Embedder],
) -> list[AblationResult]:
    """Runs every config in its own throwaway temp vector store,
    cleaned up before the next config starts (see module docstring for
    why configs never share a store).
    """
    results: list[AblationResult] = []
    for config in configs:
        with tempfile.TemporaryDirectory(prefix=f"eval-ablation-{config.name}-") as tmp_dir:
            results.append(
                run_ablation_config(
                    config,
                    labels,
                    repo_root,
                    framework_mapping_dir,
                    k_values,
                    embedder_factory,
                    Path(tmp_dir) / "lancedb",
                )
            )
    return results
