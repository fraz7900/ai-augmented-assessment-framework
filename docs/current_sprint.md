Current sprint: Sprint 20 — P0 correctness tranche: make scoring and finalization defensible for a controlled pilot
Objective: correctness and auditability over new features or UI polish. Three deliverables, all
implemented and verified; no new frameworks, no async ingestion, no auth/RBAC/multi-tenancy, and no
refactors outside the three.
Status: The three P0 deliverables are complete. Verified 2026-08-17 on this OneDrive-backed
checkout: **493 backend tests passing** (6m07s), `ruff check .` clean, **41 frontend tests passing**
across 8 files, `tsc -b` clean, `npm run build` clean, `npm run lint` clean (2 pre-existing
fast-refresh warnings in `EvidenceSourceBadge.tsx`, untouched by this sprint). Nothing is committed —
the work sits in the working tree for review.
P0.1 — positive scoring credit now requires a linked evidence trail (ADR-0057, which supersedes ONLY
ADR-0030 Decision 3's "SATISFIED counts a practice as performed even with zero evidence links" and
that decision's unconditional NOT_APPLICABLE handling; the rest of ADR-0030 stands and is relied
upon). The superseded clause conflicted directly with this repo's governing invariant (AGENTS.md
rule 2 and `.cursor/rules/assessment-generation.mdc`: "no score exists without a linked evidence
trail"), and was reachable through the shipped API — a PUT with a free-text rationale raised a
domain's MIL with nothing behind it. Now: SATISFIED confers credit only with an ACCEPTED/EDITED
link; NOT_APPLICABLE needs the same basis because shrinking the denominator moves a score exactly as
the numerator does; PENDING and REJECTED never confer credit (counting PENDING would auto-accept an
AI proposal by the back door); negative findings (NOT_SATISFIED, INSUFFICIENT_EVIDENCE,
PARTIALLY_SATISFIED) are deliberately unaffected, since the invariant guards unsupported *credit*,
not caution. Unsupported findings remain recorded with their rationale and history, and are surfaced
on the dashboard rather than silently ignored. `services/scoring_service.py` was not touched and no
framework is special-cased: the change lives entirely in the one credit function both
`compute_scores` and `build_dashboard` already shared, so the score endpoint and the dashboard
cannot disagree.
P0.2 — the evidence UI now loads the framework version the assessment is actually pinned to
(ADR-0058). `useFramework` took no version, cached under `['framework', name]`, and sent no
`?version=`, so a NIST CSF 1.1 assessment validated practice references and rendered practice text
against 2.0. Harmless until ADR-0055 added a real second version, and then reachable — the two CSF
versions share a name and, being differently numbered (`ID.AM-1` vs `ID.AM-01`), share no practice
ids at all. Version is now in the cache key AND the query string; a null `framework_version` (legacy
assessments) still resolves latest. Practice lookup, the manual practice datalist, edited AI
mappings and displayed practice text all read the one definition object, so a single change fixes
all four. The cache-collision test was confirmed to fail against the pre-fix hook.
P0.3 — an authoritative finalization-readiness gate (ADR-0058). `transition_status` previously
validated only the state machine, so an assessment could be frozen as authoritative — and its
evidence trail locked immutable — with AI proposals unreviewed, evidence requests open, and findings
claiming credit ADR-0057 refuses. New `FinalizationReadiness` model and
`GET /assessments/{id}/finalization-readiness` return machine-readable blocker categories with
counts and affected ids (never prose to parse). Blocks on: pending AI proposals, unresolved evidence
requests, unsupported SATISFIED findings, unsupported NOT_APPLICABLE findings, and a pinned
framework version that no longer resolves. Confirmed gaps, rejected evidence, NOT_SATISFIED,
PARTIALLY_SATISFIED and INSUFFICIENT_EVIDENCE deliberately do NOT block — a finalized assessment
reporting an organization as non-compliant is a legitimate, complete result, and gating it would
re-create the very pressure to misreport that ADR-0030 existed to remove. Enforced in the service,
not the UI: the frontend is not an integrity boundary, and the refusal is a 409 carrying the same
structured blockers. The Overview tab queries readiness, renders the checklist, disables Finalize
with a stated reason, refreshes after evidence review / finding changes / mapping proposals /
evidence-request create and resolve, and hides itself once finalized so a settled assessment is
never simultaneously described as provisional.
Test changes worth naming: six pre-existing tests changed, all setup or superseded expectations,
never a weakened assertion. Two encoded ADR-0030's superseded scoring clause and now assert the
inverse with the reasoning attached. Three finalized an assessment with outstanding work purely to
reach the finalized state before testing immutability; they clear the blocker first and say so. The
golden-path E2E test failed legitimately — it excluded a practice as NOT_APPLICABLE on the strength
of "confirmed with the CISO", exactly the assertion-not-artifact case ADR-0057 addresses — and was
updated to demonstrate the correct workflow instead: a signed scope memo was added to the fictional
corpus, linked as the exclusion's basis, and the test now also asserts readiness reports no
unsupported findings. That preserves end-to-end coverage of the exclusion path, which simply
flipping the assertion would have lost.
Corrections to previously-stated status: Sprint 19's entry said 449 backend / 22 frontend tests —
those were accurate then and are superseded by the counts above. It also said `main` was "ahead of
`origin/main` until someone pushes it"; Sprint 19 was pushed and CI-verified (runs green through
commit `4244afd`). It further recorded the `libgl1`/`libglib2.0-0` Dockerfile addition as
"statically reasoned only" because Docker was unavailable — that is no longer true: the image was
built, `import cv2` succeeded inside the container, and OCR of an image-only PDF ran end to end
there, so ADR-0055's disclosure on that point is now closed.
Next (P1, not started): the evidence-request and practice-finding UIs do not yet surface which
specific practices are blocking finalization from the Evidence tab itself — the checklist names them
but the reviewer must navigate manually. An "applicability attestation" record type was considered
and deliberately deferred (see ADR-0057's Alternatives): it is worth revisiting only if real pilot
use shows scope exclusions are routinely backed by artifacts that do not fit the document model.
Also still open from Sprint 19, unchanged: upload retention is not retroactive, so the 6 of 30
documents whose originals were discarded before ADR-0056 stay permanently un-re-ingestible; and 27
of 30 stored documents have no `Document` registry row (predating ADR-0039), which also means they
have no `content_hash` to verify a retained original against. Explicitly out of scope this sprint and
not begun: new frameworks, asynchronous ingestion, assessment-document association, document
archival/deletion, legacy registry backfill, bulk evidence acceptance, and
authentication/RBAC/multi-tenancy/cloud deployment.
Charter: PROJECT_CHARTER.md
Constraint: local-first by default. Evidence content must not be sent
to a cloud API unless explicitly opted in (see PROJECT_CHARTER.md Section 7).
Data rule: only public framework documentation or synthetic sample
evidence belongs anywhere under data/ (see data/sample_evidence/README.md).
