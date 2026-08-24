"""Tests for the Stage 4 ablation grid.

Uses a fake embedder_factory (deterministic, hash-of-text vectors) so
these tests stay fast and need no network access or the real ONNX
model -- run_eval.py (Stage 5) is what exercises the real
`compliance_platform.ai.embeddings.get_embedder` backends end to end;
that is not this module's job. Each config still runs through the real
IngestionService and a real (temp-dir) VectorRepository, same as
retrieval/tests/test_runner.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eval.ablation.grid import AblationConfig, default_grid, run_ablation_config, run_grid
from eval.labels.schema import RelevanceLabel

REPO_ROOT = Path(__file__).resolve().parents[4]
FRAMEWORK_MAPPING_DIR = REPO_ROOT / "framework_mapping"


class _FakeEmbedder:
    """Deterministic, dependency-free stand-in: embeds each text to a
    2-D vector of (length, count of 'security'), so texts that share
    the word chosen by the corpus fixture below cluster together the
    same way a real semantic embedder would for a toy case, without
    needing one.
    """

    backend_name = "fake"

    def __init__(self, dimensions: int = 2) -> None:
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t)), float(t.lower().count("security"))] for t in texts]


def _fake_embedder_factory(config: AblationConfig):
    return _FakeEmbedder(dimensions=config.dimensions)


@pytest.fixture()
def fake_corpus(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    corpus_dir = repo_root / "backend" / "eval" / "corpus"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "policy.txt").write_text(
        "This synthetic security policy describes access control requirements "
        "for the organization, including multi-factor authentication for all "
        "privileged accounts and periodic review of security access logs."
    )
    return repo_root


def test_default_grid_covers_every_backend_and_chunk_config_combination() -> None:
    configs = default_grid()

    assert len(configs) == 4
    names = {c.name for c in configs}
    assert len(names) == 4  # every combination gets a distinct name
    assert {c.embedding_backend for c in configs} == {"semantic_local_onnx", "hashing_local"}


def test_run_ablation_config_produces_a_score_for_a_labeled_practice(
    fake_corpus: Path, tmp_path: Path
) -> None:
    labels = [
        RelevanceLabel(
            practice_id="ACCESS-1h",
            framework="c2m2_v2_1",
            doc_ref="backend/eval/corpus/policy.txt",
            char_start=0,
            char_end=40,
        )
    ]
    config = AblationConfig(
        name="fake_config",
        embedding_backend="fake",
        dimensions=2,
        chunk_target_chars=100,
        chunk_overlap_chars=10,
    )

    result = run_ablation_config(
        config=config,
        labels=labels,
        repo_root=fake_corpus,
        framework_mapping_dir=FRAMEWORK_MAPPING_DIR,
        k_values=[1, 3],
        embedder_factory=_fake_embedder_factory,
        vector_store_dir=tmp_path / "lancedb",
    )

    assert result.config is config
    assert result.score.num_queries == 1
    assert set(result.score.mean_recall_at_k) == {1, 3}


def test_run_grid_runs_every_config_in_its_own_isolated_store(
    fake_corpus: Path, tmp_path: Path
) -> None:
    labels = [
        RelevanceLabel(
            practice_id="ACCESS-1h",
            framework="c2m2_v2_1",
            doc_ref="backend/eval/corpus/policy.txt",
            char_start=0,
            char_end=40,
        )
    ]
    configs = [
        AblationConfig("a", "fake", 2, 100, 10),
        AblationConfig("b", "fake", 2, 60, 5),
    ]

    results = run_grid(
        configs=configs,
        labels=labels,
        repo_root=fake_corpus,
        framework_mapping_dir=FRAMEWORK_MAPPING_DIR,
        k_values=[1],
        embedder_factory=_fake_embedder_factory,
    )

    assert [r.config.name for r in results] == ["a", "b"]
    assert all(r.score.num_queries == 1 for r in results)
