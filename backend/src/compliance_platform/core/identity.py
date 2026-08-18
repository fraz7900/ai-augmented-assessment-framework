"""Who is making a request.

The audit trail could say what changed and when, and never who. Every
history table carried timestamps and no actor, so a finalized assessment
-- the artifact whose entire purpose is being defensible six months
later -- could not name the human who decided anything. For a product
built around "no score exists without a linked evidence trail", the
missing half of the trail was the person.

The identity is not invented here. `deployment/frontend.nginx.conf` is
the one gated entry point for the whole stack (ADR-0045) and already
authenticates every request against `.htpasswd`; it simply never passed
the result on. It now forwards the authenticated username as
`X-Remote-User`, and this module reads it.

This is NOT authentication, and must not be mistaken for it. The
application trusts the header because the only route to it in the
deployed stack passes through the proxy that sets it, and the backend
publishes no host port of its own (docker-compose.yml). Anything that
can reach the backend directly can claim any name -- which is true of
every part of this deployment's threat model, and is why the charter
says the stack must not be exposed to a network. Real authentication in
the application is "Won't (for MVP)"; attribution is not, and does not
require it.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Header

# Recorded when a request arrives with no authenticated identity: direct
# access to the backend, i.e. local development, or a deployment
# misconfigured to bypass the proxy. Deliberately a value rather than
# NULL, and deliberately not a plausible-looking name. NULL is reserved
# for rows written before attribution existed, and the two are different
# facts: "nobody was authenticated for this write" versus "we did not
# record this at the time". An audit trail that cannot tell them apart
# invites the wrong conclusion about the older one.
UNAUTHENTICATED_ACTOR = "unauthenticated"


def get_actor(x_remote_user: Annotated[str | None, Header()] = None) -> str:
    """The authenticated username for this request, for the audit trail."""
    if x_remote_user is None:
        return UNAUTHENTICATED_ACTOR
    actor = x_remote_user.strip()
    # A blank header is the same situation as a missing one: nginx emits
    # an empty $remote_user when no auth ran, rather than omitting it.
    if not actor:
        return UNAUTHENTICATED_ACTOR
    # Bounded so a hostile or broken proxy cannot write unbounded text
    # into every history row it touches.
    return actor[:128]
