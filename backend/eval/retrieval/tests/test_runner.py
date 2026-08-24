"""Tests for the Stage 2 index builder.

build_eval_index is exercised against a REAL (temp-dir) VectorRepository
-- the whole point is confirming chunks actually land in an isolated
LanceDB store via the real IngestionService, not a fake standing in for
it -- but with a fake Embedder, so these tests stay fast and need no
network access or the real ONNX model (see ai/tests/test_embeddings.py
for coverage of the real backends themselves; that is not this
module's job).
"""

from __future__ import annotations

from pathlib import Path

from compliance_platform.core.config import Settings
from compliance_platform.repositories.vector_repository import VectorRepository
from eval.labels.schema import RelevanceLabel
from eval.retrieval.runner import build_eval_index, corpus_doc_refs

REPO_ROOT = Path(__file__).resolve().parents[4]


class _FakeEmbedder:
    backend_name = "fake"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t)), 0.0] for t in texts]


def _settings(vector_store_dir: Path) -> Settings:
    return Settings(
        vector_store_dir=vector_store_dir,
        chunk_target_chars=200,
        chunk_overlap_chars=20,
        chunk_min_chars=5,
    )


def test_corpus_doc_refs_unions_corpus_dir_and_label_doc_refs(tmp_path: Path) -> None:
    fake_repo_root = tmp_path
    corpus_dir = fake_repo_root / "backend" / "eval" / "corpus"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "a.txt").write_text("a")
    (corpus_dir / "b.txt").write_text("b")
    (corpus_dir / "not_a_txt_file.md").write_text("ignored")

    labels = [
        RelevanceLabel("P-1", "f", "data/sample_evidence/x.md", 0, 1),
        # A label pointing back into the eval corpus itself must not be
        # double-counted against the glob's own copy of the same path.
        RelevanceLabel("P-2", "f", "backend/eval/corpus/a.txt", 0, 1),
    ]

    refs = corpus_doc_refs(fake_repo_root, labels)

    assert refs == [
        "backend/eval/corpus/a.txt",
        "backend/eval/corpus/b.txt",
        "data/sample_evidence/x.md",
    ]


def test_corpus_doc_refs_with_no_labels_is_just_the_corpus_dir(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "backend" / "eval" / "corpus"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "only.txt").write_text("x")

    assert corpus_doc_refs(tmp_path, []) == ["backend/eval/corpus/only.txt"]


def test_build_eval_index_ingests_every_doc_ref_into_the_isolated_store(tmp_path: Path) -> None:
    fake_repo_root = tmp_path / "repo"
    doc_dir = fake_repo_root / "docs"
    doc_dir.mkdir(parents=True)
    (doc_dir / "one.txt").write_text(
        "This synthetic policy document has more than enough content to form a chunk."
    )
    (doc_dir / "two.txt").write_text(
        "A second synthetic document, distinct text, also long enough to chunk cleanly."
    )

    settings = _settings(tmp_path / "lancedb")
    vector_repository = VectorRepository(settings.vector_store_dir, dimensions=2)
    embedder = _FakeEmbedder()

    indexed = build_eval_index(
        settings=settings,
        vector_repository=vector_repository,
        embedder=embedder,
        repo_root=fake_repo_root,
        doc_refs=["docs/one.txt", "docs/two.txt"],
    )

    assert [doc.doc_ref for doc in indexed] == ["docs/one.txt", "docs/two.txt"]
    document_ids = {doc.document_id for doc in indexed}
    assert len(document_ids) == 2  # each ingest gets its own document_id

    for doc in indexed:
        chunks = vector_repository.chunks_for_document(doc.document_id)
        assert len(chunks) > 0
        assert all(chunk["document_id"] == doc.document_id for chunk in chunks)


def test_build_eval_index_never_touches_the_product_vector_store(tmp_path: Path) -> None:
    # Confirms this module writes only to the caller-supplied store dir
    # -- the isolation invariant backend/eval/README.md and
    # backend/eval/CLAUDE.md both require -- by pointing settings at a
    # throwaway temp dir and checking nothing appears under the real
    # repo's data/processed/lancedb as a side effect.
    product_store = REPO_ROOT / "data" / "processed" / "lancedb"
    before = product_store.exists() and sorted(product_store.rglob("*"))

    fake_repo_root = tmp_path / "repo"
    doc_dir = fake_repo_root / "docs"
    doc_dir.mkdir(parents=True)
    (doc_dir / "one.txt").write_text("Enough synthetic content here to survive chunking cleanly.")

    settings = _settings(tmp_path / "lancedb")
    vector_repository = VectorRepository(settings.vector_store_dir, dimensions=2)
    build_eval_index(
        settings=settings,
        vector_repository=vector_repository,
        embedder=_FakeEmbedder(),
        repo_root=fake_repo_root,
        doc_refs=["docs/one.txt"],
    )

    after = product_store.exists() and sorted(product_store.rglob("*"))
    assert before == after
