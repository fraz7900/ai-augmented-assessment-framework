---
name: prompt-engineering
description: Use when adding or modifying any prompt template in prompts/ — extraction, mapping, or scoring prompts — including versioning and evaluation conventions.
---

# Prompt Engineering Conventions

Conventions for authoring and versioning prompt templates in `prompts/`, per the data-as-code separation in ADR-0002.

## Versioning rule

**Never edit a prompt template in place once it has been used to produce any assessment output that still exists.** Create a new versioned file (`mapping_v2.md`, not an edited `mapping_v1.md`) so that any historical assessment remains attributable to the exact prompt version that produced it — this is required for the hallucination-rate and precision/recall metrics in `PROJECT_CHARTER.md` Section 6 to be meaningful over time (a metric change must be attributable to a specific prompt version, not lost in an in-place edit).

## Structure every prompt template around

1. **Role and scope** — what this prompt is allowed to claim (e.g., an extraction prompt should not be asked to also score maturity; keep prompts single-purpose per the service that calls them).
2. **Explicit citation requirement** — any prompt that produces a claim about evidence must instruct the model to quote its source, per the `evidence-extraction` skill's non-negotiable rule.
3. **Explicit "insufficient evidence" instruction** — the prompt must give the model permission, and instruction, to say a practice cannot be assessed from the available evidence, rather than producing a best-guess claim. This is a direct, low-cost hallucination mitigation and should be in every extraction/mapping prompt without exception.
4. **Output format contract** — structured output (JSON) the calling service can parse deterministically, not free text requiring fragile downstream parsing.

## Evaluation discipline

A new prompt version should be run against the hand-labeled validation set (see `PROJECT_CHARTER.md` Section 6) before it replaces the active version in `ai/prompt_loader.py`'s default, and the result recorded in `docs/consulting/` for that sprint. A prompt change that isn't evaluated against the validation set is a regression risk with no visibility.

## Example usage

Any sprint touching `ai/retrieval.py`, `services/mapping_service.py`, or `services/scoring_service.py` prompt content — load this skill before writing or editing the corresponding file under `prompts/`.
