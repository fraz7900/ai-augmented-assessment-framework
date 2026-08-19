"""Client separation, against the real API and database (ADR-0063).

R-39: before this, the attach flow browsed every document on the
instance, so one organisation's policy could be attached to another
organisation's assessment. These tests are that sentence made
executable, at the HTTP boundary a reviewer actually reaches — the
repository-level guard has its own tests, and the two are not
substitutes: one proves the boundary is enforced where a bypass would
land, this one proves the product cannot cross it.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from compliance_platform.api import dependencies
from compliance_platform.core.config import Settings
from compliance_platform.main import app

_CACHED = (
    dependencies.get_cached_settings,
    dependencies.get_cached_vector_repository,
    dependencies.get_cached_assessment_repository,
    dependencies.get_cached_framework_registry,
)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    settings = Settings(
        vector_store_dir=tmp_path / "lancedb",
        assessments_db_path=tmp_path / "assessments.db",
        data_raw_dir=tmp_path / "raw",
    )
    for cached in _CACHED:
        cached.cache_clear()
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)
    with TestClient(app) as test_client:
        yield test_client
    for cached in _CACHED:
        cached.cache_clear()


def _organizations(client: TestClient) -> list[dict]:
    response = client.get("/organizations")
    assert response.status_code == 200
    return response.json()


def _create_organization(client: TestClient, name: str) -> str:
    response = client.post("/organizations", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _ingest(client: TestClient, filename: str, organization_id: str | None = None) -> str:
    body = (
        "Multi factor authentication is required for all remote access to critical systems, "
        "and access reviews are performed quarterly by the security team."
    )
    data = {"organization_id": organization_id} if organization_id else {}
    response = client.post(
        "/ingest", files={"file": (filename, body.encode(), "text/plain")}, data=data
    )
    assert response.status_code == 200, response.text
    return response.json()["document_id"]


def _assessment(client: TestClient, name: str, organization_id: str | None = None) -> str:
    payload: dict = {"name": name, "framework_name": "C2M2"}
    if organization_id:
        payload["organization_id"] = organization_id
    created = client.post("/assessments", json=payload)
    assert created.status_code == 200, created.text
    return created.json()["id"]


# --- the instance starts usable ---------------------------------------


def test_a_new_instance_has_one_organization_and_needs_no_setup(client: TestClient) -> None:
    # The single-organisation deployment the charter scopes has to work
    # without anyone creating something first.
    organizations = _organizations(client)

    assert len(organizations) == 1
    assert organizations[0]["name"] == "Unassigned"


def test_an_assessment_created_without_an_organization_joins_the_only_one(
    client: TestClient,
) -> None:
    only = _organizations(client)[0]["id"]

    assessment_id = _assessment(client, "Pilot")

    assert client.get(f"/assessments/{assessment_id}").json()["organization_id"] == only


def test_creating_an_assessment_without_an_organization_is_refused_once_two_exist(
    client: TestClient,
) -> None:
    """The boundary case. With two clients on one instance there is no
    honest answer, so the server asks rather than guesses -- guessing is
    R-39 restated."""
    _create_organization(client, "Coastal Utility")

    response = client.post("/assessments", json={"name": "Pilot", "framework_name": "C2M2"})

    assert response.status_code == 400
    assert "organization_id" in response.json()["detail"]


def test_an_unknown_organization_is_refused(client: TestClient) -> None:
    response = client.post(
        "/assessments",
        json={"name": "Pilot", "framework_name": "C2M2", "organization_id": "no-such-org"},
    )

    assert response.status_code == 404


# --- the boundary -----------------------------------------------------


def test_a_document_cannot_be_attached_across_organizations(client: TestClient) -> None:
    """R-39, at the HTTP boundary. This is the request the product used
    to allow."""
    ours = _organizations(client)[0]["id"]
    theirs = _create_organization(client, "Coastal Utility")
    assessment_id = _assessment(client, "Ours", ours)
    their_document = _ingest(client, "their_policy.txt", theirs)

    response = client.post(
        f"/assessments/{assessment_id}/documents", json={"document_id": their_document}
    )

    assert response.status_code == 409
    assert "organization" in response.json()["detail"].lower()


def test_a_document_from_the_same_organization_still_attaches(client: TestClient) -> None:
    # The guard must not break the ordinary case it sits in front of.
    ours = _organizations(client)[0]["id"]
    assessment_id = _assessment(client, "Ours", ours)
    document_id = _ingest(client, "our_policy.txt", ours)

    response = client.post(
        f"/assessments/{assessment_id}/documents", json={"document_id": document_id}
    )

    assert response.status_code == 200


def test_evidence_cannot_be_linked_across_organizations(client: TestClient) -> None:
    """Linking attaches implicitly (ADR-0062), so the boundary has to
    hold on this path too -- otherwise the refusal above would be a
    front door locked beside an open window."""
    ours = _organizations(client)[0]["id"]
    theirs = _create_organization(client, "Coastal Utility")
    assessment_id = _assessment(client, "Ours", ours)
    their_document = _ingest(client, "their_policy.txt", theirs)

    response = client.post(
        f"/assessments/{assessment_id}/evidence",
        json={"document_id": their_document, "practice_reference": "ASSET-1a"},
    )

    assert response.status_code == 409


def test_the_mapping_engine_cannot_propose_another_organizations_evidence(
    client: TestClient,
) -> None:
    """The retrieval path, which is where a boundary is easiest to get
    wrong: it reaches the vector store, which knows nothing about
    organisations. The other organisation's document says exactly what
    the practice asks for, so a proposal would be a strong match if
    anything were searching it -- which is what makes the empty result
    mean something.
    """
    ours = _organizations(client)[0]["id"]
    theirs = _create_organization(client, "Coastal Utility")
    assessment_id = _assessment(client, "Ours", ours)
    their_document = _ingest(client, "their_access_control_policy.txt", theirs)

    proposed = client.post(f"/assessments/{assessment_id}/propose-mappings")

    assert proposed.status_code == 200
    assert all(link["document_id"] != their_document for link in proposed.json())


# --- scoped lists -----------------------------------------------------


def test_the_document_list_never_shows_another_organizations_documents(
    client: TestClient,
) -> None:
    ours = _organizations(client)[0]["id"]
    theirs = _create_organization(client, "Coastal Utility")
    _ingest(client, "ours.txt", ours)
    _ingest(client, "theirs.txt", theirs)

    listed = client.get(f"/documents?organization_id={ours}").json()

    assert [document["filename"] for document in listed] == ["ours.txt"]


def test_the_assessment_list_never_shows_another_organizations_assessments(
    client: TestClient,
) -> None:
    ours = _organizations(client)[0]["id"]
    theirs = _create_organization(client, "Coastal Utility")
    _assessment(client, "Ours", ours)
    _assessment(client, "Theirs", theirs)

    listed = client.get(f"/assessments?organization_id={ours}").json()

    assert [assessment["name"] for assessment in listed] == ["Ours"]


def test_recent_uploads_are_scoped_too(client: TestClient) -> None:
    # A queue listing every client's filenames would leak across the
    # boundary this sprint exists to draw, even though no evidence is
    # exposed.
    ours = _organizations(client)[0]["id"]
    theirs = _create_organization(client, "Coastal Utility")
    _ingest(client, "ours.txt", ours)
    _ingest(client, "theirs.txt", theirs)

    listed = client.get(f"/ingest/jobs?organization_id={theirs}").json()

    assert all(job["filename"] != "ours.txt" for job in listed)


# --- organisations themselves -----------------------------------------


def test_two_organizations_cannot_share_a_name(client: TestClient) -> None:
    # A chooser whose job is telling clients apart cannot do it with two
    # identical labels and two opaque ids.
    _create_organization(client, "Coastal Utility")

    response = client.post("/organizations", json={"name": "Coastal Utility"})

    assert response.status_code == 409


def test_an_organization_can_be_renamed_without_moving_anything(client: TestClient) -> None:
    only = _organizations(client)[0]["id"]
    assessment_id = _assessment(client, "Pilot", only)

    renamed = client.patch(f"/organizations/{only}", json={"name": "Riverbend Power"})

    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Riverbend Power"
    assert client.get(f"/assessments/{assessment_id}").json()["organization_id"] == only


def test_a_blank_organization_name_is_refused(client: TestClient) -> None:
    response = client.post("/organizations", json={"name": "   "})

    assert response.status_code == 400
