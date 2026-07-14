"""FastAPI dependency wiring.

Constructs the singletons (settings, embedder, vector repository) that
services/ingestion_service.py needs, and exposes a get_ingestion_service()
FastAPI dependency. This is the one place api/ is allowed to know how
those pieces are constructed — routers should only ever import from
here, never build a VectorRepository or Embedder themselves.
"""

from __future__ import annotations

from functools import lru_cache

from compliance_platform.ai.embeddings import Embedder, get_embedder
from compliance_platform.core.config import Settings, get_settings
from compliance_platform.repositories.assessment_repository import AssessmentRepository
from compliance_platform.repositories.vector_repository import VectorRepository
from compliance_platform.services.assessment_service import AssessmentService
from compliance_platform.services.framework_loader import FrameworkRegistry
from compliance_platform.services.ingestion_service import IngestionService


@lru_cache
def get_cached_settings() -> Settings:
    return get_settings()


@lru_cache
def get_cached_embedder() -> Embedder:
    settings = get_cached_settings()
    return get_embedder(
        settings.embedding_backend,
        n_features=settings.embedding_dimensions,
        model_name=settings.embedding_model_name,
        cache_dir=settings.embedding_model_cache_dir,
    )


@lru_cache
def get_cached_vector_repository() -> VectorRepository:
    settings = get_cached_settings()
    return VectorRepository(settings.vector_store_dir, settings.embedding_dimensions)


@lru_cache
def get_cached_assessment_repository() -> AssessmentRepository:
    settings = get_cached_settings()
    return AssessmentRepository(settings.assessments_db_path)


@lru_cache
def get_cached_framework_registry() -> FrameworkRegistry:
    settings = get_cached_settings()
    return FrameworkRegistry(settings.framework_mapping_dir)


def get_ingestion_service() -> IngestionService:
    return IngestionService(
        settings=get_cached_settings(),
        vector_repository=get_cached_vector_repository(),
        embedder=get_cached_embedder(),
    )


def get_assessment_service() -> AssessmentService:
    settings = get_cached_settings()
    return AssessmentService(
        assessment_repository=get_cached_assessment_repository(),
        vector_repository=get_cached_vector_repository(),
        framework_registry=get_cached_framework_registry(),
        embedder=get_cached_embedder(),
        mapping_similarity_threshold=settings.mapping_similarity_threshold,
        mapping_candidates_per_practice=settings.mapping_candidates_per_practice,
    )
