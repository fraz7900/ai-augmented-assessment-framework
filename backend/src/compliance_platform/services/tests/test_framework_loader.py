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

    Sprint 11 (ADR-0023) added a second, independent entry pairing
    ACCESS-1a with NERC CIP's CIP-007-5.3 — a real test of the
    generalized N-framework schema: ACCESS-1a now genuinely has
    equivalents in two different frameworks, both correctly merged into
    one list, not overwriting each other.
    """
    framework = _registry().require("C2M2")
    practice = _find_practice(framework, "ACCESS-1a")
    assert practice is not None
    assert len(practice.equivalents) == 2
    by_framework = {e.framework_name: e for e in practice.equivalents}
    assert by_framework["NIST CSF 2.0"].practice_id == "PR.AA-01"
    assert by_framework["NERC CIP"].practice_id == "CIP-007-5.3"
    assert all(e.rationale for e in practice.equivalents)  # real text, not blank


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
    assert _registry().get("FedRAMP") is None


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


# --- NERC CIP (ADR-0021 started the roadmap extension with CIP-004-7
# only; ADR-0022 completed the remaining 12 standards — all 13 are now
# fully transcribed, mirroring C2M2's ADR-0009 -> ADR-0018 arc) ---


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


def test_all_nerc_cip_standards_are_fully_populated() -> None:
    """ADR-0022: all 13 currently-mandatory standards now have real,
    transcribed Requirements/Parts — 141 is this file's own asserted
    total (backend/scripts/generate_nerc_cip_yaml.py), matching the
    same "assert at generation time and again at load time" pattern
    test_nist_csf_subcategory_count_matches_the_official_total and
    test_all_c2m2_domains_are_fully_populated already use.
    """
    framework = _registry().require("NERC CIP")
    assert all(d.practices_populated for d in framework.domains)
    assert all(d.source_version for d in framework.domains)
    assert all(d.source_url for d in framework.domains)
    assert len(framework.all_practice_ids()) == 141


def test_cip_004_practice_count_matches_source_document() -> None:
    framework = _registry().require("NERC CIP")
    cip004 = framework.domain("CIP-004")
    assert cip004 is not None
    assert cip004.source_version == "CIP-004-7"
    assert len(cip004.practice_ids()) == 19


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


def test_nerc_cip_standard_without_applicable_systems_table_has_empty_applicability() -> None:
    """CIP-002 (impact categorization itself), CIP-012, and CIP-014
    (physical security of Transmission stations, not BES Cyber Systems
    by impact tier) genuinely have no "Applicable Systems" table in
    their source text — empty applicability here is a real structural
    fact about these standards, not a missed transcription (see the
    nerc-cip-expert skill).
    """
    framework = _registry().require("NERC CIP")
    for standard, practice_id in [("CIP-002", "CIP-002-1.1"), ("CIP-012", "CIP-012-1.1"), ("CIP-014", "CIP-014-4.1")]:
        practice = _find_practice(framework, practice_id)
        assert practice is not None, f"{practice_id} not found"
        assert practice.applicability == ""


def test_nerc_cip_atomic_requirement_with_no_parts_has_bare_practice_id() -> None:
    """CIP-003's R3/R4 and CIP-013's R2/R3 have no sub-numbered Parts in
    the source text — the Requirement itself is the atomic practice,
    so its id has no decimal part number.
    """
    framework = _registry().require("NERC CIP")
    for practice_id in ["CIP-003-3", "CIP-003-4", "CIP-013-2", "CIP-013-3"]:
        practice = _find_practice(framework, practice_id)
        assert practice is not None, f"{practice_id} not found"


def test_nerc_cip_domain_for_practice_id_resolves_correctly() -> None:
    framework = _registry().require("NERC CIP")
    domain = framework.domain_for_practice_id("CIP-004-3.2")
    assert domain is not None
    assert domain.short_code == "CIP-004"


# --- NERC CIP <-> C2M2 cross-framework equivalence (ADR-0023) ---


def test_nerc_cip_practice_with_curated_equivalents_points_to_c2m2_and_iso() -> None:
    """CIP-007-5.3 has five real, reviewed entries in
    framework_mapping/cross_framework_equivalence.yaml — one to C2M2's
    ACCESS-1a (ADR-0023), one to ISO 27001's A.8.2 (ADR-0024), one to
    CIS Controls' 5.1 (ADR-0025), one to SOC 2's CC6.2 (ADR-0026), one
    to PCI DSS's 8.6 (ADR-0027) — merged correctly into one list by the
    same generic two-sided schema (framework_a/practice_a_id/
    framework_b/practice_b_id) every pairing in this file uses, not a
    special case per framework pair.

    This is also the regression test for a real bug found while adding
    PCI DSS: CIS Controls' Safeguard "5.1" and PCI DSS's Section "5.1"
    are the identical bare ID string, and the loader's practice-text
    index used to be keyed by bare practice_id alone — so loading PCI
    DSS silently overwrote CIS Controls' entry in that index, and this
    exact practice's CIS Controls equivalent resolved to PCI DSS's name
    and text instead. Fixed by keying the index by (framework_name,
    practice_id) and having _merge_equivalents look up the entry's own
    framework_a/framework_b field, not just the bare other_id.
    """
    framework = _registry().require("NERC CIP")
    practice = _find_practice(framework, "CIP-007-5.3")
    assert practice is not None
    assert len(practice.equivalents) == 5
    by_framework = {e.framework_name: e for e in practice.equivalents}
    assert by_framework["C2M2"].practice_id == "ACCESS-1a"
    assert by_framework["ISO 27001"].practice_id == "A.8.2"
    assert by_framework["CIS Controls"].practice_id == "5.1"
    assert by_framework["SOC 2"].practice_id == "CC6.2"
    assert by_framework["PCI DSS"].practice_id == "8.6"
    assert all(e.rationale for e in practice.equivalents)  # real text, not blank


def test_nerc_cip_practice_without_curated_equivalence_entry_has_empty_list() -> None:
    """CIP-002-1.1 (BES Cyber System impact categorization) has no
    equivalent in C2M2 (ADR-0023), ISO 27001 (ADR-0024), CIS Controls
    (ADR-0025), SOC 2 (ADR-0026), or PCI DSS (ADR-0027) — a real,
    confirmed standards gap in all five reviews, not an oversight.
    """
    framework = _registry().require("NERC CIP")
    practice = _find_practice(framework, "CIP-002-1.1")
    assert practice is not None
    assert practice.equivalents == []


def test_nerc_cip_equivalence_review_is_partial_and_disclosed() -> None:
    """ADR-0023 (C2M2) + ADR-0024 (ISO 27001) + ADR-0025 (CIS Controls)
    + ADR-0026 (SOC 2) + ADR-0027 (PCI DSS): 118 of 141 NERC CIP
    practices have at least one reviewed equivalent (393 entries total
    across all five pairings — 103 practices have more than one
    equivalent). NERC CIP <-> NIST CSF 2.0 remains separate, unstarted
    future work. Asserted against the real committed file so a future
    edit that silently changes this count is caught, mirroring how the
    C2M2/NIST coverage counts are pinned elsewhere in this project's own
    documentation.
    """
    framework = _registry().require("NERC CIP")
    covered = [p for d in framework.domains for p in d.all_practices() if p.equivalents]
    assert len(covered) == 118
    total_entries = sum(len(p.equivalents) for p in covered)
    assert total_entries == 393
    both = [p for p in covered if len(p.equivalents) > 1]
    assert len(both) == 103
    seen_frameworks = {e.framework_name for p in covered for e in p.equivalents}
    assert seen_frameworks == {"C2M2", "ISO 27001", "CIS Controls", "SOC 2", "PCI DSS"}


# --- NERC CIP <-> ISO 27001 cross-framework equivalence (ADR-0024) ---


def test_nerc_cip_practice_with_curated_iso_equivalent_points_back() -> None:
    """The ISO 27001 side of the same pairing resolves correctly too —
    A.8.2's equivalents list includes CIP-007-5.3, confirming the merge
    works symmetrically regardless of which framework is loaded first.
    """
    framework = _registry().require("ISO 27001")
    practice = _find_practice(framework, "A.8.2")
    assert practice is not None
    equivalent = next(e for e in practice.equivalents if e.framework_name == "NERC CIP")
    assert equivalent.practice_id == "CIP-007-5.3"


# --- ISO 27001 (ADR-0024 — titles-only, since the full standard is a paid,
# copyrighted publication with no free full-text access) ---


def test_iso_27001_loads_with_all_four_annex_a_themes() -> None:
    framework = _registry().require("ISO 27001")
    assert framework.scoring_model == "coverage"
    assert len(framework.domains) == 4
    assert {d.short_code for d in framework.domains} == {"A.5", "A.6", "A.7", "A.8"}


def test_iso_27001_annex_a_control_count_matches_the_official_total() -> None:
    """93 is ISO's own stated Annex A total (37 Organizational + 8 People +
    14 Physical + 34 Technological); the generator script asserts this at
    write time, and this test asserts it again at load time, mirroring
    test_nist_csf_subcategory_count_matches_the_official_total and
    test_all_c2m2_domains_are_fully_populated above.
    """
    framework = _registry().require("ISO 27001")
    assert len(framework.all_practice_ids()) == 93
    assert all(d.practices_populated for d in framework.domains)


def test_iso_27001_practice_text_is_a_title_not_a_full_requirement() -> None:
    """Confirms the deliberate scope decision: Practice.text holds the real,
    verified official control TITLE only (short), never the full
    descriptive "shall" requirement text the paid standard contains.
    Practice.mil is always None (ISO 27001 has no MIL concept, like NIST
    CSF 2.0 and NERC CIP) and applicability is always empty (ISO 27001
    Annex A has no per-control applicability-scope column).
    """
    framework = _registry().require("ISO 27001")
    practice = _find_practice(framework, "A.8.24")
    assert practice is not None
    assert practice.text == "Use of cryptography"
    assert len(practice.text) < 100  # a title, not a multi-sentence requirement
    assert practice.mil is None
    assert practice.applicability == ""


# --- CIS Controls v8 (ADR-0025 — genuinely free under CC BY-NC-ND 4.0,
# so unlike ISO 27001, Practice.text holds the full official Safeguard
# description, not a title only) ---


def test_cis_controls_loads_with_all_eighteen_controls() -> None:
    framework = _registry().require("CIS Controls")
    assert framework.scoring_model == "coverage"
    assert len(framework.domains) == 18
    assert {d.short_code for d in framework.domains} == {f"CIS-{i:02d}" for i in range(1, 19)}


def test_cis_controls_safeguard_count_matches_the_official_total() -> None:
    """153 is CIS Controls v8's own stated Safeguard total across 18
    Controls; the generator script asserts this at write time, and this
    test asserts it again at load time, mirroring
    test_iso_27001_annex_a_control_count_matches_the_official_total and
    test_nist_csf_subcategory_count_matches_the_official_total above.
    """
    framework = _registry().require("CIS Controls")
    assert len(framework.all_practice_ids()) == 153
    assert all(d.practices_populated for d in framework.domains)


def test_cis_controls_practice_has_full_description_and_real_ig_applicability() -> None:
    """Unlike ISO 27001's title-only Practice.text, CIS Controls v8's
    license (Creative Commons Attribution-NonCommercial-No Derivatives
    4.0) permits redistributing the full official Safeguard text, so
    Practice.text here is the complete description, not just a title.
    Practice.applicability holds the real Implementation Group (IG1/
    IG2/IG3) markers — a genuine reuse of the applicability field
    ADR-0021 introduced for NERC CIP, not a new schema concept.
    Practice.mil is always None (CIS Controls v8 has no MIL concept).
    """
    framework = _registry().require("CIS Controls")
    practice = _find_practice(framework, "1.1")
    assert practice is not None
    assert practice.text.startswith("Establish and Maintain Detailed Enterprise Asset Inventory.")
    assert len(practice.text) > 200  # a full description, not a short title
    assert practice.mil is None
    assert practice.applicability == "IG1, IG2, IG3"


def test_cis_controls_ig3_only_safeguard_has_narrower_applicability() -> None:
    """Not every Safeguard applies to every Implementation Group — 2.7
    (allowlisting authorized scripts) is IG3-only in the real source
    table, confirming applicability isn't just copied uniformly."""
    framework = _registry().require("CIS Controls")
    practice = _find_practice(framework, "2.7")
    assert practice is not None
    assert practice.applicability == "IG3"


