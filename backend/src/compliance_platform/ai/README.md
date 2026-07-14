# ai/

LLM orchestration layer: prompt template loading (from the top-level `prompts/` directory, not hardcoded strings), retrieval-augmented context assembly, embeddings generation, and the model client abstraction that switches between local Ollama inference and the optional cloud API fallback.

This module is the enforcement point for the local-first privacy constraint described in `PROJECT_CHARTER.md` Section 7 (Risks): any code path that would send evidence content to a cloud API must be explicit, opt-in, and logged here — never a silent default.

Planned modules (Sprint 1-2, expanded Sprint 8): `embeddings.py`, `retrieval.py`, `prompt_loader.py`, `model_client.py`, `hallucination_check.py`.
