"""How a request's actor is derived, for the audit trail (ADR-0061)."""

from __future__ import annotations

from compliance_platform.core.identity import UNAUTHENTICATED_ACTOR, get_actor


def test_the_proxys_authenticated_username_is_the_actor() -> None:
    assert get_actor("priya") == "priya"


def test_a_missing_header_is_recorded_as_unauthenticated_not_guessed() -> None:
    # Direct access to the backend, i.e. local development. The record
    # says so rather than inventing a plausible name.
    assert get_actor(None) == UNAUTHENTICATED_ACTOR


def test_a_blank_header_is_treated_as_no_identity() -> None:
    # nginx emits an empty $remote_user when no auth ran, rather than
    # omitting the header — so blank has to mean the same as absent.
    assert get_actor("") == UNAUTHENTICATED_ACTOR
    assert get_actor("   ") == UNAUTHENTICATED_ACTOR


def test_surrounding_whitespace_does_not_become_part_of_the_identity() -> None:
    assert get_actor("  priya \n") == "priya"


def test_an_absurdly_long_identity_is_bounded() -> None:
    # A hostile or broken proxy must not be able to write unbounded text
    # into every history row it touches.
    assert len(get_actor("x" * 5000)) == 128


def test_unauthenticated_is_not_a_plausible_username() -> None:
    # It appears in the same column as real names, so it has to be
    # obviously not one of them when an auditor reads the trail.
    assert UNAUTHENTICATED_ACTOR == "unauthenticated"