# --- NERC CIP <-> CIS Controls cross-framework equivalence (ADR-0025) ---


def test_cis_controls_practice_equivalent_points_back_to_nerc_cip() -> None:
    """The CIS Controls side of the pairing resolves correctly too —
    5.1's equivalents list includes CIP-007-5.3, confirming the merge
    works symmetrically regardless of which framework is loaded first,
    the same check test_nerc_cip_practice_with_curated_iso_equivalent_points_back
    already does for the ISO 27001 pairing.
    """
    framework = _registry().require("CIS Controls")
    practice = _find_practice(framework, "5.1")
    assert practice is not None
    equivalent = next(e for e in practice.equivalents if e.framework_name == "NERC CIP")
    assert equivalent.practice_id == "CIP-007-5.3"


# --- SOC 2 (ADR-0026 — criterion-statement-only, since AICPA's Trust
# Services Criteria is copyrighted, all-rights-reserved content despite
# being freely downloadable — the same titles-only-equivalent treatment
# ISO 27001 got, not CIS Controls' full-transcription treatment) ---


def test_soc2_loads_with_all_five_categories() -> None:
    framework = _registry().require("SOC 2")
    assert framework.scoring_model == "coverage"
    assert len(framework.domains) == 5
    assert {d.short_code for d in framework.domains} == {"CC", "A", "C", "PI", "P"}


