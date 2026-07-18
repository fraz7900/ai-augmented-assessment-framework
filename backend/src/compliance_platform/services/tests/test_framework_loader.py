"""Tests against the real, committed C2M2 YAML data, not a fixture copy
— this is deliberately an integration-flavored unit test: the whole
point of framework_mapping/c2m2_v2_1.yaml is that it is real,
transcribed source content (see ADR-0009), so a test that only ever
exercises a synthetic fixture would not catch a transcription or
loader bug in the actual file this project ships.
"""

from __future__ import annotations

import pytest

from compliance_platform.core.config import get_settings
from compliance_platform.services.framework_loader import FrameworkNotFoundError, FrameworkRegistry


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
    assert _registry().get("ISO 27001") is None


def test_registry_caches_loaded_framework() -> None:
    registry = _registry()
    first = registry.require("C2M2")
    second = registry.require("C2M2")
    assert first is second


# --- NIST CSF 2.0 (Sprint 4) ---


def test_nist_csf_loads_with_all_six_functions_fully_populated() -> None:
    framework = _registry().require("NIST CSF 2.0")
    assert framework.version == "2.0"
    assert framework.scoring_model == "coverage"
    assert len(framework.domains) == 6
    assert {d.short_code for d in framework.domains} == {"GV", "ID", "PR", "DE", "RS", "RC"}
    assert all(d.practices_populated for d in framework.domains)


def test_nist_csf_subcategory_count_matches_the_official_total() -> None:
    """106 is NIST's own stated total (confirmed via WebSearch before
    transcription, see ADR-0010); the generator script asserts this at
    write time, and this test asserts it again at load time so a future
    hand-edit of the committed YAML (against the file's own header
    warning not to) would still be caught.
    """
    framework = _registry().require("NIST CSF 2.0")
    assert len(framework.all_practice_ids()) == 106


def test_protect_function_includes_identity_and_access_control_category() -> None:
    """Grounds this in something demo-relevant: PR.AA is the category
    directly exercised by data/sample_evidence/synthetic_access_control_policy.md,
    mirroring the C2M2 ACCESS domain choice in Sprint 3.
    """
    framework = _registry().require("NIST CSF 2.0")
    protect = framework.domain("PR")
    assert protect is not None
    aa_category = next(o for o in protect.objectives if o.title.startswith("Identity Management"))
    assert aa_category.purpose  # real, transcribed category purpose text, not blank
    assert {"PR.AA-01", "PR.AA-03", "PR.AA-05"} <= {p.id for p in aa_category.practices}


def test_govern_function_has_no_mil_values() -> None:
    """NIST CSF 2.0 subcategories have no native maturity level — see
    ADR-0010 — so Practice.mil must be None throughout, not defaulted
    to some arbitrary number.
    """
    framework = _registry().require("NIST CSF 2.0")
    govern = framework.domain("GV")
    assert govern is not None
    assert all(p.mil is None for p in govern.all_practices())


def test_nist_registry_and_c2m2_registry_coexist() -> None:
    registry = _registry()
    c2m2 = registry.require("C2M2")
    nist = registry.require("NIST CSF 2.0")
    assert c2m2.scoring_model == "cumulative_mil"
    assert nist.scoring_model == "coverage"


# --- Sprint 9: closing real, measured coverage gaps — require()'s own
# failure path, and get()'s "known name but the YAML file is actually
# missing on disk" branch, had no test despite require() being used
# throughout this file's happy-path tests above. ---


def test_get_returns_none_for_unrecognized_framework_name() -> None:
    assert _registry().get("Not A Real Framework") is None


def test_require_raises_for_unrecognized_framework_name() -> None:
    with pytest.raises(FrameworkNotFoundError):
        _registry().require("Not A Real Framework")


def test_get_returns_none_when_known_filename_is_missing_on_disk(tmp_path) -> None:
    """A name in _KNOWN_FRAMEWORKS (e.g. "C2M2") but pointed at a
    directory where the actual YAML file doesn't exist — the get()
    branch distinct from an unrecognized name entirely.
    """
    registry = FrameworkRegistry(tmp_path)
    assert registry.get("C2M2") is None
