# User Personas

Derived from `PROJECT_CHARTER.md` Section 5 (Stakeholder Map). Each persona names the specific platform interaction it drives, not a generic bio, so it stays traceable to actual epics in `epics_and_user_stories.md`.

## Primary user: Priya, Compliance / GRC Lead

Runs the annual C2M2 self-assessment end to end: collects evidence from control owners, maps it to practices, and produces the board-ready report. Currently does this in Excel and email threads. Wants the platform to replace the manual cross-referencing step, not to replace her judgment on what counts as sufficient evidence — she must remain the one who accepts or rejects every AI-proposed mapping (see the human-in-the-loop invariant in `.claude/skills/assessment-generation/SKILL.md`).

**Primary flows:** create an assessment, upload evidence, review AI-proposed evidence-to-practice mappings, transition assessment status, generate the final report.

## Executive sponsor: Marcus, VP Security / CISO

Does not touch the tool day-to-day. Needs a defensible maturity narrative to bring to the board and to regulators, and needs to trust that the underlying evidence trail would survive an external audit. Cares about the distinction between "AI-proposed, still pending review" and "human-confirmed" being visible in anything shown to him, per the executive-reporting skill's rule.

**Primary flows:** view the executive dashboard, review the finalized report, is never the one linking evidence or transitioning assessment status.

## Verifier: Diane, Internal Audit

Independently checks that a finalized assessment's scores are actually supported by the cited evidence. Needs the status-history and evidence-link audit trail (Sprint 2's `AssessmentStatusChange` and `EvidenceLink` records) to be complete and immutable once an assessment is finalized.

**Primary flows:** view status history, view evidence links per practice, confirm a finalized assessment cannot be silently altered (see `AssessmentFinalizedError` in `services/assessment_service.py`).

## Contributor: Sam, OT Engineering Lead

A control owner, not a compliance specialist. Submits evidence (a network segmentation diagram, an access review log) when asked, without wanting to learn the full C2M2 practice taxonomy. Needs the upload flow to be low-friction — this persona is why `services/document_parsers.py` accepts PDF/DOCX/TXT/Markdown rather than requiring a specific structured format.

**Primary flows:** upload a document via `/ingest`, nothing further — Sam does not create assessments or review mappings.

## Out of scope for the MVP persona set

An external assessor / third-party auditor persona is named in the charter's Stakeholder Map but is explicitly out of scope for MVP user stories: the MVP has no multi-tenant access model (`PROJECT_CHARTER.md` Section 12), so an external party using the platform directly, rather than receiving its output as a report, is a post-MVP roadmap concern.
