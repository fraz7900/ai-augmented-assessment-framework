# Sprint 4 — MBA and Consulting Interview Narrative

Continues the convention from Sprints 0-3: claims here are tied to what was actually built and found this sprint, listed in `docs/consulting/sprint-04-deliverables.md`'s Change Log.

## MBA Applications

**Systems thinking demonstrated by generalizing only when a second data point demanded it.** `models/framework.py`'s `Practice.mil` field was written as a required `int` in Sprint 3 because C2M2 was the only framework that existed. Sprint 4 needed it optional, plus a new `scoring_model` field, precisely because NIST CSF 2.0's real structure required it — not because of speculative future-proofing. This is the discipline of generalizing from evidence rather than anticipation, and it is visible in the commit history as two sprints apart, not designed upfront on a guess about what a second framework might need.

**Intellectual honesty demonstrated by not treating a clean result as boring.** Sprint 3's verification step caught a real bug and made a good story; Sprint 4's verification step confirmed everything was already correct and could easily have been glossed over as uneventful. It's included in this sprint's narrative anyway, because a verification process is only actually trustworthy if it's reported consistently — including the times it finds nothing — not only when it produces a dramatic catch.

**Product judgment demonstrated by not forcing consistency for its own sake.** Fully transcribing NIST CSF 2.0 while C2M2 remains partially transcribed could look like an inconsistent standard applied across the same project. `ADR-0010` explains why it isn't: the constraint that justified partial C2M2 coverage (document size, 356 practices across 96 pages) simply didn't apply to NIST CSF 2.0 (106 subcategories across 32 pages), so applying the same "verified, not fabricated" principle produced a different outcome for each framework. Recognizing when a precedent's *reasoning* transfers but its *conclusion* shouldn't is a specific, nameable judgment call, not a contradiction.

## Consulting Interviews

**Consulting competency demonstrated:** designing a shared mechanism (the scoring dispatcher) that accommodates two genuinely different underlying models without forcing false equivalence between them. This is the same move a consulting team makes when building a cross-business-unit reporting framework for two divisions with fundamentally different KPIs — the shared mechanism (a report template, a dashboard, a scoring engine) has to know the difference between the two, not paper over it with one number that means different things depending on who's looking at it.

**Business problem solved:** the temptation, given a working MIL-scoring engine from Sprint 3, would be to reuse it as-is for NIST CSF 2.0 and quietly treat its output as an equivalent maturity number — faster to ship, and wrong. Recognizing that a standard with genuinely no maturity concept needs a genuinely different scoring semantic, and building that as a first-class, separately-tested code path rather than a workaround, is the harder and more defensible choice.

**Measurable value created:** a complete, source-verified NIST CSF 2.0 dataset (106 of 106 subcategories); a working coverage-scoring engine, verified live against real evidence; 14 new tests; and a scoring architecture now proven to generalize across two structurally different frameworks without framework-specific branching in the engine itself.

**How this would be presented to a client:** as the second framework in a two-framework MVP commitment, delivered with an explicit note about which one is more complete and why — the same way a consulting team reports pilot results across two business units when one pilot naturally had more available data to work with than the other, rather than presenting both as equally mature to avoid an awkward comparison.

## STAR story draft

**Situation:** Having just built a scoring engine for one compliance framework (C2M2) with a native, cumulative maturity-level structure, the next sprint required adding a second framework (NIST CSF 2.0) that — as flagged by project documentation written before either framework's real content existed — has no native maturity concept at all.

**Task:** Add real support for the second framework without either fabricating a maturity scale that standard doesn't define, or building a second, disconnected scoring engine that duplicates the first one's plumbing (loading, validation, API surface) for no good reason.

**Action:** Verified the framework's actual structure against its official source before writing any data, the same discipline used for the first framework, and found the earlier-written project documentation's claim (no native maturity levels) held up. Generalized the shared data model with one new field (`scoring_model`) that lets each framework declare which of two scoring semantics applies to it, then wrote a second, independently-tested scoring function and a single dispatcher — rather than either forcing the new framework through the old function or duplicating the loading and validation layers.

**Result:** Both frameworks now run through one unmodified assessment engine, verified live: a real cumulative MIL score for one, a real coverage fraction for the other, each computed correctly and each clearly distinguishable from the other via a declared property rather than an implicit assumption — with the full 106-subcategory dataset transcribed and self-checked against the standard's own published total before being shipped.
