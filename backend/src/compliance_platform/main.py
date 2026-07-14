"""FastAPI application entrypoint.

Run locally with: uvicorn compliance_platform.main:app --reload
(from backend/src/, with the backend venv active).
"""

from __future__ import annotations

from fastapi import FastAPI

from compliance_platform.api import health, ingestion

app = FastAPI(
    title="AI-Augmented Compliance Assessment Platform",
    description=(
        "Local-first document ingestion for C2M2 and NIST CSF 2.0 compliance "
        "assessment. See PROJECT_CHARTER.md for scope and constraints."
    ),
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(ingestion.router)
