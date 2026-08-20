"""Stage 2: turns each labeled practice into one retrieval query.

A query's text is the practice's own definition text -- the same
signal services/mapping_service.py::find_mapping_candidates embeds for
the product's own AI-proposed mappings (ADR-0011) -- so this harness
measures the retrieval step the product actually depends on, not a
different, easier-to-answer query it invented for itself.

Deliberately NOT a thin wrapper around find_mapping_candidates: that
function applies `mapping_similarity_threshold` and
`candidates_per_practice` (default 1), both product-facing decisions
about when to *show* a candidate to a reviewer. This harness needs the
raw, unfiltered ranked list -- recall@k/MRR/nDCG are meaningless over a
list that has already been cut down to one result before they see it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from compliance_platform.ai.embeddings import Embedder
from compliance_platform.models.framework import FrameworkDefinition, Practice
from compliance_platform.repositories.vector_repository import VectorRepository
from compliance_platform.services.framework_loader import load_framework_file
from eval.labels.schema import RelevanceLabel


class PracticeNotFoundError(ValueError):
    """A label names a practice_id that does not exist in the
    framework's own YAML -- a labelling typo, not a harness bug."""


@dataclass(frozen=True)
class RankedChunk:
    chunk_id: str
    document_id: str
    char_start: int
    char_end: int
    distance: float


@dataclass(frozen=True)
class QueryResult:
    practice_id: str
    framework: str
    query_text: str
    ranked_chunks: list[RankedChunk]


def find_practice(framework_def: FrameworkDefinition, practice_id: str) -> Practice:
    for domain in framework_def.domains:
        for practice in domain.all_practices():
            if practice.id == practice_id:
                return practice
    raise PracticeNotFoundError(
        f"practice_id {practice_id!r} not found in framework {framework_def.name!r}"
    )


def run_queries(
    labels: list[RelevanceLabel],
    embedder: Embedder,
    vector_repository: VectorRepository,
    document_ids: list[str],
    framework_mapping_dir: Path,
    limit: int,
) -> list[QueryResult]:
    """One query per unique (practice_id, framework) pair in labels --
    not one per label row, since several gold spans can name the same
    practice (see labels.template.yaml's shape: several rows could
    legitimately share a practice_id). Searches across every indexed
    document_id, not just the ones a label happens to reference, so a
    chunk from a *different* document than the gold one can still be
    retrieved and correctly scored as not relevant by metrics/ranking.py
    -- the exact failure mode recall@k exists to catch.
    """
    unique_queries = sorted({(label.practice_id, label.framework) for label in labels})
    framework_cache: dict[str, FrameworkDefinition] = {}
    results: list[QueryResult] = []
    for practice_id, framework in unique_queries:
        if framework not in framework_cache:
            framework_cache[framework] = load_framework_file(
                framework_mapping_dir / f"{framework}.yaml"
            )
        practice = find_practice(framework_cache[framework], practice_id)
        vector = embedder.embed([practice.text])[0]
        raw = vector_repository.search_within_documents(vector, document_ids, limit=limit)
        ranked_chunks = [
            RankedChunk(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                char_start=row["char_start"],
                char_end=row["char_end"],
                distance=row["_distance"],
            )
            for row in raw
        ]
        results.append(
            QueryResult(
                practice_id=practice_id,
                framework=framework,
                query_text=practice.text,
                ranked_chunks=ranked_chunks,
            )
        )
    return results
