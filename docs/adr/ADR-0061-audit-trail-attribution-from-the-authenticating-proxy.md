# ADR-0061: Attribute every audited decision to the identity the proxy already authenticated

**Status:** Accepted
**Sprint:** 21
**Deciders:** Fraz Ahmed
**Related:** ADR-0045 (nginx as the single gated entry point — the identity already exists there),
ADR-0060 (the finalization seal, which now covers attribution and moves to payload version 2),
ADR-0030 (`PracticeFinding.set_by`, which meant "who decided" and had nobody to name), ADR-0043
(evidence requests, whose `requested_by` was client-supplied), ADR-0011 (retrieval-only mapping —
why an AI-proposed link's creator is an operator, not an author)

## Context

The audit trail recorded what changed and when, and never who. `AssessmentStatusChange` and
`EvidenceLink` carried timestamps and no actor at all. `PracticeFinding.set_by` existed but defaulted
to the literal string `"human"`. `EvidenceRequest.requested_by` and `resolved_by` were free text taken
straight from the request body, so a caller could name anyone.

For a product whose stated purpose is answering *"why is this scored MIL2?"* six months later, the
missing half of that answer was the person. A finalized assessment — the artifact ADR-0058 gates and
ADR-0060 seals — could not name the human who accepted a piece of evidence, judged a practice, or
froze the record as authoritative.

The identity was not missing. `deployment/frontend.nginx.conf` has authenticated every request
against `.htpasswd` since ADR-0045, and the backend publishes no host port of its own, so that proxy
is the only route in. nginx simply never told the application who got through.

This is deliberately **not** the "no authentication, RBAC, or multi-tenancy" item that
`PROJECT_CHARTER.md` puts in "Won't (for MVP)". Attribution is not authorization: nothing here decides
what anyone may do. It records who did it.

## Decision

1. **nginx forwards the authenticated username** as `X-Remote-User $remote_user`.
2. **`core/identity.py`'s `get_actor`** reads it as a FastAPI dependency, trimming and bounding the
   value at 128 characters.
3. **A missing or blank header records `"unauthenticated"`**, a sentinel — never a plausible-looking
   name, and never NULL.
4. **NULL keeps a different meaning**: a row written before attribution existed. "Nobody was
   authenticated for this write" and "we did not record this at the time" are different facts.
5. **New columns**: `EvidenceLink.created_by`, `EvidenceLink.reviewed_by`,
   `AssessmentStatusChange.actor`. `PracticeFinding.set_by` and `PracticeFindingChange.set_by` are now
   populated from the actor instead of `"human"`.
6. **The authenticated identity outranks anything in the request body.** `requested_by` and
   `resolved_by` survive only as a fallback for a direct, unproxied call.
7. **The seal payload moves to version 2**, covering the actor fields. Version 1's builder is retained
   for seals written before these columns existed.
8. **Every write endpoint takes the actor**; no read endpoint does.

## Rationale

**Why the proxy's identity rather than a login in the application.** Building authentication would
mean sessions, password storage, and a user table — the "Won't (for MVP)" list, and a large amount of
security-sensitive surface. The deployment already authenticates every request; the only defect was
that it kept the answer to itself. Forwarding a value that already exists is the smallest change that
closes the gap, and it does not foreclose real authentication later: the same column takes a value
from either source.

**Why trusting a header is acceptable here, stated plainly.** Anything that can reach the backend
directly can claim any name. That is true, and it is the same assumption the entire deployment already
rests on — the backend publishes no host port (`docker-compose.yml`), the proxy is the only route, and
the charter says this stack must not be exposed to a network. Attribution is exactly as strong as the
deployment's existing perimeter, no stronger, and `core/identity.py` says so rather than implying
more.

**Why a sentinel and not NULL for an unauthenticated write.** Two situations must stay
distinguishable: a row from before attribution existed, and a row written today by a caller that
presented no identity. Collapsing them invites the wrong conclusion about the older one — that
somebody chose not to record a name, rather than that there was no name to record.

**Why `"unauthenticated"` and not something friendlier.** It appears in the same column as real
usernames. An auditor reading the trail must not mistake it for a person, so it is deliberately not
shaped like one.

**Why the server's identity beats the request body.** A field the caller fills in is a claim, not
attribution. Keeping it as a fallback preserves local development and direct API use without letting
a proxied request launder a false name through it.

**Why an AI-proposed link has a `created_by` at all.** It records the operator who asked for
proposals, not an author. `source` already says the engine produced the mapping and `review_status`
says nobody has confirmed it, so there is no risk of reading this as human authorship — and "who ran
the mapping engine against this assessment" is a real audit question.

**Why the seal had to move to version 2.** Attribution that can be silently rewritten after
finalization answers "who decided this" no better than attribution that was never recorded. Version 1
is kept and still verifies the seals written under it — the exact scenario `seal_version` was
introduced for in ADR-0060, arriving one sprint later.

## Consequences

- A finalized assessment can now name the person behind every decision in it, and that naming is
  covered by the seal.
- Three new nullable columns via the existing `_add_missing_columns` helper; existing rows keep NULL
  and are reported as unattributed rather than back-filled.
- `set_by` on new findings is a username where it used to be the constant `"human"`. Historical rows
  still read `"human"`, which is now visibly the old format rather than a claim about a person.
- Seals written under ADR-0060 remain verifiable; new ones are version 2.
- The frontend's evidence-request form still sends `requested_by`, which the server now ignores when
  a proxied identity is present. The field should eventually be removed from that form — it currently
  invites a user to type a name that will not be used.
- Running the backend directly (development, tests) records `unauthenticated` throughout. That is
  accurate, and it makes the difference between a proxied and unproxied deployment visible in the
  data.

## Alternatives considered

**Build real authentication in the application.** Rejected for this sprint: it is explicitly
"Won't (for MVP)" scope, it is a large security-sensitive surface, and it is not required to answer
"who decided this" in a single-user deployment whose perimeter already authenticates.

**Trust the request body and simply add `actor` to it everywhere.** Rejected: a caller-supplied name
is a claim. It would produce a column that looks like attribution and is not, which is worse than the
honest absence it replaces.

**Use NULL for unauthenticated writes.** Rejected — see Rationale; it destroys the distinction from
pre-attribution rows.

**Back-fill existing rows with a best guess.** Rejected on the same principle as ADR-0060's refusal to
seal retroactively: a value invented now would look like a record and attest to nothing.

**Leave the seal at version 1 and exclude the actor fields.** Rejected: it would leave attribution as
the one part of a finalized record that could be rewritten without detection, which is precisely the
kind of gap this project's own invariant exists to close.