def test_soc2_criteria_count_matches_the_official_total() -> None:
    """61 is the Trust Services Criteria's own total across its 5
    categories (33 Common Criteria + 3 Availability + 2 Confidentiality
    + 5 Processing Integrity + 18 Privacy); the generator script asserts
    this at write time, and this test asserts it again at load time,
    mirroring test_cis_controls_safeguard_count_matches_the_official_total
    and test_iso_27001_annex_a_control_count_matches_the_official_total
    above.
    """
    framework = _registry().require("SOC 2")
    assert len(framework.all_practice_ids()) == 61
    assert all(d.practices_populated for d in framework.domains)


def test_soc2_practice_text_is_a_statement_not_points_of_focus() -> None:
    """Confirms the deliberate scope decision: Practice.text holds the
    real, verified criterion STATEMENT only (the shortest real
    identifying unit for a TSC criterion, the same role a title plays
    for ISO 27001), never the much longer "points of focus" elaboration
    the real source document also contains for every criterion.
    Practice.mil is always None (SOC 2 has no MIL concept, like NIST CSF
    2.0/NERC CIP/ISO 27001/CIS Controls).
    """
    framework = _registry().require("SOC 2")
    practice = _find_practice(framework, "CC6.8")
    assert practice is not None
    assert practice.text == (
        "The entity implements controls to prevent or detect and act upon the introduction of "
        "unauthorized or malicious software to meet the entity's objectives."
    )
    assert len(practice.text) < 200  # a criterion statement, not the points-of-focus elaboration
    assert practice.mil is None


