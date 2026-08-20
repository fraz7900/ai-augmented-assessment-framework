"""Stage 5: end-to-end retrieval-eval runner.

Not part of the application -- for a human to run directly, same
convention as backend/scripts/benchmark_scalability.py. Run manually:

    cd backend && source .venv/bin/activate
    python -m eval.run_eval

Wires together every earlier stage against the CURRENT labels file
(backend/eval/labels/labels.template.yaml, unless --labels overrides
it) exactly as it stands on disk:

  1. load_and_validate (Stage 1) -- refuses to run against a labels
     file that doesn't resolve against real documents.
  2. retrieval/runner.py (Stage 2) -- builds one isolated eval vector
     store, at the default embedding_backend/chunk_target_chars.
  3. retrieval/query.py (Stage 2) -- one query per labeled practice.
  4. metrics/scoring.py (Stage 3) -- recall@k / MRR / nDCG for that run.
  5. ablation/grid.py (Stage 4) -- reruns 2-4 across the embedder x
     chunking grid.

Writes a JSON snapshot to backend/eval/results/ and prints a report to
stdout. Generates no labels and judges no result: every number below is
mechanically computed from whatever labels.template.yaml already
contains -- see the SEED SET banner this script prints whenever the
label set is too small to support a real benchmark claim (today: the
two rows the Stage 1 template ships are marked EXAMPLE ONLY in that
file, not even preliminary real judgments -- see labels.template.yaml's
own header comment).
"""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from compliance_platform.ai.embeddings import Embedder, get_embedder
from compliance_platform.core.config import Settings
from compliance_platform.repositories.vector_repository import VectorRepository
from eval.ablation.grid import AblationConfig, AblationResult, default_grid, run_grid
from eval.labels.loader import load_and_validate
from eval.labels.schema import RelevanceLabel
from eval.metrics.scoring import AggregateScore, score_query_results
from eval.retrieval.query import run_queries
from eval.retrieval.runner import build_eval_index, corpus_doc_refs

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LABELS_PATH = REPO_ROOT / "backend" / "eval" / "labels" / "labels.template.yaml"
DEFAULT_RESULTS_DIR = REPO_ROOT / "backend" / "eval" / "results"
FRAMEWORK_MAPPING_DIR = REPO_ROOT / "framework_mapping"
K_VALUES = [1, 3, 5]

# Below this many unique labeled (practice_id, framework) pairs, a
# recall@k/MRR/nDCG number is noise, not a benchmark result -- 10 is a
# judgment call, not a measured cutoff (this harness is the thing that
# would produce one), picked because a handful of queries can be swung
# entirely by one easy or one unlucky case. Flagged honestly rather
# than hidden either way: this script always reports the real query
# count next to every number, banner or not.
SEED_SET_THRESHOLD = 10
SEED_SET_BANNER = "SEED SET - illustrative only, not the full labeled benchmark"


def _real_embedder_factory(config: AblationConfig) -> Embedder:
    kwargs: dict[str, object] = {"cache_dir": REPO_ROOT / "data" / "processed" / "model_cache"}
    if config.embedding_backend == "hashing_local":
        kwargs["n_features"] = config.dimensions
    return get_embedder(config.embedding_backend, **kwargs)


def run_default(
    labels: list[RelevanceLabel], settings: Settings, embedder: Embedder, vector_store_dir: Path
) -> tuple[AggregateScore, int]:
    vector_repository = VectorRepository(vector_store_dir, dimensions=settings.embedding_dimensions)
    doc_refs = corpus_doc_refs(REPO_ROOT, labels)
    indexed = build_eval_index(settings, vector_repository, embedder, REPO_ROOT, doc_refs)
    doc_ref_to_document_id = {doc.doc_ref: doc.document_id for doc in indexed}
    document_ids = [doc.document_id for doc in indexed]

    query_results = run_queries(
        labels=labels,
        embedder=embedder,
        vector_repository=vector_repository,
        document_ids=document_ids,
        framework_mapping_dir=FRAMEWORK_MAPPING_DIR,
        limit=max(K_VALUES),
    )
    score = score_query_results(query_results, labels, doc_ref_to_document_id, K_VALUES)
    return score, len(indexed)


def _score_to_dict(score: AggregateScore) -> dict:
    return {
        "num_queries": score.num_queries,
        "mean_recall_at_k": score.mean_recall_at_k,
        "mean_ndcg_at_k": score.mean_ndcg_at_k,
        "mean_reciprocal_rank": score.mean_reciprocal_rank,
        "per_query": [
            {
                "practice_id": q.practice_id,
                "framework": q.framework,
                "num_gold_spans": q.num_gold_spans,
                "num_retrieved": q.num_retrieved,
                "recall_at_k": q.recall_at_k,
                "ndcg_at_k": q.ndcg_at_k,
                "reciprocal_rank": q.reciprocal_rank,
            }
            for q in score.per_query
        ],
    }


