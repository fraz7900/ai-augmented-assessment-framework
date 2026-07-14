# Product Management Documentation

**Status:** Deferred to Sprint 1 kickoff — see rationale below.

The full product management artifact set requested in the project brief — Vision Statement, Product Requirements Document, User Personas, User Stories, Epics, Functional and Non-functional Requirements, Acceptance Criteria, Assumptions Log, Decision Log, Risk Register, and MoSCoW/RICE prioritization — belongs here.

## Why this is empty at the end of Sprint 0

`PROJECT_CHARTER.md` already establishes the stakeholder map, success metrics, risks, assumptions, and MVP scope at the business level. Writing a full PRD, user stories, and RICE-prioritized backlog before a single technical decision (vector store, chunking strategy) has been validated against real ingestion behavior would mean prioritizing features against assumptions rather than evidence — the same anti-pattern the charter itself calls out in Section 6 by framing success metrics as hypotheses to validate, not pre-claimed results.

Sprint 0 scope was explicitly held to architecture, repository, and Claude Code configuration (see the Suggested Sprint Sequence in the original brief and `README.md`'s status line). Product management documentation is scoped to begin **Sprint 1 kickoff**, once:

1. The vector store decision (ChromaDB vs. LanceDB) has been made against a real ingestion workload, so the PRD's non-functional requirements (latency, storage) are grounded in a measurement, not a guess.
2. There is a first working ingestion path to write user stories against, so "as a compliance lead, I upload a document" is a story that can carry real acceptance criteria instead of placeholder ones.

## What will land here at Sprint 1 kickoff

- `vision.md`
- `prd.md`
- `personas.md`
- `epics_and_user_stories.md`
- `requirements.md` (functional and non-functional)
- `assumptions_log.md`
- `decision_log.md`
- `risk_register.md`
- `prioritization.md` (MoSCoW and RICE scoring for the Sprint 1-10 backlog)

This deferral is itself logged here rather than silently skipped, consistent with the project's own principle (see `docs/architecture/00-repository-architecture.md`, "What Sprint 0 deliberately does not resolve") that an intentional scope decision must be visible, not indistinguishable from an oversight.
