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

from compliance_platform.models.schemas import TextProvenance


class ChatResult(BaseModel):
    practice_reference: str
    document_id: str
    chunk_id: str
    similarity: float
    chunk_text: str
    # How this quoted passage's text was obtained (ADR-0074). Chat is
    # where the product quotes evidence verbatim, so it is where R-33
    # bites hardest: OCR text is approximate, and a reviewer reading a
    # quotation is entitled to know that before relying on it. Resolved
    # per passage where the store can say, and hedged where it cannot.
    text_provenance: TextProvenance = TextProvenance.UNKNOWN


class ChatResponse(BaseModel):
    question: str
    results: list[ChatResult]
