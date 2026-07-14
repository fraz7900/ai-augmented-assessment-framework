"""FastAPI application entrypoint.

Run locally with: uvicorn compliance_platform.main:app --reload
(from backend/src/, with the backend venv active).
"""

from __future__ import annotations

from fastapi import FastAPI

from compliance_platform.api import assessments, frameworks, health, ingestion

app = FastAPI(
    title="AI-Augmented Compliance Assessment Platform",
    description=(
        "Local-first document ingestion, assessment tracking, and C2M2 scoring "
        "for energy-sector cybersecurity compliance assessment. See "
        "PROJECT_CHARTER.md for scope and constraints."
    ),
    version="0.3.0",
)

app.include_router(health.router)
app.include_router(ingestion.router)
app.include_router(assessments.router)
app.include_router(frameworks.router)
