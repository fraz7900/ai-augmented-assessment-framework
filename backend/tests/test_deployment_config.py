"""Guards the deployment image's environment against a settings drift
that fails silently rather than loudly.

ADR-0056 added upload retention, whose path is `Settings.data_raw_dir`.
`deployment/backend.Dockerfile` redirects every runtime-writable path
onto the `/data` volume, and this one was missed. Nothing broke visibly:
Settings computes its default relative to the installed package, so the
container happily retained uploads to `/usr/local/lib/data/raw` inside
its own image layer, wrote files successfully, raised nothing -- and
discarded every one of them on the next container recreation. The
feature looked like it worked and preserved nothing, which is the worst
possible failure for a feature whose entire purpose is preservation.

That is the second time this class of mistake landed: the same sprint's
test fixtures redirected `vector_store_dir` and `assessments_db_path`
but not `data_raw_dir`, and a full test run wrote 45 files into the
developer's real `data/raw/`. Both times the cause was identical -- a
new writable path added to Settings, and a place that enumerates
writable paths not updated to match.

So this test enumerates them from Settings itself rather than from a
hand-kept list. A path added to Settings later is picked up
automatically, and the author is told at test time which of the two
places they still need to update.
"""

from __future__ import annotations

import re
from pathlib import Path

from compliance_platform.core.config import Settings

DEPLOYMENT = Path(__file__).resolve().parents[2] / "deployment"
DOCKERFILE = DEPLOYMENT / "backend.Dockerfile"
NGINX_CONF = DEPLOYMENT / "frontend.nginx.conf"

# Paths the application only ever READS. They are baked into the image
# (framework_mapping) or are host-side developer conveniences that the
# container has no reason to write, so they legitimately need no /data
# redirect. Anything NOT listed here is treated as writable and must be
# redirected -- the default is "must be on the volume", so forgetting to
# classify a new path fails the test rather than passing silently.
READ_ONLY_OR_UNUSED_IN_CONTAINER = {
    "repo_root",
    "framework_mapping_dir",  # baked in at build time, read-only
    "sample_evidence_dir",  # developer/demo material, not a runtime path
    "data_processed_dir",  # parent of vector_store/db, never written directly
}


def _settings_env_name(field_name: str) -> str:
    return f"COMPLIANCE_PLATFORM_{field_name.upper()}"


def _dockerfile_env_assignments() -> dict[str, str]:
    """Every COMPLIANCE_PLATFORM_* assignment in the Dockerfile's ENV
    block, including continuation lines."""
    text = DOCKERFILE.read_text(encoding="utf-8")
    return dict(re.findall(r"(COMPLIANCE_PLATFORM_[A-Z_]+)=(\S+)", text))


def _writable_path_fields() -> list[str]:
    settings = Settings()
    return [
        name
        for name in Settings.model_fields
        if isinstance(getattr(settings, name), Path)
        and name not in READ_ONLY_OR_UNUSED_IN_CONTAINER
    ]


def test_every_writable_path_is_redirected_onto_the_data_volume() -> None:
    assigned = _dockerfile_env_assignments()
    missing = [
        name for name in _writable_path_fields() if _settings_env_name(name) not in assigned
    ]
    assert not missing, (
        "deployment/backend.Dockerfile does not redirect these writable Settings paths, so the "
        f"container will write them into its own ephemeral image layer and lose them on "
        f"recreation: {missing}. Add COMPLIANCE_PLATFORM_<NAME>=/data/... to its ENV block, or "
        "add the field to READ_ONLY_OR_UNUSED_IN_CONTAINER if it genuinely is not written."
    )


def _nginx_client_max_body_bytes() -> int | None:
    """nginx's upload ceiling in bytes, or None if the directive is absent
    (in which case nginx silently applies its own 1MB default)."""
    match = re.search(r"client_max_body_size\s+(\d+)([kKmMgG]?);", NGINX_CONF.read_text("utf-8"))
    if match is None:
        return None
    size, unit = int(match.group(1)), match.group(2).lower()
    return size * {"": 1, "k": 1024, "m": 1024**2, "g": 1024**3}[unit]


def test_nginx_allows_uploads_at_least_as_large_as_the_application_does() -> None:
    """The reverse proxy must not be stricter than the app it fronts.

    nginx enforces client_max_body_size BEFORE proxying, so if it is
    lower than Settings.max_upload_bytes the application's limit is
    unreachable: the upload dies at the proxy with a bare "413 Request
    Entity Too Large" that names no size and never reaches any
    application log.

    This was a real defect, not a hypothetical. The directive was absent
    entirely, so nginx applied its 1MB default against the app's 25MB --
    and it went unnoticed because every synthetic sample in this repo is
    under 50KB. It surfaced the first time anyone uploaded a real
    standards PDF (1.5MB).
    """
    nginx_limit = _nginx_client_max_body_bytes()
    app_limit = Settings().max_upload_bytes

    assert nginx_limit is not None, (
        "deployment/frontend.nginx.conf sets no client_max_body_size, so nginx will silently "
        f"cap uploads at its 1MB default while the application advertises {app_limit} bytes."
    )
    assert nginx_limit >= app_limit, (
        f"nginx allows {nginx_limit} bytes but the application allows {app_limit}. Uploads "
        "between the two are rejected by the proxy with a 413 the application never sees."
    )


def test_nginx_does_not_rely_on_its_default_proxy_timeout() -> None:
    """Ingestion is synchronous and routinely exceeds nginx's 60s default.

    Unlike the size limit above there is no application-side constant to
    compare against -- how long an upload takes depends on the document --
    so this asserts the weaker but still real invariant: the deployment
    must state a timeout rather than inherit nginx's default, which is
    known to be too short. A real 59-page PDF measured ~93s end to end,
    of which ~76s was embedding.

    The failure mode this prevents is nasty: the backend keeps working
    and the ingestion actually SUCCEEDS, but nginx has already given up,
    so the user is shown "504 Gateway Timeout" for a document that was
    in fact stored.
    """
    conf = NGINX_CONF.read_text("utf-8")
    match = re.search(r"proxy_read_timeout\s+(\d+)s?;", conf)
    assert match is not None, (
        "deployment/frontend.nginx.conf sets no proxy_read_timeout, so nginx will cut off "
        "synchronous ingestion at its 60s default and report a 504 for uploads that succeed."
    )
    assert int(match.group(1)) > 60, (
        f"proxy_read_timeout is {match.group(1)}s, at or below nginx's own 60s default -- "
        "which a real 59-page document has been measured to exceed."
    )


def test_redirected_paths_point_at_the_persistent_volume() -> None:
    """Being listed is not enough -- it has to point at /data, which is
    the only path docker-compose backs with a named volume."""
    assigned = _dockerfile_env_assignments()
    for name in _writable_path_fields():
        # A missing assignment is the other test's job to report; skipping
        # it here keeps that failure readable instead of burying it under
        # a KeyError from this one.
        value = assigned.get(_settings_env_name(name))
        if value is None:
            continue
        assert value.startswith("/data/"), (
            f"{_settings_env_name(name)} is set to {value!r}, which is not on the /data volume. "
            "Anything written outside /data does not survive container recreation."
        )
