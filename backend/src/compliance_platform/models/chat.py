"""Pydantic response models for retrieval-only chat (Sprint 8).

Read-only, computed shapes — never persisted — built fresh from an
assessment's current evidence links on every request by
services/chat_service.py. See ADR-0014: there is no separate
"confidence" vs. "generated claim" distinction to model here the way a
generative answer would need, because nothing is generated — each
result IS the cited, already human-reviewed evidence chunk.
"""

from __future__ import annotations

from pydantic import BaseModel


class ChatResult(BaseModel):
    practice_reference: str
    document_id: str
    chunk_id: str
    similarity: float
    chunk_text: str


class ChatResponse(BaseModel):
    question: str
    results: list[ChatResult]
