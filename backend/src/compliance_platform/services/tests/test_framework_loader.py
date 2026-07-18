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


def _find_practice(framework, practice_id: str):
    for domain in framework.domains:
        for objective in domain.objectives:
            for practice in objective.practices:
                if practice.id == practice_id:
                    return practice
    return None


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


def test_all_c2m2_domains_are_fully_populated() -> None:
    """Sprint 10 follow-up (US-3.1a): the remaining 8 domains (THREAT,
    RISK, SITUATION, RESPONSE, THIRD-PARTIES, WORKFORCE, ARCHITECTURE,
    PROGRAM) were transcribed from the same source PDF (see
    backend/scripts/generate_c2m2_yaml.py's module docstring) — C2M2 is
    no longer partially populated. 356 is the source document's own
    stated total (total_practices_in_source), asserted at generation
    time by the script and again here at load time, mirroring
    test_nist_csf_subcategory_count_matches_the_official_total below.
    """
    framework = _registry().require("C2M2")
    assert all(d.practices_populated for d in framework.domains)
    assert len(framework.all_practice_ids()) == 356


def test_c2m2_practice_with_curated_equivalent_is_populated() -> None:
    """Sprint 10 (US-5.2/FR-14, ADR-0019): ACCESS-1a has a real, reviewed
    entry in framework_mapping/cross_framework_equivalence.yaml pointing
    at NIST CSF 2.0's PR.AA-01. Asserted against the real committed file,
    same discipline as the rest of this test module.
    """
    framework = _registry().require("C2M2")
    practice = _find_practice(framework, "ACCESS-1a")
    assert practice is not None
    assert len(practice.equivalents) == 1
    equivalent = practice.equivalents[0]
    assert equivalent.framework_name == "NIST CSF 2.0"
    assert equivalent.practice_id == "PR.AA-01"
    assert equivalent.rationale  # real text, not blank


def test_nist_practice_with_curated_equivalent_points_back_to_c2m2() -> None:
    framework = _registry().require("NIST CSF 2.0")
    practice = _find_practice(framework, "PR.AA-01")
    assert practice is not None
    assert len(practice.equivalents) == 1
    equivalent = practice.equivalents[0]
    assert equivalent.framework_name == "C2M2"
    assert equivalent.practice_id == "ACCESS-1a"


def test_practice_without_curated_equivalence_entry_has_empty_list() -> None:
    """Empty, not missing/None — see models/framework.py's Practice.equivalents
    default, so callers never need a null check."""
    framework = _registry().require("C2M2")
    practice = _find_practice(framework, "ASSET-1b")
    assert practice is not None
    assert practice.equivalents == []


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


# --- NERC CIP (ADR-0021 — roadmap extension started, not fully
# transcribed: 13 standards present as real sourced stubs, only
# CIP-004-7 fully transcribed) ---


def test_nerc_cip_loads_with_all_thirteen_currently_mandatory_standards() -> None:
    framework = _registry().require("NERC CIP")
    assert framework.scoring_model == "coverage"
    assert len(framework.domains) == 13
    assert {d.short_code for d in framework.domains} == {
        "CIP-002",
        "CIP-003",
        "CIP-004",
        "CIP-005",
        "CIP-006",
        "CIP-007",
        "CIP-008",
        "CIP-009",
        "CIP-010",
        "CIP-011",
        "CIP-012",
        "CIP-013",
        "CIP-014",
    }


def test_cip_004_is_fully_populated_and_others_are_real_stubs() -> None:
    """Mirrors C2M2's original Sprint 3 state (ADR-0009): partial-but-real,
    not fabricated-complete. Only CIP-004-7 has practices transcribed;
    the other 12 domains are honest stubs with real purpose/version/url
    but no objectives yet.
    """
    framework = _registry().require("NERC CIP")
    cip004 = framework.domain("CIP-004")
    assert cip004 is not None
    assert cip004.practices_populated
    assert cip004.source_version == "CIP-004-7"
    assert len(cip004.practice_ids()) == 19

    stubs = [d for d in framework.domains if d.short_code != "CIP-004"]
    assert len(stubs) == 12
    assert all(not d.practices_populated for d in stubs)
    assert all(d.objectives == [] for d in stubs)
    # Real, source-verified metadata even though unpopulated — not blank.
    assert all(d.purpose for d in stubs)
    assert all(d.source_version for d in stubs)
    assert all(d.source_url for d in stubs)


def test_cip_004_practice_has_real_applicability_text() -> None:
    """The whole reason ADR-0021 added Practice.applicability: NERC CIP's
    "Applicable Systems" column varies per Part by BES Cyber System
    impact tier, unlike anything in C2M2/NIST CSF 2.0.
    """
    framework = _registry().require("NERC CIP")
    practice = _find_practice(framework, "CIP-004-1.1")
    assert practice is not None
    assert practice.mil is None
    assert "High Impact BES Cyber Systems" in practice.applicability


def test_c2m2_and_nist_practices_have_empty_applicability() -> None:
    """Backward-compat: the new field is additive and empty for every
    practice in frameworks that predate it.
    """
    c2m2 = _registry().require("C2M2")
    nist = _registry().require("NIST CSF 2.0")
    assert _find_practice(c2m2, "ACCESS-1a").applicability == ""
    assert _find_practice(nist, "PR.AA-01").applicability == ""


def test_nerc_cip_domain_for_practice_id_resolves_correctly() -> None:
    framework = _registry().require("NERC CIP")
    domain = framework.domain_for_practice_id("CIP-004-3.2")
    assert domain is not None
    assert domain.short_code == "CIP-004"
