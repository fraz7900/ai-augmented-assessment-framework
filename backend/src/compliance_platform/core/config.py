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
    allowed_extensions: tuple[str, ...] = (".pdf", ".docx", ".txt", ".md")

    # Embeddings (see ai/embeddings.py, ADR-0006, and ADR-0008).
    embedding_backend: str = "semantic_local_onnx"
    embedding_dimensions: int = 384
    embedding_model_name: str = "BAAI/bge-small-en-v1.5"
    embedding_model_cache_dir: Path = _REPO_ROOT / "data" / "processed" / "model_cache"

    # Relational storage (see repositories/assessment_repository.py and ADR-0007).
    assessments_db_path: Path = _REPO_ROOT / "data" / "processed" / "assessments.db"


def get_settings() -> Settings:
    """Factory rather than a module-level singleton, so tests can override
    settings (e.g. point vector_store_dir at a tmp_path) without global
    state leaking between tests.
    """
    return Settings()
