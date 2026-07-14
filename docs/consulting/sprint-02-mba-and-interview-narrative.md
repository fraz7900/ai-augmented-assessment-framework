# Sprint 2 — MBA and Consulting Interview Narrative

Continues the convention from Sprints 0-1: claims here are tied to what was actually built and found this sprint, listed in `docs/consulting/sprint-02-deliverables.md`'s Change Log.

## MBA Applications

**Product thinking under a self-imposed deadline pressure to skip the "boring" work.** By Sprint 2, the project had a working, demoable technical increment for two sprints running — the natural pull is to keep building features (start C2M2 next) rather than go back and pay off the PM-documentation debt logged in `docs/product/README.md` since Sprint 0. Doing it anyway, and specifically doing it *after* two sprints of real build experience rather than at the start, produced a PRD and backlog that immediately surfaced an actionable resequencing recommendation (the embedding-backend RICE finding) — evidence that the deferral decision was a real prioritization call, not an excuse to avoid unglamorous work.

**Strategic thinking demonstrated by RICE actually changing a decision.** A RICE exercise that reproduces the obvious priority order (build the core features first) is not doing analytical work — it's decoration. This sprint's RICE scoring instead surfaced that a *retrieval-quality fix* — not a new framework, not a new feature — is the highest-leverage item in the backlog, because its effort estimate is low (a backend swap behind an interface already built for exactly this purpose) while its downstream impact is high. Recognizing that the cheapest fix can outrank the most visible feature is a specific, defensible strategic-thinking data point, not a restated platitude about prioritization.

**Leadership demonstrated by writing down a limitation of your own design.** The new risk register entry (audit-trail bypass — nothing currently prevents a direct-repository call from skipping the finalized-assessment lock enforced only in the service layer) was found by the same person who designed the system, while writing this sprint's risk assessment, not flagged by an external reviewer. Surfacing a gap in your own architecture, in a document meant to be read by a "client," is a small but real test of whether the consulting-style transparency this project claims to model is actually being practiced or just narrated.

## Consulting Interviews

**Consulting competency demonstrated:** recognizing when a "close the deferred item" task and a "build the next feature" task should be sequenced together rather than treated as competing priorities. The PM documentation could have been written generically at any point; writing it specifically after Sprint 1-2's real findings (the embedding bug, the race condition) made it materially better, which is the argument for *when* to do a retrospective-style deliverable, not just *whether* to do one.

**Business problem solved:** a backlog that, left unexamined, would have proceeded straight to C2M2 implementation (the "obviously next" item per the original sprint sequence) without surfacing that a cheaper, higher-leverage fix existed and should happen first. This is the standard case-interview pattern of "the client's proposed next step isn't wrong, but it isn't the highest-value next step either" — arrived at here via an actual RICE calculation against actual effort estimates, not asserted.

**Measurable value created:** a working assessment lifecycle (create → link evidence → review → finalize) verified live against the running server including both of its guard rails; 45 passing tests; 9 PM documents that produced one concrete resequencing recommendation rather than restating the charter in more forms.

**How this would be presented to a client:** as the second half of a "here's what we built, and here's what we learned about what to build next" update — the RICE table itself, presented as a one-slide "we recommend X before Y, here's the effort/impact math," is the exact artifact a consulting team would bring to a steering committee checkpoint.

## STAR story draft

**Situation:** After two sprints of technical delivery (ingestion pipeline, assessment engine), a product management documentation set had been deliberately deferred twice, with a written rationale each time, while a full Sprint 3-10 backlog remained unprioritized beyond the original high-level sprint sequence.

**Task:** Produce the deferred PM artifact set at a point where it would carry real signal — not restate `PROJECT_CHARTER.md` in more files — and use it to actually inform near-term sequencing, not just document it after the fact.

**Action:** Wrote the assumptions log and risk register first, specifically pulling forward two concrete findings from Sprint 1 (a rejected `TfidfVectorizer` approach and a LanceDB race condition) that a Sprint-0-era PRD could never have included. Then ran a RICE prioritization pass against the actual remaining backlog, scoring effort against the real architecture already built (an `Embedder` interface designed in Sprint 1 specifically to make a backend swap cheap) rather than against a generic estimate.

**Result:** The RICE table surfaced that revisiting the embedding backend outranks starting C2M2 implementation on a leverage basis, a recommendation now logged as an open decision for Sprint 3 in this sprint's consulting deliverables — a concrete instance of prioritization analysis changing a sequencing decision rather than confirming one that would have happened anyway.
