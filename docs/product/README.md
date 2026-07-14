# Product Management Documentation

**Status:** Delivered at Sprint 2 kickoff, per the deferral rationale originally logged in this file (preserved below for the historical record).

The full product management artifact set requested in the project brief now lives here, written against a working ingestion pipeline (Sprint 1) and assessment engine (Sprint 2) rather than against unvalidated assumptions:

- [`vision.md`](./vision.md) — vision statement
- [`prd.md`](./prd.md) — Product Requirements Document (goals, non-goals, key flows, success metrics)
- [`personas.md`](./personas.md) — user personas, traced to `PROJECT_CHARTER.md`'s Stakeholder Map
- [`epics_and_user_stories.md`](./epics_and_user_stories.md) — epics and user stories with acceptance criteria, delivered and planned
- [`requirements.md`](./requirements.md) — functional and non-functional requirements, each traced to a user story or ADR
- [`assumptions_log.md`](./assumptions_log.md) — what was assumed, and what actually happened to each assumption
- [`decision_log.md`](./decision_log.md) — business-facing decision index, cross-referenced to the technical ADRs in `docs/adr/`
- [`risk_register.md`](./risk_register.md) — master, living risk register
- [`prioritization.md`](./prioritization.md) — MoSCoW and RICE scoring for the Sprint 3-10 backlog

## Why this was deferred past Sprint 0, and why that was the right call

`PROJECT_CHARTER.md` already established the stakeholder map, success metrics, risks, assumptions, and MVP scope at the business level in Sprint 0. Writing a full PRD, user stories, and RICE-prioritized backlog before a single technical decision (vector store, embedding backend) had been validated against real ingestion behavior would have meant prioritizing features against assumptions rather than evidence — the same anti-pattern the charter itself calls out in Section 6 by framing success metrics as hypotheses to validate, not pre-claimed results.

In practice, this paid off directly: `assumptions_log.md` A-6 and A-7 record two assumptions made while building Sprint 1 (`TfidfVectorizer` would work; a listing-based table-existence check was safe) that turned out to be wrong and were caught before shipping. A PRD or backlog written before Sprint 1 could not have known to prioritize around either finding, because neither was discoverable without building the thing first.

This deferral was itself logged rather than silently skipped, consistent with the project's own principle (see `docs/architecture/00-repository-architecture.md`, "What Sprint 0 deliberately does not resolve") that an intentional scope decision must be visible, not indistinguishable from an oversight — and now that the deferral has been honored rather than left open indefinitely, that same principle applies to closing it out visibly.
