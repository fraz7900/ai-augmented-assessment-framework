"""Who the server thinks you are.

Exists because attribution stopped being something the client supplies
(ADR-0061). The evidence-request forms used to ask "your name" and send
it; the server now ignores that in favour of the identity the proxy
authenticated. Removing the field without replacing it would leave a
reviewer recording decisions under a name they cannot see -- so the UI
asks the server instead, and shows the answer.

Also the fastest way for an operator to confirm the proxy is actually
forwarding the header: if this returns `unauthenticated` through the
deployed stack, `X-Remote-User` is not arriving and every decision is
being recorded anonymously.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from compliance_platform.core.identity import UNAUTHENTICATED_ACTOR, get_actor

router = APIRouter(tags=["identity"])


class Identity(BaseModel):
    actor: str
    # Explicit rather than making the client compare against a magic
    # string it would have to keep in sync with the backend.
    is_authenticated: bool


@router.get("/identity", response_model=Identity)
def read_identity(actor: str = Depends(get_actor)) -> Identity:
    return Identity(actor=actor, is_authenticated=actor != UNAUTHENTICATED_ACTOR)
