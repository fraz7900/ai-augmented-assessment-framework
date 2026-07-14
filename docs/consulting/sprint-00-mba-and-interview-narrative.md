# Sprint 0 — MBA and Consulting Interview Narrative

This document translates Sprint 0's actual work into reusable application and interview material. It is written to be revised as later sprints add evidence, not treated as final copy — claims here should stay tied to what was actually built, listed in `docs/consulting/sprint-00-deliverables.md`'s Change Log.

## MBA Applications

**Leadership.** Sprint 0 was executed as a self-directed engagement with no external deadline pressure and no assigned scope — the decision to spend an entire sprint on planning and architecture before any visible product existed was a deliberate, self-imposed discipline, made against the natural pull (especially on a solo project) to start coding immediately for the sake of visible progress. That restraint, and the willingness to produce a paper trail (ADRs) justifying it, is the leadership behavior worth naming in an essay about resisting a locally-rewarding but strategically weaker path.

**Innovation.** The core technical bet — that a local-first, privacy-preserving LLM architecture is not a compromise but the actual product differentiator for critical-infrastructure compliance — reframes a common constraint (can't use cloud AI on sensitive data) as the design center of the system, rather than treating it as a limitation to work around. This is the kind of reframing worth describing concretely, once Sprint 1-2 produce a working local RAG pipeline to point to as evidence the bet paid off.

**Product thinking.** The explicit, logged deferral of full product management documentation (`docs/product/README.md`) is itself a product decision: prioritizing requirements against validated technical constraints rather than against assumptions, and being willing to say "not yet" to a requested deliverable with a written reason rather than either skipping it silently or producing a low-quality version to check the box.

**Strategic thinking.** Four Architecture Decision Records were produced specifically because the original plan (as given) didn't fully fit the actual repository's needs (a polyglot codebase, an undecided vector store, incomplete tooling). Rather than force-fitting the original plan or silently deviating, each deviation was reasoned through and logged. That is the specific muscle strategic thinking essays are trying to surface: noticing when the stated plan and the situation don't match, and having a repeatable process (write the ADR) for resolving the mismatch instead of an ad hoc one.

## Consulting Interviews

**Consulting competency demonstrated:** structuring an ambiguous, wide-open brief (the original architecture prompt, which specified far more than any one sprint could execute) into a sequenced, staged plan with explicit in-scope/out-of-scope boundaries per stage. This is directly the skill tested in a case interview's "how would you approach this" opening move.

**Business problem solved:** a 30+ section master brief risked producing either an unfinished sprawl (everything half-built) or a narrow slice with no architectural coherence (features built without a plan that later features could build on). Sprint 0's scoping decision — architecture and tooling only, PM docs and code explicitly deferred with reasons — avoided both failure modes.

**Measurable value created (so far, honestly stated):** zero product surface area, by design; the measurable value this sprint is the elimination of four specific rework risks (documented in the ADRs) before any code existed to be reworked. This is a legitimate, if unglamorous, answer to "what did you ship" — and naming it precisely, rather than overstating Sprint 0 as more than it was, is itself consistent with the restrained, defensible tone this project's own documents (see the EB-letter-style guidance reused elsewhere in this workspace: prefer "informed" over "caused," prefer precise claims over impressive-sounding ones) are held to throughout.

**How this would be presented to a client:** as a one-page "before you build, here's what we decided and why" memo — Situation (broad brief, no existing codebase), Complication (four points where the brief's assumptions didn't fit the actual repository), Resolution (four ADRs, a staged activation plan for tooling, and an explicit backlog of what's deferred to which future sprint) — the same structure specified for this platform's own executive reporting in `.claude/skills/executive-reporting/SKILL.md`, applied reflexively to the project's own sprint reporting.

## STAR story draft (to refine as the project progresses)

**Situation:** Given an extremely broad, 2,000+ word technical brief for an AI compliance platform, with no existing codebase and significant latitude in how to sequence the work.

**Task:** Turn the brief into an executable plan without either under-scoping (ignoring most of the brief) or over-building (attempting everything in one sprint and shipping nothing coherent).

**Action:** Produced a Project Charter scoping the business problem and MVP boundary before any architecture work; then scoped Sprint 0 narrowly to architecture, repository, and tooling; identified four places the brief's assumptions didn't fit the actual repository and resolved each with a written decision record rather than a silent deviation; explicitly deferred the product-management documentation set with a logged rationale rather than producing a rushed, low-quality version.

**Result:** A repository where every later sprint has an unambiguous place to add code, a documented reason for every structural deviation from the original brief, and a paper trail that is itself usable as application and interview material — to be updated with concrete product outcomes as Sprints 1 onward deliver working software.
