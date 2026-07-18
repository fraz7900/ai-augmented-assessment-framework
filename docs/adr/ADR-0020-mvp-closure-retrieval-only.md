# ADR-0020: MVP closed — retrieval-only stands as the final architecture; Ollama/cloud API fallback formally descoped, not left open

**Status:** Accepted — closes the MVP
**Sprint:** 10 (fourth follow-up, after ADR-0016/0017/0018/0019)
**Deciders:** Fraz Ahmed (project owner decision, not a unilateral technical call)
**Related:** `PROJECT_CHARTER.md` Section 12, D-18, D-25, ADR-0011, ADR-0014, R-1, R-16, R-23, NFR-2

## Context

`PROJECT_CHARTER.md` Section 12 names one MVP-scope item this project has never built: "Local-first
inference via Ollama; optional, explicitly flagged Claude/OpenAI API fallback." Every other in-scope
bullet is delivered and live-verified as of Sprint 10 (frontend, deployment stack, both frameworks
fully transcribed, cross-framework equivalence). This was the one remaining open question standing
between "every MVP item delivered" and "seven of eight, with one item under active reconsideration
every few sprints."

That reconsideration already happened twice, each time as a real decision, not a default:

- **D-18 (Sprint 5):** the mapping engine shipped retrieval-only; Ollama was evaluated (sudo
  requirement checked directly, 1.4 GB package size confirmed, not assumed) and deferred — "deferred,
  not abandoned."
- **D-25 (Sprint 8):** chat's Ollama feasibility was re-checked rather than assumed unchanged, found
  to have a viable sudo-free path this time, and the choice was put to the project owner directly
  rather than decided silently. Retrieval-only was chosen again.

Both prior decisions used "deferred" language — leaving the door open indefinitely. Asked directly
whether to finally build the Ollama/API-fallback layer or close the MVP without it, the project owner
chose to close the MVP as retrieval-only. This ADR records that as a final decision for this MVP, not
a third instance of deferral.

## Decision

1. **The MVP is closed with retrieval-only as its permanent architecture, not a placeholder awaiting a
   future generative layer.** No Ollama integration, no Claude/OpenAI API fallback, will be built
   under the MVP charter. `PROJECT_CHARTER.md` Section 12's Ollama/API-fallback bullet is annotated
   in place (not rewritten) to point here, consistent with this project's standing practice of
   preserving original scope text as history rather than silently editing it (the same convention
   `docs/product/prioritization.md` already uses for its own historical rows).
2. **NFR-2** ("Any future cloud-API fallback must be explicit, opt-in per call, and logged") moves
   from "Planned" to closed/will-not-build for this MVP — the requirement itself was never wrong, it
   simply has no fallback left to govern once the decision is to not build one.
3. **R-1's residual-risk caveat is resolved, not just downgraded further.** R-1 ("AI hallucinates a
   compliance claim not supported by evidence") was already "Mitigated by construction" as of Sprint 5,
   with one stated residual: "a future generative extraction layer... would reintroduce this risk."
   That future layer is now formally not being built under this MVP, so the residual condition itself
   is closed, not merely still-hypothetical.
4. **The backlog item "Ollama-based generative extraction layer"** (`docs/product/prioritization.md`,
   RICE score 1.0 — already the lowest-scored item in the backlog) moves from an open "Should, once
   justified" row to **Won't**, the same MoSCoW category already used for genuinely out-of-scope MVP
   items (multi-tenant auth, the five roadmap frameworks, cloud deployment, OCR, continuous
   monitoring) — this item now belongs in that category for the same reason those do: a real,
   considered decision not to build it, not an oversight or a deferred maybe.

## Rationale

1. **This is the appropriate kind of decision to reserve for explicit confirmation, not infer from
   silence.** D-25 already named the underlying reason: "a consequential, hard-to-reverse choice
   (multi-GB download, a new persistent process, this codebase's first generative-AI capability)."
   Closing the MVP without it is the mirror image of that same category of decision, and was asked
   for directly rather than assumed from two prior deferrals.
2. **Retrieval-only has demonstrated real value across every capability it touches** — evidence-to-
   practice mapping (ADR-0011), chat (ADR-0014), and now cross-framework equivalence (ADR-0019) all
   ship real, cited, human-reviewed output with nothing generated that could be unverifiable. The
   three disclosed precision-ceiling risks this approach carries (R-16, R-23, and the 27 excluded
   equivalence entries in ADR-0019) are each mitigated by transparency (always showing the score,
   never hiding it behind a threshold) and mandatory human review, not by claiming the retrieval
   signal is more precise than it is. A generative layer was never necessary to deliver the platform's
   actual value proposition — it would have added review-burden reduction at the cost of this
   project's core "nothing generated, nothing to hallucinate" property (R-1), a trade this project
   has now decided, twice reconsidered and once finally decided, not to make.
3. **Annotating the charter in place rather than rewriting Section 12** keeps the original MVP
   commitment visible as what was actually promised at Sprint 0, with the final resolution recorded
   as a pointer forward — the same reason `prioritization.md`'s own top note explains why its
   Sprint-3 RICE re-sequencing is "kept as originally written... so the prioritization record stays an
   honest history rather than being quietly rewritten after the fact."

## Consequences

- `PROJECT_CHARTER.md` Section 12: Ollama/API-fallback bullet gets an inline annotation pointing to
  this ADR; no other charter text changes.
- `docs/product/requirements.md`: NFR-2 status updated to closed/will-not-build.
- `docs/product/risk_register.md`: R-1's residual-risk note updated — the "future generative layer"
  condition is now closed, not merely hypothetical-and-open.
- `docs/product/prioritization.md`: the Ollama-based generative extraction layer row moves to Won't,
  alongside the MVP's other genuinely out-of-scope items.
- `docs/product/decision_log.md`: new entry recording this as the final resolution of the D-18/D-25
  thread.
- `docs/current_sprint.md` and root `README.md`: MVP marked complete — every `PROJECT_CHARTER.md`
  Section 12 bullet is now either delivered or, for this one item, deliberately and finally closed.
- No code changes — this ADR is a scope-closure decision, not an implementation change.

## Alternatives considered

- **Build the Ollama layer now, closing the MVP with all eight bullets literally delivered.** Rejected
  by the project owner directly — the retrieval-only architecture already delivers the platform's
  real value proposition, and introducing generative inference at MVP-closure time would trade a
  demonstrated, low-risk architecture for a capability this project has twice already declined for
  the same underlying reason (R-1's hallucination risk, cost/footprint at D-18, review burden
  reduction that mandatory human review already substantially provides).
- **Leave the item open/deferred a third time, closing "everything else" but not this one.** Rejected
  — an MVP with one permanently-deferred bullet is not actually closed; asking for and recording an
  explicit final answer is more honest than letting the ambiguity persist indefinitely.
