"""FastAPI application entrypoint.

Run locally with: uvicorn compliance_platform.main:app --reload
(from backend/src/, with the backend venv active).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from compliance_platform.api import assessments, documents, frameworks, health, ingestion
from compliance_platform.api.error_handlers import register_exception_handlers
from compliance_platform.core.config import get_settings
from compliance_platform.core.logging_config import configure_logging

_settings = get_settings()
configure_logging(_settings)

app = FastAPI(
    title="AI-Augmented Compliance Assessment Platform",
    description=(
        "Local-first document ingestion, assessment tracking, and C2M2 scoring "
        "for energy-sector cybersecurity compliance assessment. See "
        "PROJECT_CHARTER.md for scope and constraints."
    ),
    version="0.3.0",
)

register_exception_handlers(app)

# Sprint 10: the frontend's Vite dev server runs on a different origin
# (localhost:5173) than this API (127.0.0.1:8000). Restricted to known
# origins rather than "*" — this is a single-user/small-team local MVP
# with no multi-tenant/cloud deployment (charter Section 12), so there
# is no legitimate cross-origin caller to allow beyond the frontend
# itself. Sprint 18 (ADR-0045): origins are now
# Settings.cors_allowed_origins, not hardcoded — a real deployment on a
# different host/domain no longer needs a code change just to have its
# frontend origin allowed. Moot for deployment/'s own default path
# (ADR-0045 routes frontend+API through nginx on one origin), but this
# still matters for local dev and anyone using the backend directly on
# a separately published port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_settings.cors_allowed_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(ingestion.router)
app.include_router(assessments.router)
app.include_router(frameworks.router)
app.include_router(documents.router)
