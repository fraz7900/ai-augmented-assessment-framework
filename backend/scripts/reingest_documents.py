"""Re-ingest already-stored documents so their chunks pick up current
parsing and chunking, remapping reviewed evidence links instead of
breaking them.

Why this exists
---------------
ADR-0054 (word-boundary snapping) and ADR-0055 (sentence snapping, PDF
normalisation, OCR) all changed the text and offsets of the chunks this
platform stores. Both ADRs deliberately did NOT migrate existing data,
and ADR-0054 gave the reason plainly: re-chunking a document invalidates
every `chunk_id` that a reviewed `EvidenceLink` points at, and silently
breaking reviewed citations is worse than leaving old boundaries in
place.

That reason is real, but it is not permanent. Chunks record
`char_start`/`char_end` (ADR-0042), so an old chunk and a new chunk can
be compared by the span of source text they cover. A link pointing at an
old chunk can therefore be moved to the new chunk covering the same span,
which is a principled remap rather than a guess -- edges move by at most
a bounded shift (40 chars for word snapping, `overlap//2` for sentence
snapping), so the correct new chunk overlaps the old one almost entirely.

Two hard constraints this tool works within
-------------------------------------------
1. **Original uploads are not retained.** `IngestionService.ingest()`
   takes bytes, extracts text, stores chunks, and discards the source;
   `data/raw/` is configured but nothing ever writes to it. So this
   cannot re-chunk anything by itself -- the operator must supply the
   original files. Reconstructing a source document from its own stored
   chunks was rejected outright: chunks overlap and are individually
   stripped, so the "reconstruction" would be a lossy fabrication stored
   under a content_hash that never existed.
2. **Not every stored document has a registry row.** `Document`
   (ADR-0039) arrived long after ingestion did, so older documents exist
   in the vector store with no row at all. This tool therefore drives
   from the vector store, which is the authoritative list of what is
   actually chunked, and treats a missing registry row as information to
   report rather than an error.

Usage
-----
    # Report only. Never writes. Start here.
    python scripts/reingest_documents.py --source-dir ../data/sample_evidence

    # Apply, for matched documents only.
    python scripts/reingest_documents.py --source-dir ../data/sample_evidence --apply

Matching is by content: a stored document is matched to a source file
when the document's longest stored chunk appears in that file's freshly
parsed text. That is deliberate -- filenames are not reliable (27 of the
30 documents in this repo's own dev store have no registry row and so no
recorded filename at all), whereas chunk text is what was actually
ingested.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlmodel import Session, create_engine, select

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from compliance_platform.ai.embeddings import get_embedder  # noqa: E402
from compliance_platform.core.config import Settings  # noqa: E402
from compliance_platform.models.assessment import Document, EvidenceLink  # noqa: E402
from compliance_platform.models.schemas import ParseStatus  # noqa: E402
from compliance_platform.repositories.vector_repository import VectorRepository  # noqa: E402
from compliance_platform.services import (  # noqa: E402
    chunking,
    document_parsers,
    original_store,
)


def _normalise(text: str) -> str:
    """Whitespace-insensitive form, for content matching only."""
    return " ".join(text.split())


def _overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def _load_sources(source_dir: Path, settings: Settings) -> dict[Path, str]:
    """Parse every candidate source file with the CURRENT parser."""
    sources: dict[Path, str] = {}
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file() or path.name.lower() == "readme.md":
            continue
        try:
            document_parsers.file_type_from_extension(path.name)
        except ValueError:
            continue  # not an ingestible format
        parsed = document_parsers.parse_document(
            path.name, path.read_bytes(), settings=settings
        )
        if parsed.parse_status in {ParseStatus.SUCCESS, ParseStatus.SUCCESS_OCR}:
            sources[path] = parsed.raw_text
    return sources


def _match_source(chunks: list[dict], sources: dict[Path, str]) -> Path | None:
    """The source file containing this document's longest stored chunk.

    The longest chunk is used as the probe because short chunks (a
    heading, a single row) can appear in more than one document, while a
    ~1200-character body chunk is effectively unique.
    """
    probe = max((c["text"] for c in chunks), key=len, default="")
    if not probe:
        return None
    needle = _normalise(probe)
    matches = [path for path, text in sources.items() if needle in _normalise(text)]
    return matches[0] if len(matches) == 1 else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=None,
        help=(
            "Fallback directory of original files, for documents ingested BEFORE upload "
            "retention existed (ADR-0055). Documents with a retained original need no "
            "--source-dir and are matched by document id, not by content."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually re-ingest and remap. Without this the script only reports.",
    )
    args = parser.parse_args()

    settings = Settings()
    vectors = VectorRepository(settings.vector_store_dir, settings.embedding_dimensions)
    engine = create_engine(f"sqlite:///{settings.assessments_db_path}")

    sources = _load_sources(args.source_dir, settings) if args.source_dir else {}
    if args.source_dir:
        print(f"parsed {len(sources)} fallback source file(s) from {args.source_dir}")
    print(f"retained-original store: {settings.data_raw_dir}\n")

    with Session(engine) as session:
        registry = {d.id: d for d in session.exec(select(Document)).all()}
        links = session.exec(select(EvidenceLink)).all()
        links_by_document: dict[str, list[EvidenceLink]] = {}
        for link in links:
            links_by_document.setdefault(link.document_id, []).append(link)

        document_ids = vectors.document_ids()
        totals = {"matched": 0, "unmatched": 0, "relinked": 0, "unmappable": 0}
        embedder = get_embedder(
            settings.embedding_backend,
            n_features=settings.embedding_dimensions,
            model_name=settings.embedding_model_name,
            cache_dir=settings.embedding_model_cache_dir,
        )

        for document_id in document_ids:
            chunks = vectors.chunks_for_document(document_id)
            doc_links = links_by_document.get(document_id, [])
            pinned = [link for link in doc_links if link.chunk_id]
            row = registry.get(document_id)

            print(f"{document_id}")
            print(
                f"  chunks={len(chunks)}  evidence_links={len(doc_links)} "
                f"(chunk-pinned: {len(pinned)})  "
                f"registry_row={'yes' if row else 'NO (pre-ADR-0039)'}"
            )
            if row:
                print(f"  filename={row.filename}  parser_version={row.parser_version}")

            # A retained original (ADR-0055) is authoritative: it is keyed
            # by document id, so there is no matching to get wrong. The
            # content-matched fallback exists only for documents ingested
            # before retention, and cannot be as certain.
            retained = original_store.path_for(settings, document_id)
            text: str | None = None
            if retained is not None:
                content = retained.read_bytes()
                if row and row.content_hash and (
                    original_store.content_hash(content) != row.content_hash
                ):
                    # Refuse rather than rebuild from a file that is not
                    # the document it claims to be.
                    totals["unmatched"] += 1
                    print(
                        f"  source=RETAINED BUT CORRUPT ({retained.name}) — content_hash "
                        "does not match the registry; refusing to re-ingest\n"
                    )
                    continue
                parsed = document_parsers.parse_document(
                    row.filename if row else retained.name, content, settings=settings
                )
                if parsed.parse_status in {ParseStatus.SUCCESS, ParseStatus.SUCCESS_OCR}:
                    text = parsed.raw_text
                    print(f"  source=retained original ({retained.name})")

            if text is None:
                source = _match_source(chunks, sources)
                if source is None:
                    totals["unmatched"] += 1
                    print(
                        "  source=UNMATCHED — no retained original and no matching file in "
                        "--source-dir; cannot re-ingest\n"
                    )
                    continue
                text = sources[source]
                print(f"  source={source.name} (content-matched fallback)")

            totals["matched"] += 1
            if not args.apply:
                print("  (report only; re-run with --apply to re-ingest)\n")
                continue
            new_chunks = chunking.chunk_document(document_id, text, settings)
            new_vectors = embedder.embed([c.text for c in new_chunks])

            # Remap BEFORE deleting, so a failure here leaves the old
            # chunks in place rather than orphaning reviewed links.
            remap: dict[str, str] = {}
            unmappable: list[str] = []
            for link in pinned:
                old = next((c for c in chunks if c["chunk_id"] == link.chunk_id), None)
                if old is None:
                    unmappable.append(link.id)
                    continue
                best = max(
                    new_chunks,
                    key=lambda c: _overlap(
                        old["char_start"], old["char_end"], c.char_start, c.char_end
                    ),
                    default=None,
                )
                if best is None or _overlap(
                    old["char_start"], old["char_end"], best.char_start, best.char_end
                ) == 0:
                    unmappable.append(link.id)
                    continue
                remap[link.id] = best.chunk_id

            vectors.delete_chunks_for_document(document_id)
            vectors.add_chunks(new_chunks, new_vectors)
            for link in pinned:
                if link.id in remap:
                    link.chunk_id = remap[link.id]
                    session.add(link)
            session.commit()

            totals["relinked"] += len(remap)
            totals["unmappable"] += len(unmappable)
            print(
                f"  re-ingested: {len(chunks)} -> {len(new_chunks)} chunks; "
                f"relinked {len(remap)} evidence link(s); "
                f"{len(unmappable)} could not be remapped"
            )
            if unmappable:
                # Named individually: a citation that silently lost its
                # chunk is exactly the failure this tool exists to avoid.
                print(f"  UNMAPPABLE link ids: {', '.join(unmappable)}")
            print()

    print(
        f"documents matched={totals['matched']} unmatched={totals['unmatched']}; "
        f"evidence links relinked={totals['relinked']} unmappable={totals['unmappable']}"
    )
    if not args.apply:
        print("no changes were written (report mode)")


if __name__ == "__main__":
    main()
