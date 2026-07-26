# ADR-0036: Local reasoner go/no-go — reconfirmed retrieval-only, ADR-0020 stands

**Status:** Accepted — closes the F.1 thread, not a fourth deferral
**Sprint:** 18 (controlled-pilot readiness pass, follow-up to ADR-0030/0031/0032/0033/0034/0035)
**Deciders:** Fraz Ahmed (project owner decision, asked directly — "Start on the reasoner go/no-go
decision" → reaffirmed retrieval-only)
**Related:** ADR-0011 (retrieval-only mapping engine, D-18), ADR-0014 (retrieval-only chat, D-25),
ADR-0020 (MVP closure — retrieval-only, permanent), ADR-0030 (`PracticeFinding.set_by`),
`docs/architecture/02-controlled-pilot-readiness-audit.md` §F.1

## Context

`docs/adr/ADR-0020-mvp-closure-retrieval-only.md` closed retrieval-only as this platform's permanent
architecture at Sprint 10, after two prior reconsiderations (ADR-0011/D-18 at Sprint 5,
ADR-0014/D-25 at Sprint 8), each an explicit project-owner decision. ADR-0020 was explicit that a
third open-ended deferral was not an acceptable outcome — the whole point of closing the MVP was to
stop leaving this question open indefinitely.

This sprint's controlled-pilot readiness audit (§F.1) designed, but did not implement, the
`LLMProvider`/`EvidencePack`/`ReasonerResult` interfaces a local reasoner would need, and explicitly
recommended putting the question back to the project owner directly — the same way D-18/D-25/ADR-0020
each were — rather than defaulting to either "build it" or "leave it designed-but-unbuilt forever"
without an explicit answer. Two things are materially different since Sprint 10, worth naming even
though the answer below doesn't change:

- `PracticeFinding.set_by` (ADR-0030) already reserves a `"model"` value for exactly this case, and
  the append-only `PracticeFindingChange` audit trail already exists — a reasoner's guardrails
  (pending-not-auto-applied results, an audit trail of what it claimed) are more mature now than at
  Sprint 10, when none of this existed yet.
- The sanitization pipeline (ADR-0032) and framework version pinning (ADR-0031) added this sprint
  further reinforce the project's "verified, human-reviewed, never silently trusted" posture that a
  reasoner would need to fit into cleanly.

Asked directly whether this changes the underlying calculus, the project owner reconfirmed
retrieval-only.

## Decision

1. **ADR-0020 stands. No local reasoner is built.** The `LLMProvider`/`EvidencePack`/`ReasonerResult`
   design from the audit doc §F.1 remains a documented, unimplemented design — not resurrected as
   in-progress work, not silently dropped either.
2. **This thread is closed, not deferred a third time under this decision's own lineage** (a fourth
   time counting ADR-0020 itself). A future reconsideration requires a materially new reason to
   reopen it — e.g., a concrete pilot-user complaint about review burden that transparency and human
   review don't adequately address — not a routine "what's next" sprint check-in surfacing it again
   by default.
3. **No code changes.** Same as ADR-0020's own Consequences section — this is a scope-closure
   decision, not an implementation change.

## Rationale

1. **The underlying trade ADR-0020 identified is unchanged**: a local reasoner would reduce review
   burden at the cost of this project's core "nothing generated, nothing to hallucinate" property
   (R-1). The guardrails maturing (§Context) makes a future reasoner *safer to build if built*, but
   does not itself change whether building one is worth that trade — those are different questions,
   and conflating "we could build it more safely now" with "we should build it now" would have been
   exactly the kind of unearned justification this project's discipline warns against.
2. **Asking directly, and getting a direct answer, is the correct resolution of an explicitly-flagged
   open decision** — the same pattern ADR-0020 itself established, and the same reason the audit doc's
   §F.1 recommended this exact sequence rather than either implementing the design unilaterally or
   leaving it as a perpetually-open question in every future sprint's status report.
3. **Recording this as its own ADR, rather than a silent no-op, keeps the decision trail honest**:
   a future contributor (or a future instance of this same agent) reading the audit doc or ADR-0020
   should find "this was asked again in Sprint 18 and reconfirmed" as a real, dated fact, not have to
   infer it from the design notes simply not being followed up on.

## Consequences

- No code, model, service, or dependency changes.
- `docs/architecture/02-controlled-pilot-readiness-audit.md` §F.1: updated to record the reconfirmed
  decision and point here, rather than continuing to read as an open question.
- The `LLMProvider`/`EvidencePack`/`ReasonerResult` design (ADR-0020's audit-doc predecessor text,
  §F.1) remains available for reference if a materially new reason to reconsider arises later — not
  deleted, since it represents real design work already done, just not acted on.
- No change to `PROJECT_CHARTER.md`, `docs/product/requirements.md`, or `docs/product/risk_register.md`
  — those were already updated to their final retrieval-only-permanent state by ADR-0020 itself; this
  ADR reconfirms, it does not re-open anything those documents record.

## Alternatives considered

- **Build the local reasoner now, using this sprint's more mature guardrails as justification.**
  Rejected by the project owner directly — see Rationale #1: safer-to-build is not the same question
  as worth-building, and the underlying review-burden-vs-hallucination-risk trade ADR-0020 already
  weighed is unchanged.
- **Leave the question open/deferred again, noting the guardrails changed without asking directly.**
  Rejected — this is precisely the "leaving the door open indefinitely" failure mode ADR-0020 was
  written to close; the audit doc's own §F.1 recommendation was to ask directly, not to let the
  maturing guardrails serve as a silent, undecided nudge toward eventually building it.
