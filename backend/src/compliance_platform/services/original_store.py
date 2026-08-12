"""Retention of the original uploaded file for each ingested document.

Why this exists (ADR-0055)
--------------------------
Ingestion used to take bytes, extract text, store chunks, and discard the
source. `Settings.data_raw_dir` existed and pointed at `data/raw/`, but
nothing ever wrote to it. The consequence was only discovered when the
re-ingestion tooling was built: chunks produced by an older chunker
cannot be corrected without re-chunking the document, re-chunking needs
the document, and the document was gone. In this repo's own dev store,
6 of 30 documents are permanently un-re-ingestible for exactly that
reason.

Reconstructing a source from its own stored chunks was rejected outright
(see ADR-0055): chunks overlap and are individually stripped, so the
result would be a lossy fabrication stored under a content_hash that
never existed.

Layout
------
One file per document at `<data_raw_dir>/<document_id>__<filename>`. The
document_id prefix is what makes lookup exact; the filename suffix is
carried so the directory is legible to a human operator, and is
sanitised because it comes from an upload and must never be able to
escape the directory or overwrite something else.

Privacy
-------
This writes uploaded evidence to disk, so it is worth being precise: it
introduces no new class of exposure. The same content is already
persisted in the vector store as chunk text under `data/processed/`, and
nothing here transmits anything. `privacy-protection.mdc`'s rule that
only public or synthetic material may exist under `data/` continues to
govern what may be uploaded during development.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from compliance_platform.core.config import Settings

_logger = logging.getLogger(__name__)

# Anything that is not a safe filename character becomes "_". This is a
# security boundary, not tidiness: `filename` arrives from an upload, and
# without it a name like "../../etc/passwd" would be a path traversal.
_UNSAFE_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]")
_MAX_FILENAME_CHARS = 100
_SEPARATOR = "__"


def _safe_filename(filename: str) -> str:
    # Take the basename first, so any directory component in the upload's
    # name is discarded before sanitising what remains.
    base = Path(filename).name
    cleaned = _UNSAFE_CHARS_RE.sub("_", base).lstrip(".")
    return cleaned[:_MAX_FILENAME_CHARS] or "upload"


def store(settings: Settings, document_id: str, filename: str, content: bytes) -> Path | None:
    """Persist the original upload. Returns its path, or None if
    retention is disabled or the write failed.

    A failed write is logged and swallowed rather than raised: the
    document is fully ingested and usable at this point, and losing the
    ability to re-ingest it later must not turn a successful upload into
    a failed one. It is not silent either -- `scripts/reingest_documents.py`
    reports every document that has no retained original.
    """
    if not settings.retain_original_uploads:
        return None
    try:
        settings.data_raw_dir.mkdir(parents=True, exist_ok=True)
        path = settings.data_raw_dir / f"{document_id}{_SEPARATOR}{_safe_filename(filename)}"
        path.write_bytes(content)
        return path
    except OSError as exc:
        _logger.error("failed to retain original upload id=%s error=%s", document_id, exc)
        return None


def path_for(settings: Settings, document_id: str) -> Path | None:
    """The retained original for a document, or None if there isn't one
    (retention disabled, write failed, or -- the common case -- the
    document was ingested before retention existed).
    """
    if not settings.data_raw_dir.exists():
        return None
    for path in settings.data_raw_dir.glob(f"{document_id}{_SEPARATOR}*"):
        if path.is_file():
            return path
    return None


def content_hash(content: bytes) -> str:
    """sha256, matching services/document_parsers.py._content_hash, so a
    retained file can be checked against the `content_hash` recorded on
    its Document row before anything is rebuilt from it."""
    return hashlib.sha256(content).hexdigest()


def delete(settings: Settings, document_id: str) -> bool:
    """Remove a document's retained original. True if one was removed."""
    path = path_for(settings, document_id)
    if path is None:
        return False
    try:
        path.unlink()
        return True
    except OSError as exc:  # pragma: no cover - filesystem-dependent
        _logger.error("failed to delete retained original id=%s error=%s", document_id, exc)
        return False