def test_soc2_common_criteria_and_additional_criteria_have_distinct_applicability() -> None:
    """CC1.1 (Common Criteria) is required in every SOC 2 report
    regardless of engagement scope; P1.1 (Privacy, an additional
    category-specific criterion) is required only when Privacy is in
    the engagement's scope — a real, source-verified distinction (TSP
    Section 100, para. .07), the same reuse of the applicability
    concept ADR-0021 (NERC CIP) and ADR-0025 (CIS Controls) already
    established, not a new schema concept.
    """
    framework = _registry().require("SOC 2")
    common = _find_practice(framework, "CC1.1")
    additional = _find_practice(framework, "P1.1")
    assert common is not None and additional is not None
    assert "every SOC 2 report" in common.applicability
    assert "Privacy" in additional.applicability
    assert common.applicability != additional.applicability


# --- NERC CIP <-> SOC 2 cross-framework equivalence (ADR-0026) ---


def test_soc2_practice_equivalent_points_back_to_nerc_cip() -> None:
    """The SOC 2 side of the pairing resolves correctly too — CC6.2 is a
    coarser criterion several NERC CIP parts map onto (the same
    many-NERC-parts-to-one-SOC2-criterion pattern seen throughout this
    pairing), and its equivalents list includes CIP-007-5.3 among them,
    confirming the merge works symmetrically regardless of which
    framework is loaded first, the same check already done for the ISO
    27001 and CIS Controls pairings.
    """
    framework = _registry().require("SOC 2")
    practice = _find_practice(framework, "CC6.2")
    assert practice is not None
    nerc_equivalents = {e.practice_id for e in practice.equivalents if e.framework_name == "NERC CIP"}
    assert "CIP-007-5.3" in nerc_equivalents


