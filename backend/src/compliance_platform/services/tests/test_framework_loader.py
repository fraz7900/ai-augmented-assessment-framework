"""Tests against the real, committed C2M2 YAML data, not a fixture copy
— this is deliberately an integration-flavored unit test: the whole
point of framework_mapping/c2m2_v2_1.yaml is that it is real,
transcribed source content (see ADR-0009), so a test that only ever
exercises a synthetic fixture would not catch a transcription or
loader bug in the actual file this project ships.
"""

from __future__ import annotations

from compliance_platform.core.config import get_settings
from compliance_platform.services.framework_loader import FrameworkRegistry


def _registry() -> FrameworkRegistry:
    settings = get_settings()
    return FrameworkRegistry(settings.framework_mapping_dir)


def test_c2m2_loads_with_all_ten_domains() -> None:
    framework = _registry().require("C2M2")
    assert framework.version == "2.1"
    assert len(framework.domains) == 10
    assert {d.short_code for d in framework.domains} == {
        "ASSET",
        "THREAT",
        "RISK",
        "ACCESS",
        "SITUATION",
        "RESPONSE",
        "THIRD-PARTIES",
        "WORKFORCE",
        "ARCHITECTURE",
        "PROGRAM",
    }


def test_access_and_asset_domains_are_fully_populated() -> None:
    framework = _registry().require("C2M2")
    access = framework.domain("ACCESS")
    asset = framework.domain("ASSET")
    assert access is not None and access.practices_populated
    assert asset is not None and asset.practices_populated
    # Counts transcribed directly from the source PDF (see
    # backend/scripts/generate_c2m2_yaml.py): ACCESS = 10+9+10+6 = 35,
    # ASSET = 8+8+5+9+6 = 36.
    assert len(access.practice_ids()) == 35
    assert len(asset.practice_ids()) == 36


def test_unpopulated_domains_have_no_practices_but_do_have_a_purpose() -> None:
    framework = _registry().require("C2M2")
    risk = framework.domain("RISK")
    assert risk is not None
    assert risk.practices_populated is False
    assert risk.objectives == []
    assert risk.purpose  # still has real, verified purpose text


def test_domain_for_practice_id_resolves_correctly() -> None:
    framework = _registry().require("C2M2")
    domain = framework.domain_for_practice_id("ACCESS-2f")
    assert domain is not None
    assert domain.short_code == "ACCESS"


def test_management_activities_objective_has_no_mil1_practices() -> None:
    """Verifies the structural pattern confirmed in the source document
    (Table 4 / the ACCESS and ASSET domain sections): the final
    "Management Activities" objective in a domain has no MIL1 practices,
    only MIL2 and MIL3.
    """
    framework = _registry().require("C2M2")
    access = framework.domain("ACCESS")
    assert access is not None
    management_objective = next(
        o for o in access.objectives if o.title == "Management Activities for the ACCESS domain"
    )
    mils_present = {p.mil for p in management_objective.practices}
    assert 1 not in mils_present
    assert mils_present == {2, 3}


def test_get_returns_none_for_unknown_framework() -> None:
    assert _registry().get("NIST CSF 2.0") is None


def test_registry_caches_loaded_framework() -> None:
    registry = _registry()
    first = registry.require("C2M2")
    second = registry.require("C2M2")
    assert first is second
