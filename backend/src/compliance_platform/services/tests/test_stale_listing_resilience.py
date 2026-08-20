"""A file that is there but not yet listed (ADR-0082, R-11).

R-11 has been open since Sprint 1 and confirmed live twice: the
OneDrive-synced filesystem this project is developed on does not give
instantly-consistent directory listings, so `path.exists()` can report
False for a file that is present.

The reason it stayed open is that it looked harmless. It is not: every
one of the four sites failed SILENTLY. A framework reads as not found,
the cross-framework equivalence file reads as empty, a framework's
practices vanish from the text index -- with nothing raised and nothing
logged, on a product whose whole argument is that its conclusions are
traceable.

These tests simulate exactly that condition by making `exists()` lie
while the file is really there. Under the old check-then-act code every
one of them fails; under EAFP the data loads, because opening a file
that exists succeeds regardless of what a listing said a moment ago.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from compliance_platform.services import original_store
from compliance_platform.services.framework_loader import FrameworkRegistry

_FRAMEWORKS = Path(__file__).resolve().parents[4].parent / "framework_mapping"


@pytest.fixture
def lying_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every Path.exists() reports False. The files are all still there.

    This is the stale-listing condition, made deterministic. It is a
    stronger version of the real fault -- which is intermittent and
    affects one path at a time -- so anything that survives it survives
    the real thing.
    """
    monkeypatch.setattr(Path, "exists", lambda self: False)


def test_a_framework_loads_even_when_the_listing_says_it_is_missing(
    lying_exists: None,
) -> None:
    """The failure a reviewer would have met as "framework unavailable"
    on an assessment whose framework was sitting on disk the whole time."""
    registry = FrameworkRegistry(_FRAMEWORKS)

    framework = registry.get("C2M2")

    assert framework is not None
    assert framework.name == "C2M2"
    assert len(framework.domains) == 10


def test_equivalence_entries_survive_a_stale_listing(lying_exists: None) -> None:
    """The worst of the four. A stale listing here did not fail -- it
    returned zero cross-framework equivalents, so every equivalence in
    the product silently disappeared."""
    registry = FrameworkRegistry(_FRAMEWORKS)

    entries = registry._load_equivalence_entries()

    assert entries, "equivalence entries vanished when exists() reported False"


def test_the_practice_text_index_is_not_silently_truncated(lying_exists: None) -> None:
    """`continue` on a stale listing dropped one framework's practices
    out of the index without a word."""
    registry = FrameworkRegistry(_FRAMEWORKS)

    index = registry._build_practice_text_index()

    assert index, "the practice text index came back empty"
    assert any(key[0] == "C2M2" for key in index), "C2M2's practices are missing"


def test_a_retained_original_is_still_found(lying_exists: None, tmp_path: Path) -> None:
    from compliance_platform.core.config import Settings

    settings = Settings(data_raw_dir=tmp_path)
    (tmp_path / "doc-1__policy.txt").write_bytes(b"retained")

    assert original_store.path_for(settings, "doc-1") is not None


def test_a_genuinely_absent_framework_still_returns_none(tmp_path: Path) -> None:
    """EAFP must not turn "missing" into "crash". The behaviour when a
    file really is absent is unchanged -- which is the half of this that
    could have regressed."""
    registry = FrameworkRegistry(tmp_path)

    assert registry.get("C2M2") is None
    assert registry._load_equivalence_entries() == []
    assert registry._build_practice_text_index() == {}


def test_a_missing_retention_directory_still_reports_no_original(tmp_path: Path) -> None:
    from compliance_platform.core.config import Settings

    settings = Settings(data_raw_dir=tmp_path / "does-not-exist")

    assert original_store.path_for(settings, "doc-1") is None


def test_no_check_then_act_remains_in_the_service_layer() -> None:
    """A regression guard on the pattern rather than on one site. The
    next `exists()` before an open would reopen the window, and would
    look perfectly reasonable in review.
    """
    services = Path(__file__).resolve().parents[1]
    offenders = [
        path.name
        for path in services.glob("*.py")
        if ".exists()" in path.read_text(encoding="utf-8")
    ]

    assert not offenders, f"check-then-act reintroduced in: {offenders}"