def format_report(
    labels: list[RelevanceLabel],
    num_indexed_documents: int,
    default_score: AggregateScore,
    ablation_results: list[AblationResult],
    is_seed_set: bool,
) -> str:
    lines: list[str] = []
    if is_seed_set:
        lines.append(f"*** {SEED_SET_BANNER} ***")
        lines.append(
            f"Only {default_score.num_queries} unique labeled (practice_id, framework) pair(s) "
            f"below SEED_SET_THRESHOLD={SEED_SET_THRESHOLD} -- see labels.template.yaml, whose two "
            "rows are marked EXAMPLE ONLY, not verified relevance judgments."
        )
        lines.append("")
    lines.append(f"Labels file rows: {len(labels)}; unique queries: {default_score.num_queries}")
    lines.append(f"Eval corpus documents indexed: {num_indexed_documents}")
    lines.append("")
    lines.append("-- Default run (semantic_local_onnx, chunk_target_chars=1200) --")
    lines.append(f"mean MRR: {default_score.mean_reciprocal_rank:.4f}")
    for k in K_VALUES:
        lines.append(
            f"  recall@{k}: {default_score.mean_recall_at_k[k]:.4f}   "
            f"nDCG@{k}: {default_score.mean_ndcg_at_k[k]:.4f}"
        )
    lines.append("")
    lines.append("-- Ablation grid (Stage 4) --")
    for result in ablation_results:
        lines.append(
            f"{result.config.name}: n={result.score.num_queries} "
            f"MRR={result.score.mean_reciprocal_rank:.4f} "
            f"recall@{K_VALUES[-1]}={result.score.mean_recall_at_k[K_VALUES[-1]]:.4f} "
            f"nDCG@{K_VALUES[-1]}={result.score.mean_ndcg_at_k[K_VALUES[-1]]:.4f}"
        )
    if is_seed_set:
        lines.append("")
        lines.append(f"*** {SEED_SET_BANNER} ***")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS_PATH)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    args = parser.parse_args()

    labels = load_and_validate(args.labels, REPO_ROOT)
    num_unique_queries = len({(label.practice_id, label.framework) for label in labels})
    is_seed_set = num_unique_queries < SEED_SET_THRESHOLD

    with tempfile.TemporaryDirectory(prefix="eval-default-run-") as tmp_dir:
        default_settings = Settings(vector_store_dir=Path(tmp_dir) / "lancedb")
        default_embedder = _real_embedder_factory(
            AblationConfig(
                name="default",
                embedding_backend=default_settings.embedding_backend,
                dimensions=default_settings.embedding_dimensions,
                chunk_target_chars=default_settings.chunk_target_chars,
                chunk_overlap_chars=default_settings.chunk_overlap_chars,
            )
        )
        default_score, num_indexed = run_default(
            labels, default_settings, default_embedder, default_settings.vector_store_dir
        )

    ablation_results = run_grid(
        configs=default_grid(),
        labels=labels,
        repo_root=REPO_ROOT,
        framework_mapping_dir=FRAMEWORK_MAPPING_DIR,
        k_values=K_VALUES,
        embedder_factory=_real_embedder_factory,
    )

    report = format_report(labels, num_indexed, default_score, ablation_results, is_seed_set)
    print(report)

    args.results_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.results_dir / "seed_run_results.json"
    output_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "labels_path": str(args.labels.relative_to(REPO_ROOT)),
                "is_seed_set": is_seed_set,
                "seed_set_banner": SEED_SET_BANNER if is_seed_set else None,
                "num_label_rows": len(labels),
                "num_indexed_documents": num_indexed,
                "k_values": K_VALUES,
                "default_run": {
                    "embedding_backend": default_settings.embedding_backend,
                    "chunk_target_chars": default_settings.chunk_target_chars,
                    "chunk_overlap_chars": default_settings.chunk_overlap_chars,
                    "score": _score_to_dict(default_score),
                },
                "ablation": [
                    {
                        "config": {
                            "name": r.config.name,
                            "embedding_backend": r.config.embedding_backend,
                            "chunk_target_chars": r.config.chunk_target_chars,
                            "chunk_overlap_chars": r.config.chunk_overlap_chars,
                        },
                        "score": _score_to_dict(r.score),
                    }
                    for r in ablation_results
                ],
            },
            indent=2,
        )
        + "\n"
    )
    print(f"\nWrote {output_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
