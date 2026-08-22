"""Stage 2: builds an isolated evaluation vector store.

Reuses the real `IngestionService` (parse -> chunk -> embed -> store,
see ADR-0008 for the embedder and ADR-0005 for the vector store) exactly
as the product does, pointed at a caller-supplied `VectorRepository` --
in every real run that means a `Settings.vector_store_dir` under a temp
directory, never `data/processed/`'s product store (see
backend/eval/README.md "Isolation"). This module never writes to that
product store itself; it is the caller's responsibility to construct
`VectorRepository` against an isolated path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from compliance_platform.ai.embeddings import Embedder
from compliance_platform.core.config import Settings
from compliance_platform.models.assessment import DEFAULT_ORGANIZATION_ID, Document
from compliance_platform.repositories.vector_repository import VectorRepository
from compliance_platform.services.ingestion_service import IngestionService
from eval.labels.schema import RelevanceLabel

_EVAL_CORPUS_SUBDIR = Path("backend") / "eval" / "corpus"


class _InMemoryDocumentRepository:
    """Minimal `DocumentRepositoryProtocol` stand-in, local to eval/.

    `IngestionService` needs a document registry to satisfy
    create_document/get_document/resolve_organization_id, but this
    harness has no use for a real SQLite-backed one: everything Stage 2
    and Stage 3 need (document_id, chunks, vectors) already lives in the
    isolated `VectorRepository` `build_eval_index` writes to. Same
    pattern as services/tests/test_ingestion_service.py's
    `_FakeDocumentRepository`, duplicated here rather than imported so
    eval/ never depends on compliance_platform's test tree.
    """

    def __init__(self) -> None:
        self._documents: dict[str, Document] = {}

    def create_document(self, document: Document) -> Document:
        self._documents[document.id] = document
        return document

    def get_document(self, document_id: str) -> Document | None:
        return self._documents.get(document_id)

    def resolve_organization_id(self, organization_id: str | None = None) -> str:
        return organization_id or DEFAULT_ORGANIZATION_ID


@dataclass(frozen=True)
class EvalDocument:
    """One corpus file indexed into the eval vector store."""

    doc_ref: str
    document_id: str


def corpus_doc_refs(repo_root: Path, labels: list[RelevanceLabel]) -> list[str]:
    """The eval corpus is every `backend/eval/corpus/*.txt` file, plus
    every document a current label references -- today that means the
    two pre-existing `data/sample_evidence/` files the Stage 1
    template's EXAMPLE rows point at (see backend/eval/corpus/README.md,
    "Kept in scope, not duplicated here"). Derived from the labels file
    rather than hardcoded, so this keeps working unchanged once real
    labels replace the EXAMPLE rows and reference different documents.

    Returns paths relative to repo_root, sorted for a deterministic
    ingestion order (LanceDB's document_id assignment doesn't depend on
    order, but a deterministic file order makes any run reproducible to
    read about).
    """
    eval_corpus_dir = repo_root / _EVAL_CORPUS_SUBDIR
    corpus_files = {
        str(p.relative_to(repo_root)) for p in eval_corpus_dir.glob("*.txt")
    }
    label_docs = {label.doc_ref for label in labels}
    return sorted(corpus_files | label_docs)


def build_eval_index(
    settings: Settings,
    vector_repository: VectorRepository,
    embedder: Embedder,
    repo_root: Path,
    doc_refs: list[str],
) -> list[EvalDocument]:
    """Ingests every doc_ref through the real IngestionService, pointed
    at the given (isolated) vector_repository. Returns the doc_ref ->
    document_id mapping the query stage needs to resolve a label's gold
    doc_ref to the document_id its chunks are actually stored under
    (document_id is server-generated per ingest call, not derivable from
    doc_ref alone).
    """
    document_repository = _InMemoryDocumentRepository()
    ingestion = IngestionService(
        settings=settings,
        vector_repository=vector_repository,
        embedder=embedder,
        document_repository=document_repository,
    )
    indexed: list[EvalDocument] = []
    for doc_ref in doc_refs:
        path = repo_root / doc_ref
        result = ingestion.ingest(filename=path.name, content=path.read_bytes())
        indexed.append(EvalDocument(doc_ref=doc_ref, document_id=result.document_id))
    return indexed
