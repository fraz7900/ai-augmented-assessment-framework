"""Application configuration.

Central, typed settings so no module reaches for `os.environ` directly.
See core/README.md: this module is a cross-cutting concern every other
layer depends on.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root is four levels up from this file:
# backend/src/compliance_platform/core/config.py -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    """Runtime configuration.

    Values may be overridden via environment variables (e.g. in a .env
    file, which is gitignored per .gitignore) but every field has a
    sensible local-first default so the app runs out of the box.
    """

    model_config = SettingsConfigDict(env_prefix="COMPLIANCE_PLATFORM_", env_file=".env")

    # Structured logging (see core/logging_config.py). Stdout only, no
    # file/rotation policy — this is a local-first, single-process app.
    log_level: str = "INFO"

    repo_root: Path = _REPO_ROOT
    data_raw_dir: Path = _REPO_ROOT / "data" / "raw"
    data_processed_dir: Path = _REPO_ROOT / "data" / "processed"
    sample_evidence_dir: Path = _REPO_ROOT / "data" / "sample_evidence"
    vector_store_dir: Path = _REPO_ROOT / "data" / "processed" / "lancedb"

    # Chunking (see services/chunking.py and the data-cleaning skill).
    chunk_target_chars: int = 1200
    chunk_overlap_chars: int = 150
    chunk_min_chars: int = 40

    # Ingestion validation (see services/document_parsers.py).
    max_upload_bytes: int = 25 * 1024 * 1024  # 25 MB
    # Backpressure for asynchronous ingestion. A queued job holds its
    # uploaded bytes in memory until a worker frees up, so this bounds
    # that commitment at roughly max_pending_ingestions *
    # max_upload_bytes in the worst case. The synchronous endpoint got
    # this bound for free by making the caller wait; accepting uploads
    # immediately removes it, so it is reintroduced deliberately.
    max_pending_ingestions: int = 10
    # NOTE: there is deliberately no `allowed_extensions` setting. One
    # existed, was never read by any code path, and had drifted to list
    # only PDF/DOCX/TXT/MD -- omitting the XLSX/CSV support added in
    # ADR-0041. So the single most authoritative-looking statement of
    # "what can this platform ingest?" was both inert and wrong, which is
    # worse than no statement at all. The readiness audit
    # (docs/architecture/02-controlled-pilot-readiness-audit.md, item 2)
    # flagged it as an unused duplicate; removed in Sprint 19.
    #
    # The real, enforced source of truth is
    # services/document_parsers.py._EXTENSION_TO_FILE_TYPE, which
    # file_type_from_extension() raises on -- one list, exercised on every
    # upload, so it cannot silently drift the way a second copy did.
    # Decompression-bomb ceiling (controlled-pilot readiness audit §A.12,
    # security hardening): applies to EXTRACTED text, after parsing —
    # complements document_parsers.py's DOCX-specific pre-check (which
    # rejects before extraction) by catching the same failure mode for
    # any format, including PDF's internal stream compression, which has
    # no equivalent cheap pre-check the way a ZIP's central directory
    # does. 20M characters is far beyond any real policy document.
    max_extracted_text_chars: int = 20_000_000

    # OCR for scanned/image-only PDFs (see services/ocr.py, ADR-0055).
    # On by default: a scanned policy PDF is ordinary real-world evidence,
    # and leaving it unreadable was the single largest practical gap in
    # the ingestion pipeline. Off is still a supported configuration --
    # OCR is slow (seconds per page) and its output needs review, so a
    # deployment that would rather reject scans than accept approximate
    # text can say so.
    ocr_enabled: bool = True
    # 200 DPI is the usual floor for reliable recognition of body text;
    # below it, small type degrades sharply, and above it the render cost
    # grows quadratically for little accuracy gain.
    ocr_render_dpi: int = 200
    # Recognition confidence below which a detected line is discarded
    # rather than stored as evidence text a reviewer might quote.
    ocr_min_confidence: float = 0.5
    # Wall-clock guard: OCR costs seconds per page, so a very large scan
    # is truncated (with a warning naming what was skipped) rather than
    # blocking a request for an unbounded time.
    ocr_max_pages: int = 50

    # Retention of original uploads (see services/original_store.py,
    # ADR-0055). On by default: without it, a document whose chunks were
    # produced by an older chunker can never be corrected, because
    # re-chunking needs the source and the source was discarded at
    # upload. Off is supported for a deployment that would rather not
    # keep a second copy of every upload on disk, at the cost of making
    # re-ingestion depend on the operator still holding the originals.
    retain_original_uploads: bool = True

    # Embeddings (see ai/embeddings.py, ADR-0006, and ADR-0008).
    embedding_backend: str = "semantic_local_onnx"
    embedding_dimensions: int = 384
    embedding_model_name: str = "BAAI/bge-small-en-v1.5"
    embedding_model_cache_dir: Path = _REPO_ROOT / "data" / "processed" / "model_cache"

    # Relational storage (see repositories/assessment_repository.py and ADR-0007).
    assessments_db_path: Path = _REPO_ROOT / "data" / "processed" / "assessments.db"

    # Framework definitions (see services/framework_loader.py, ADR-0002, ADR-0009).
    framework_mapping_dir: Path = _REPO_ROOT / "framework_mapping"

    # AI-proposed mapping (see services/mapping_service.py and ADR-0011).
    # Cosine-similarity threshold, calibrated empirically (see ADR-0011)
    # against real practice text vs. real policy chunk text — not a
    # principled cutoff, a starting point documented as such.
    mapping_similarity_threshold: float = 0.55
    mapping_candidates_per_practice: int = 1

    # Retrieval-only chat (see services/chat_service.py and ADR-0014).
    # Cosine-similarity threshold, calibrated empirically against real
    # questions and real reviewed evidence text (see ADR-0014): observed
    # true-match scores ranged 0.54-0.86, observed false-positive scores
    # (genuinely unrelated questions, domain-general vocabulary overlap)
    # ranged 0.36-0.54 — the gap is real but not clean, the same
    # disclosed-not-hidden finding ADR-0011 made for mapping (R-16).
    # 0.4 filters the clearest noise without cutting the weakest
    # observed true match; a borderline result can still surface, which
    # is why similarity is always returned, not hidden behind the cutoff.
    chat_similarity_threshold: float = 0.4
    chat_result_limit: int = 5

    # CORS (Sprint 18, ADR-0045: single-user/small-team deployment
    # hardening). Was previously hardcoded directly in main.py to the
    # two local Vite-dev-server origins -- fine for local development,
    # but meant any real deployment on a different host/domain needed a
    # CODE CHANGE just to have its frontend origin allowed at all.
    # Defaults preserve exactly the prior hardcoded behavior; a real
    # deployment overrides via COMPLIANCE_PLATFORM_CORS_ALLOWED_ORIGINS
    # (comma-separated). Moot for the default deployment/ path (ADR-0045
    # routes the frontend and API through nginx on one origin, so no
    # cross-origin request is ever made) -- this exists for local dev
    # and for anyone who deliberately keeps the backend on a separately
    # published port instead.
    cors_allowed_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )


def get_settings() -> Settings:
    """Factory rather than a module-level singleton, so tests can override
    settings (e.g. point vector_store_dir at a tmp_path) without global
    state leaking between tests.
    """
    return Settings()
