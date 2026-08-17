# ADR-0058: A finalization-readiness gate, and the pinned framework version in the evidence UI

**Status:** Accepted
**Sprint:** 20 (P0 correctness tranche)
**Deciders:** Fraz Ahmed
**Related:** ADR-0057 (the evidence invariant whose violations this gate reports), ADR-0030
(`PracticeFinding`), ADR-0031/ADR-0053 (framework version pinning and the multi-version registry),
ADR-0055 (NIST CSF 1.1 — the second real version that made the UI defect reachable), ADR-0043
(evidence requests), ADR-0015 (centralized exception→HTTP mapping)

## Context

Two defects, both reachable in the shipped product, both about an assessment claiming more certainty
than it has.

**1. Finalization validated only the state machine.** `AssessmentService.transition_status` checked
that `in_review → finalized` was a legal edge and nothing else. An assessment could therefore be
frozen as authoritative — and its evidence trail locked immutable — while AI proposals sat
unreviewed, evidence requests sat open, and findings claimed credit ADR-0057 refuses to grant. The
audit-immutability guarantee then made that state permanent.

**2. The evidence UI loaded the wrong framework version.** `EvidenceTab` called
`useFramework(assessment.framework_name)`; `useFramework` accepted no version, cached under
`['framework', name]`, and sent no `?version=`. The backend has supported
`GET /frameworks/{name}?version=` since ADR-0053, so the UI simply never asked. Harmless while every
framework had one version — and reachable the moment ADR-0055 added NIST CSF 1.1, because the two
CSF versions share a name and, being differently numbered (`ID.AM-1` vs `ID.AM-01`), share no
practice ids at all. A 1.1-pinned assessment would validate references and render practice text
against 2.0.

## Decision

### Finalization readiness

1. **A structured `FinalizationReadiness` model** (`assessment_id`, `status`, `is_ready`,
   `blockers`), where each blocker carries a closed-enum `category`, the true `count`, up to 50
   `affected_ids`, and an actionable `summary`.
2. **`GET /assessments/{assessment_id}/finalization-readiness`** returns it.
3. **Blocked when**: any `PENDING` evidence link remains; any evidence request is unresolved; any
   `SATISFIED` finding lacks accepted/edited evidence; any `NOT_APPLICABLE` finding lacks the same;
   or the assessment's pinned framework version no longer resolves.
4. **Not blocked by** confirmed gaps, rejected evidence, `NOT_SATISFIED`, `PARTIALLY_SATISFIED` or
   `INSUFFICIENT_EVIDENCE`. An assessment reporting an organization as non-compliant is a complete,
   legitimate result.
5. **Enforced in `transition_status`**, raising `AssessmentNotReadyForFinalizationError` → HTTP 409
   with the blockers in the body. The frontend is not an integrity boundary; the gate holds for
   curl, a script, or a future second client.
6. **Frontend**: the Overview tab queries readiness, renders the blocker checklist, disables
   Finalize with a stated reason, and re-queries after evidence review, finding changes, mapping
   proposals, and evidence-request create/resolve.

### Pinned framework version in the UI

7. **`useFramework(name, version)`** — version in the cache key *and* the query string.
   `undefined`/`null` sends no `?version=`, preserving latest-resolution for legacy assessments
   whose `framework_version` is null.
8. `EvidenceTab` passes `assessment.framework_version`, which fixes practice lookup, the manual
   practice datalist, edited AI mappings and rendered practice text together — all four read the
   same definition object.

## Rationale

**Why the gate is server-side.** A disabled button is a usability affordance. The invariant has to
survive a caller that never renders one — and this repository already treats that distinction as
load-bearing (ADR-0030's finalized-assessment checks live in the service for the same reason).

**Why blockers are an enum, not prose.** The UI disables a control and renders a checklist from
them. Parsing English to decide that would break the first time the wording improved, and the
wording *should* be free to improve.

**Why gaps must never block.** This is the distinction the platform exists to make. ADR-0030 was
written to stop "no evidence found" and "control confirmed absent" being indistinguishable; a gate
that refused to finalize a non-compliant assessment would re-introduce exactly that pressure, this
time as an incentive to misreport. The checklist says so explicitly in its ready state.

**Why an unresolvable framework version blocks.** If the pinned definition is gone, the scores
cannot be reproduced or explained — the same "why is this MIL2" question ADR-0057 is about. Checked
only when a registry is configured at all: a service constructed without one has no framework data
by design, which is a deployment condition rather than a defect in the assessment.

**Why `count` is separate from `affected_ids`.** The id list is capped so a pathological assessment
cannot return a response the size of its evidence table. Keeping the true total alongside it means
the UI can say "and 112 more" rather than implying the visible list is complete.

**Why version belongs in the query key, not only the URL.** react-query serves from cache by key.
With the version only in the URL, the first fetched version would satisfy every subsequent request
for that framework name — the bug would survive the fix and be harder to see.

## Consequences

- `models/schemas.py`: `FinalizationBlockerCategory`, `FinalizationBlocker`,
  `FinalizationReadiness`.
- `services/assessment_service.py`: `finalization_readiness()`, the gate inside
  `transition_status`, `AssessmentNotReadyForFinalizationError`, `_MAX_BLOCKER_IDS`.
- `api/error_handlers.py`: a dedicated handler registered after the generic loop so the 409 body
  carries `blockers` as well as `detail`.
- **Three pre-existing tests changed their setup, not their assertions.** They finalized an
  assessment with outstanding work purely to reach the finalized state, then asserted immutability.
  They now clear the blocker first; each carries a comment saying so, and the gate's own behaviour is
  covered by dedicated tests rather than by their side effects.
- **This is a behavioural break for any caller that finalizes with outstanding review work.** That
  is the intent. `draft → in_review` is deliberately ungated — being in review is precisely the state
  where work is outstanding.
- Frontend: `useFinalizationReadiness`, `FinalizationChecklist`, readiness invalidation on five
  mutations, and `useFramework`'s new signature. The checklist is hidden once finalized, so a settled
  assessment is never simultaneously described as provisional.
- Tests: 10 new backend service cases (one per blocker, the negative-findings case, the refused and
  successful transitions, and the ungated `draft → in_review`), 4 new API integration cases, 6
  frontend cases for the checklist, and 5 for version-pinned framework loading — the cache-collision
  case verified to fail against the pre-fix hook.

## Alternatives considered

**Enforce readiness only in the API layer.** Rejected: `api/README.md` requires the HTTP boundary to
stay thin, and the service is what other services and scripts call.

**Block finalization on unresolved gaps as well.** Rejected — see Rationale. It would make the
platform unable to report the finding it most exists to report.

**Return 422 rather than 409.** Rejected: the request is well-formed and the assessment simply is
not in a state where it can be honoured, which is what 409 means. It also matches the existing
`AssessmentFinalizedError`/`InvalidStatusTransitionError` precedent.

**Auto-resolve or auto-reject stale pending proposals at finalization.** Rejected outright: that is
auto-accepting AI output with extra steps, which `AGENTS.md` rule 2 forbids.

**Put the version only in the URL and rely on `staleTime`.** Rejected — see Rationale; the cache key
is the part that actually prevents the collision.