# --- PCI DSS (ADR-0027 — Section-level statement-only, since PCI DSS
# v4.0.1 is copyrighted, all-rights-reserved content despite being freely
# downloadable — the same statement-only treatment as ISO 27001/SOC 2,
# but at PCI DSS's own natural "Section" granularity, not its finer
# leaf-level "Defined Approach Requirement" granularity, a disclosed
# scope choice distinct from the copyright question) ---


def test_pci_dss_loads_with_all_twelve_requirements() -> None:
    framework = _registry().require("PCI DSS")
    assert framework.scoring_model == "coverage"
    assert len(framework.domains) == 12
    assert {d.short_code for d in framework.domains} == {f"REQ-{i:02d}" for i in range(1, 13)}


def test_pci_dss_section_count_matches_the_official_total() -> None:
    """63 is PCI DSS v4.0.1's own stated Section total across its 12
    Requirements (5+3+7+2+4+5+3+6+5+7+6+10); the generator script
    asserts this at write time, and this test asserts it again at load
    time, mirroring test_soc2_criteria_count_matches_the_official_total
    and test_cis_controls_safeguard_count_matches_the_official_total
    above.
    """
    framework = _registry().require("PCI DSS")
    assert len(framework.all_practice_ids()) == 63
    assert all(d.practices_populated for d in framework.domains)


def test_pci_dss_practice_text_is_a_section_statement_not_leaf_requirement() -> None:
    """Confirms the deliberate scope decision: Practice.text holds the
    real, verified SECTION-level statement only (e.g. "9.2 Physical
    access controls manage entry into facilities and systems containing
    cardholder data."), never the finer-grained "Defined Approach
    Requirement" text (e.g. 9.2.1, 9.2.2...) or its accompanying Testing
    Procedures/Purpose/Good Practice guidance — PCI DSS is uniquely
    three levels deep (Requirement -> Section -> Defined Approach
    Requirement), unlike every other framework in this project.
    Practice.mil is always None (PCI DSS has no MIL concept) and
    applicability is always empty (no per-Section applicability-scope
    concept was verified in the source, unlike NERC CIP/CIS Controls/
    SOC 2).
    """
    framework = _registry().require("PCI DSS")
    practice = _find_practice(framework, "9.2")
    assert practice is not None
    assert practice.text == (
        "Physical access controls manage entry into facilities and systems containing cardholder data."
    )
    assert practice.mil is None
    assert practice.applicability == ""


# --- NERC CIP <-> PCI DSS cross-framework equivalence (ADR-0027) ---


def test_pci_dss_practice_equivalent_points_back_to_nerc_cip() -> None:
    """The PCI DSS side of the pairing resolves correctly too — Section
    9.2 is a coarser statement several NERC CIP physical-security parts
    map onto, and its equivalents list includes CIP-006-1.1 among them,
    confirming the merge works symmetrically regardless of which
    framework is loaded first, the same check already done for the ISO
    27001, CIS Controls, and SOC 2 pairings.
    """
    framework = _registry().require("PCI DSS")
    practice = _find_practice(framework, "9.2")
    assert practice is not None
    nerc_equivalents = {e.practice_id for e in practice.equivalents if e.framework_name == "NERC CIP"}
    assert "CIP-006-1.1" in nerc_equivalents
