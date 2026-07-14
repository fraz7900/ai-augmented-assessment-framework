# prompts/

Versioned prompt templates as data files (Markdown or YAML with placeholders), not strings embedded in Python. Loaded at runtime by `backend/src/compliance_platform/ai/prompt_loader.py`.

Why prompts live outside `backend/src/`: prompt changes are a distinct kind of change from code changes — they need their own review lens (does this change bias the mapping? does it affect the hallucination rate?) and their own version history independent of application logic. Treating prompts as versioned data is also what makes the confidence-scoring and hallucination-rate metrics in `PROJECT_CHARTER.md` Section 6 meaningful over time: a metric regression can be attributed to a specific prompt version, not buried in a code diff.

Planned structure (Sprint 1+): `extraction/`, `mapping/`, `scoring/`, each with versioned files (e.g., `mapping_v1.md`, `mapping_v2.md`).
