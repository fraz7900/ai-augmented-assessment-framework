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

DOCKERFILE = Path(__file__).resolve().parents[2] / "deployment" / "backend.Dockerfile"

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
