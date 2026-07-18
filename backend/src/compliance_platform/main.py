"""FastAPI application entrypoint.

Run locally with: uvicorn compliance_platform.main:app --reload
(from backend/src/, with the backend venv active).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from compliance_platform.api import assessments, frameworks, health, ingestion
from compliance_platform.api.error_handlers import register_exception_handlers

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
# (localhost:5173) than this API (127.0.0.1:8000). Restricted to known local
# dev origins rather than "*" — this is a single-user local MVP with no
# multi-tenant/cloud deployment (charter Section 12), so there is no
# legitimate cross-origin caller to allow beyond the frontend itself.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(ingestion.router)
app.include_router(assessments.router)
app.include_router(frameworks.router)
