# ADR-0002: Framework definitions and prompts are versioned data, not code

**Status:** Accepted
**Sprint:** 0
**Deciders:** Fraz Ahmed

## Context

The platform's core value proposition depends on two bodies of content that change independently of application logic and independently of each other: (1) the structure of compliance frameworks (C2M2's domains and MILs, NIST CSF 2.0's functions and categories), and (2) the prompts that instruct the LLM how to extract and map evidence. Both could be implemented as Python constants or embedded strings inside `backend/src/`.

## Decision

Framework definitions live in `framework_mapping/` and prompt templates live in `prompts/`, both as versioned data files (YAML/Markdown) at the repository root, outside `backend/src/`. Application code reads these files at runtime through thin loaders; it does not embed their content.

## Rationale

1. **Different review lens, different change cadence.** A change to the NIST CSF schema (e.g., NIST publishes a 2.1 revision) is a standards-compliance change reviewed against the published standard. A change to a mapping prompt is an AI-behavior change reviewed against the hallucination-rate and precision/recall metrics defined in `PROJECT_CHARTER.md` Section 6. Neither reviewer needs to read Python to do their job if the content is isolated as data.
2. **Extensibility without rewrites.** The roadmap in the charter commits to five additional frameworks beyond the MVP two. If framework structure were encoded as Python classes or conditionals, each addition would risk touching the mapping engine itself. As data consumed by a generic loader, each addition is new files plus, at most, a loader extension — not a change to the engine's logic.
3. **Auditability.** An external assessor or regulator (see the Stakeholder Map in the charter) can be shown exactly what framework structure the system is using without reading source code, and exactly which prompt version produced a given assessment's mappings — both are direct requirements for a system that produces compliance-relevant output.

## Consequences

- Requires a loader/validation layer (`scripts/` will include a framework-YAML validator, per `scripts/README.md`) so malformed data files fail fast rather than causing silent mapping errors.
- Prompt versioning requires discipline: a prompt change must be a new file or a tracked version bump, not an in-place edit, so that historical assessments remain attributable to the prompt version that produced them.

## Alternatives considered

- **Frameworks as Python dataclasses:** rejected — couples framework updates to a code deploy and a Python-literate reviewer.
- **Prompts as inline strings in `ai/` modules:** rejected — makes prompt history indistinguishable from code history in `git log`, and makes A/B testing prompt versions (needed for the confidence-scoring evaluation work) unnecessarily awkward.
