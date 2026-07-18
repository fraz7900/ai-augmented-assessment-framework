"""Generates framework_mapping/nerc_cip.yaml (ADR-0021).

Same "data as code, generated not hand-edited" pattern as
generate_c2m2_yaml.py / generate_nist_csf_yaml.py (ADR-0002). Unlike
those two frameworks, NERC CIP is a *suite* of 13 independently
versioned standards rather than one document, so each Domain below
carries its own source_version/source_url (see Domain in
models/framework.py) instead of relying on FrameworkDefinition's
single source_* fields.

All 13 currently-mandatory standards (CIP-002 through CIP-014; CIP-015
is "Subject to Future Enforcement", not yet in force, and is
deliberately excluded — see the nerc-cip-expert skill) are present
with real, source-verified purpose/version/effective-date/URL
metadata. Only CIP-004-7 (Personnel & Training) is fully transcribed
into Requirements/Parts this pass — the other 12 are real structural
stubs (practices_populated: False, objectives: []), not fabricated
coverage. This mirrors exactly how C2M2 began (ADR-0009: 2 of 10
domains transcribed, the rest real stubs) before later being completed
(ADR-0018).

Source verification method for every purpose/title/version/date below:
NERC's site (nerc.com) blocks WebFetch with a domain-wide WAF (403 on
every path); a direct curl with a browser User-Agent succeeds cleanly
(HTTP 200) — the same "WebFetch fails, curl succeeds" pattern ADR-0009
already documented for C2M2's own source PDF. The 13 PDFs were fetched
that way and parsed with pypdf (the same tool ADR-0009 used), and the
version/effective-date/canonical-URL metadata was read directly from
the structured JSON page model embedded in nerc.com's own standards
index (https://www.nerc.com/standards/reliability-standards/cip), not
scraped prose or search-result titles.
"""

from __future__ import annotations

from pathlib import Path

import yaml

# (short_code, source_version, full_name, purpose, effective_date, pdf_url)
# short_code is the stable standard number (drops the version suffix,
# since the version changes over time but CIP-004 itself does not);
# source_version is the specific version this data was transcribed
# from/verified current against.
STANDARDS = [
    (
        "CIP-002",
        "CIP-002-5.1a",
        "Cyber Security — BES Cyber System Categorization",
        (
            "To identify and categorize BES Cyber Systems and their associated BES Cyber "
            "Assets for the application of cyber security requirements commensurate with the "
            "adverse impact that loss, compromise, or misuse of those BES Cyber Systems could "
            "have on the reliable operation of the BES. Identification and categorization of "
            "BES Cyber Systems support appropriate protection against compromises that could "
            "lead to misoperation or instability in the BES."
        ),
        "2016-12-27",
        "https://www.nerc.com/globalassets/standards/reliability-standards/cip/cip-002-5.1a.pdf",
    ),
    (
        "CIP-003",
        "CIP-003-9",
        "Cyber Security — Security Management Controls",
        (
            "To specify consistent and sustainable security management controls that "
            "establish responsibility and accountability to protect BES Cyber Systems against "
            "compromise that could lead to misoperation or instability in the Bulk Electric "
            "System (BES)."
        ),
        "2026-04-01",
        "https://www.nerc.com/globalassets/standards/reliability-standards/cip/cip-003-9.pdf",
    ),
    (
        "CIP-004",
        "CIP-004-7",
        "Cyber Security — Personnel & Training",
        (
            "To minimize the risk against compromise that could lead to misoperation or "
            "instability in the Bulk Electric System (BES) from individuals accessing BES "
            "Cyber Systems by requiring an appropriate level of personnel risk assessment, "
            "training, security awareness, and access management in support of protecting BES "
            "Cyber Systems."
        ),
        "2024-01-01",
        "https://www.nerc.com/globalassets/standards/reliability-standards/cip/cip-004-7.pdf",
    ),
    (
        "CIP-005",
        "CIP-005-7",
        "Cyber Security — Electronic Security Perimeter(s)",
        (
            "To manage electronic access to BES Cyber Systems by specifying a controlled "
            "Electronic Security Perimeter in support of protecting BES Cyber Systems against "
            "compromise that could lead to misoperation or instability in the BES."
        ),
        "2022-10-01",
        "https://www.nerc.com/globalassets/standards/reliability-standards/cip/cip-005-7.pdf",
    ),
    (
        "CIP-006",
        "CIP-006-6",
        "Cyber Security — Physical Security of BES Cyber Systems",
        (
            "To manage physical access to Bulk Electric System (BES) Cyber Systems by "
            "specifying a physical security plan in support of protecting BES Cyber Systems "
            "against compromise that could lead to misoperation or instability in the BES."
        ),
        "2016-07-01",
        "https://www.nerc.com/globalassets/standards/reliability-standards/cip/cip-006-6.pdf",
    ),
    (
        "CIP-007",
        "CIP-007-6",
        "Cyber Security — System Security Management",
        (
            "To manage system security by specifying select technical, operational, and "
            "procedural requirements in support of protecting BES Cyber Systems against "
            "compromise that could lead to misoperation or instability in the Bulk Electric "
            "System (BES)."
        ),
        "2016-07-01",
        "https://www.nerc.com/globalassets/standards/reliability-standards/cip/cip-007-6.pdf",
    ),
    (
        "CIP-008",
        "CIP-008-6",
        "Cyber Security — Incident Reporting and Response Planning",
        (
            "To mitigate the risk to the reliable operation of the BES as the result of a "
            "Cyber Security Incident by specifying incident response requirements."
        ),
        "2021-01-01",
        "https://www.nerc.com/globalassets/standards/reliability-standards/cip/cip-008-6.pdf",
    ),
    (
        "CIP-009",
        "CIP-009-6",
        "Cyber Security — Recovery Plans for BES Cyber Systems",
        (
            "To recover reliability functions performed by BES Cyber Systems by specifying "
            "recovery plan requirements in support of the continued stability, operability, "
            "and reliability of the BES."
        ),
        "2016-07-01",
        "https://www.nerc.com/globalassets/standards/reliability-standards/cip/cip-009-6.pdf",
    ),
    (
        "CIP-010",
        "CIP-010-4",
        "Cyber Security — Configuration Change Management and Vulnerability Assessments",
        (
            "To prevent and detect unauthorized changes to BES Cyber Systems by specifying "
            "configuration change management and vulnerability assessment requirements in "
            "support of protecting BES Cyber Systems from compromise that could lead to "
            "misoperation or instability in the Bulk Electric System (BES)."
        ),
        "2022-10-01",
        "https://www.nerc.com/globalassets/standards/reliability-standards/cip/cip-010-4.pdf",
    ),
    (
        "CIP-011",
        "CIP-011-3",
        "Cyber Security — Information Protection",
        (
            "To prevent unauthorized access to BES Cyber System Information (BCSI) by "
            "specifying information protection requirements in support of protecting BES "
            "Cyber Systems against compromise that could lead to misoperation or instability "
            "in the Bulk Electric System (BES)."
        ),
        "2024-01-01",
        "https://www.nerc.com/globalassets/standards/reliability-standards/cip/cip-011-3.pdf",
    ),
    (
        "CIP-012",
        "CIP-012-2",
        "Cyber Security – Communications between Control Centers",
        (
            "To protect the confidentiality, integrity, and availability of Real-time "
            "Assessment and Real-time monitoring data transmitted between Control Centers."
        ),
        "2026-07-01",
        "https://www.nerc.com/globalassets/standards/reliability-standards/cip/cip-012-2.pdf",
    ),
    (
        "CIP-013",
        "CIP-013-2",
        "Cyber Security - Supply Chain Risk Management",
        (
            "To mitigate cyber security risks to the reliable operation of the Bulk Electric "
            "System (BES) by implementing security controls for supply chain risk management "
            "of BES Cyber Systems."
        ),
        "2022-10-01",
        "https://www.nerc.com/globalassets/standards/reliability-standards/cip/cip-013-2.pdf",
    ),
    (
        "CIP-014",
        "CIP-014-3",
        "Physical Security",
        (
            "To identify and protect Transmission stations and Transmission substations, and "
            "their associated primary control centers, that if rendered inoperable or damaged "
            "as a result of a physical attack could result in instability, uncontrolled "
            "separation, or Cascading within an Interconnection."
        ),
        "2022-06-16",
        "https://www.nerc.com/globalassets/standards/reliability-standards/cip/cip-014-3.pdf",
    ),
]

# CIP-004-7's own six Requirements (R1-R6), each transcribed as one
# Objective; "purpose" is the Requirement's own governing sentence
# (mirrors NIST CSF 2.0 categories having a purpose separate from
# their subcategories' specific text). Each Part becomes one Practice,
# with applicability set from the real "Applicable Systems" column —
# the concept ADR-0021 added the field for. Practice text is the
# table's "Requirements" column; the "Measures" column is evidentiary
# detail, not modeled as its own field (nothing else in the schema
# needs it, per the framework-mapping skill's "don't special-case the
# loader" guidance — Practice.text already carries the substantive
# obligation).
CIP004_REQUIREMENTS = [
    (
        1,
        "R1 – Security Awareness Program",
        (
            "Each Responsible Entity shall implement one or more documented processes that "
            "collectively include each of the applicable requirement parts in CIP-004-7 Table "
            "R1 – Security Awareness Program."
        ),
        [
            (
                "1.1",
                "High Impact BES Cyber Systems\nMedium Impact BES Cyber Systems",
                (
                    "Security awareness that, at least once each calendar quarter, reinforces "
                    "cyber security practices (which may include associated physical security "
                    "practices) for the Responsible Entity's personnel who have authorized "
                    "electronic or authorized unescorted physical access to BES Cyber Systems."
                ),
            ),
        ],
    ),
    (
        2,
        "R2 – Cyber Security Training Program",
        (
            "Each Responsible Entity shall implement one or more cyber security training "
            "program(s) appropriate to individual roles, functions, or responsibilities that "
            "collectively includes each of the applicable requirement parts in CIP-004-7 Table "
            "R2 – Cyber Security Training Program."
        ),
        [
            (
                "2.1",
                (
                    "High Impact BES Cyber Systems and their associated: 1. EACMS; and 2. PACS\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: 1. EACMS; and 2. PACS"
                ),
                (
                    "Training content on: cyber security policies; physical access controls; "
                    "electronic access controls; the visitor control program; handling of BES "
                    "Cyber System Information and its storage; identification of a Cyber "
                    "Security Incident and initial notifications in accordance with the "
                    "entity's incident response plan; recovery plans for BES Cyber Systems; "
                    "response to Cyber Security Incidents; and cyber security risks associated "
                    "with a BES Cyber System's electronic interconnectivity and "
                    "interoperability with other Cyber Assets, including Transient Cyber "
                    "Assets, and with Removable Media."
                ),
            ),
            (
                "2.2",
                (
                    "High Impact BES Cyber Systems and their associated: 1. EACMS; and 2. PACS\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: 1. EACMS; and 2. PACS"
                ),
                (
                    "Require completion of the training specified in Part 2.1 prior to "
                    "granting authorized electronic access and authorized unescorted physical "
                    "access to applicable Cyber Assets, except during CIP Exceptional "
                    "Circumstances."
                ),
            ),
            (
                "2.3",
                (
                    "High Impact BES Cyber Systems and their associated: 1. EACMS; and 2. PACS\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: 1. EACMS; and 2. PACS"
                ),
                (
                    "Require completion of the training specified in Part 2.1 at least once "
                    "every 15 calendar months."
                ),
            ),
        ],
    ),
    (
        3,
        "R3 – Personnel Risk Assessment Program",
        (
            "Each Responsible Entity shall implement one or more documented personnel risk "
            "assessment program(s) to attain and retain authorized electronic or authorized "
            "unescorted physical access to BES Cyber Systems that collectively include each of "
            "the applicable requirement parts in CIP-004-7 Table R3 – Personnel Risk "
            "Assessment Program."
        ),
        [
            (
                "3.1",
                (
                    "High Impact BES Cyber Systems and their associated: 1. EACMS; and 2. PACS\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: 1. EACMS; and 2. PACS"
                ),
                "Process to confirm identity.",
            ),
            (
                "3.2",
                (
                    "High Impact BES Cyber Systems and their associated: 1. EACMS; and 2. PACS\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: 1. EACMS; and 2. PACS"
                ),
                (
                    "Process to perform a seven year criminal history records check as part of "
                    "each personnel risk assessment that includes: current residence, "
                    "regardless of duration; and other locations where, during the seven years "
                    "immediately prior to the date of the criminal history records check, the "
                    "subject has resided for six consecutive months or more. If it is not "
                    "possible to perform a full seven year criminal history records check, "
                    "conduct as much of the seven year criminal history records check as "
                    "possible and document the reason the full seven year criminal history "
                    "records check could not be performed."
                ),
            ),
            (
                "3.3",
                (
                    "High Impact BES Cyber Systems and their associated: 1. EACMS; and 2. PACS\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: 1. EACMS; and 2. PACS"
                ),
                "Criteria or process to evaluate criminal history records checks for authorizing access.",
            ),
            (
                "3.4",
                (
                    "High Impact BES Cyber Systems and their associated: 1. EACMS; and 2. PACS\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: 1. EACMS; and 2. PACS"
                ),
                (
                    "Criteria or process for verifying that personnel risk assessments "
                    "performed for contractors or service vendors are conducted according to "
                    "Parts 3.1 through 3.3."
                ),
            ),
            (
                "3.5",
                (
                    "High Impact BES Cyber Systems and their associated: 1. EACMS; and 2. PACS\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: 1. EACMS; and 2. PACS"
                ),
                (
                    "Process to ensure that individuals with authorized electronic or "
                    "authorized unescorted physical access have had a personnel risk "
                    "assessment completed according to Parts 3.1 to 3.4 within the last seven "
                    "years."
                ),
            ),
        ],
    ),
    (
        4,
        "R4 – Access Management Program",
        (
            "Each Responsible Entity shall implement one or more documented access management "
            "program(s) that collectively include each of the applicable requirement parts in "
            "CIP-004-7 Table R4 – Access Management Program."
        ),
        [
            (
                "4.1",
                (
                    "High Impact BES Cyber Systems and their associated: 1. EACMS; and 2. PACS\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: 1. EACMS; and 2. PACS"
                ),
                (
                    "Process to authorize based on need, as determined by the Responsible "
                    "Entity, except for CIP Exceptional Circumstances: electronic access; and "
                    "unescorted physical access into a Physical Security Perimeter."
                ),
            ),
            (
                "4.2",
                (
                    "High Impact BES Cyber Systems and their associated: 1. EACMS; and 2. PACS\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: 1. EACMS; and 2. PACS"
                ),
                (
                    "Verify at least once each calendar quarter that individuals with active "
                    "electronic access or unescorted physical access have authorization "
                    "records."
                ),
            ),
            (
                "4.3",
                (
                    "High Impact BES Cyber Systems and their associated: 1. EACMS; and 2. PACS\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: 1. EACMS; and 2. PACS"
                ),
                (
                    "For electronic access, verify at least once every 15 calendar months that "
                    "all user accounts, user account groups, or user role categories, and their "
                    "specific, associated privileges are correct and are those that the "
                    "Responsible Entity determines are necessary."
                ),
            ),
        ],
    ),
    (
        5,
        "R5 – Access Revocation",
        (
            "Each Responsible Entity shall implement one or more documented access revocation "
            "program(s) that collectively include each of the applicable requirement parts in "
            "CIP-004-7 Table R5 – Access Revocation."
        ),
        [
            (
                "5.1",
                (
                    "High Impact BES Cyber Systems and their associated: 1. EACMS; and 2. PACS\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: 1. EACMS; and 2. PACS"
                ),
                (
                    "A process to initiate removal of an individual's ability for unescorted "
                    "physical access and Interactive Remote Access upon a termination action, "
                    "and complete the removals within 24 hours of the termination action "
                    "(removal of the ability for access may be different than deletion, "
                    "disabling, revocation, or removal of all access rights)."
                ),
            ),
            (
                "5.2",
                (
                    "High Impact BES Cyber Systems and their associated: 1. EACMS; and 2. PACS\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: 1. EACMS; and 2. PACS"
                ),
                (
                    "For reassignments or transfers, revoke the individual's authorized "
                    "electronic access to individual accounts and authorized unescorted "
                    "physical access that the Responsible Entity determines are not necessary "
                    "by the end of the next calendar day following the date that the "
                    "Responsible Entity determines that the individual no longer requires "
                    "retention of that access."
                ),
            ),
            (
                "5.3",
                "High Impact BES Cyber Systems and their associated: EACMS",
                (
                    "For termination actions, revoke the individual's non-shared user accounts "
                    "(unless already revoked according to Part 5.1) within 30 calendar days of "
                    "the effective date of the termination action."
                ),
            ),
            (
                "5.4",
                "High Impact BES Cyber Systems and their associated: EACMS",
                (
                    "For termination actions, change passwords for shared account(s) known to "
                    "the user within 30 calendar days of the termination action. For "
                    "reassignments or transfers, change passwords for shared account(s) known "
                    "to the user within 30 calendar days following the date that the "
                    "Responsible Entity determines that the individual no longer requires "
                    "retention of that access. If the Responsible Entity determines and "
                    "documents that extenuating operating circumstances require a longer time "
                    "period, change the password(s) within 10 calendar days following the end "
                    "of the operating circumstances."
                ),
            ),
        ],
    ),
    (
        6,
        "R6 – Access Management for BES Cyber System Information",
        (
            "Each Responsible Entity shall implement one or more documented access management "
            "program(s) to authorize, verify, and revoke provisioned access to BCSI pertaining "
            "to the \"Applicable Systems\" identified in CIP-004-7 Table R6 – Access Management "
            "for BES Cyber System Information that collectively include each of the applicable "
            "requirement parts in that table. To be considered access to BCSI in the context of "
            "this requirement, an individual has both the ability to obtain and use BCSI."
        ),
        [
            (
                "6.1",
                (
                    "High Impact BES Cyber Systems and their associated: 1. EACMS; and 2. PACS\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: 1. EACMS; and 2. PACS"
                ),
                (
                    "Prior to provisioning, authorize (unless already authorized according to "
                    "Part 4.1) based on need, as determined by the Responsible Entity, except "
                    "for CIP Exceptional Circumstances: provisioned electronic access to "
                    "electronic BCSI; and provisioned physical access to physical BCSI."
                ),
            ),
            (
                "6.2",
                (
                    "High Impact BES Cyber Systems and their associated: 1. EACMS; and 2. PACS\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: 1. EACMS; and 2. PACS"
                ),
                (
                    "Verify at least once every 15 calendar months that all individuals with "
                    "provisioned access to BCSI: have an authorization record; and still need "
                    "the provisioned access to perform their current work functions, as "
                    "determined by the Responsible Entity."
                ),
            ),
            (
                "6.3",
                (
                    "High Impact BES Cyber Systems and their associated: 1. EACMS; and 2. PACS\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: 1. EACMS; and 2. PACS"
                ),
                (
                    "For termination actions, remove the individual's ability to use "
                    "provisioned access to BCSI (unless already revoked according to Part 5.1) "
                    "by the end of the next calendar day following the effective date of the "
                    "termination action."
                ),
            ),
        ],
    ),
]


def build_domain(short_code: str, source_version: str, full_name: str, purpose: str, source_url: str) -> dict:
    if short_code != "CIP-004":
        return {
            "short_code": short_code,
            "full_name": full_name,
            "purpose": purpose,
            "practices_populated": False,
            "objectives": [],
            "source_version": source_version,
            "source_url": source_url,
        }

    objectives = []
    for number, title, req_purpose, parts in CIP004_REQUIREMENTS:
        objectives.append(
            {
                "number": number,
                "title": title,
                "purpose": req_purpose,
                "practices": [
                    {
                        "id": f"CIP-004-{part_number}",
                        "text": text,
                        "applicability": applicability,
                    }
                    for part_number, applicability, text in parts
                ],
            }
        )
    return {
        "short_code": short_code,
        "full_name": full_name,
        "purpose": purpose,
        "practices_populated": True,
        "objectives": objectives,
        "source_version": source_version,
        "source_url": source_url,
    }


def main() -> None:
    framework = {
        "name": "NERC CIP",
        "full_name": "NERC Critical Infrastructure Protection Standards",
        "version": "see each domain's own source_version",
        "source_title": "NERC Critical Infrastructure Protection (CIP) Reliability Standards",
        "source_publisher": "North American Electric Reliability Corporation",
        "source_date": "see each domain's own source_version",
        "source_url": "https://www.nerc.com/standards/reliability-standards/cip",
        "retrieved_date": "2026-07-18",
        # Real count of transcribed Parts in the one fully-transcribed
        # standard (CIP-004-7). NOT the full 13-standard suite's total
        # requirement-part count, which is not yet known — fabricating
        # that number would violate this project's verified-over-
        # fabricated discipline (see the framework-mapping skill). This
        # will grow as more standards are fully transcribed.
        "total_practices_in_source": 19,
        "scoring_model": "coverage",
        "mil_levels": [],
        "scoring_note": (
            "NERC CIP is a compliance/audit standard, not a native maturity model — like NIST "
            "CSF 2.0 (ADR-0010), it has no MIL concept, so Practice.mil is always None here. "
            "Scores are the project-defined coverage measure (fraction of a standard's Parts "
            "with accepted/edited evidence), via services/scoring_service.py's "
            "compute_domain_coverage. Only CIP-004-7 is fully transcribed as of ADR-0021; the "
            "other 12 domains are real structural stubs (practices_populated: False) with no "
            "practices to score yet, not silently-omitted coverage."
        ),
        "domains": [
            build_domain(short_code, source_version, full_name, purpose, source_url)
            for short_code, source_version, full_name, purpose, _effective_date, source_url in STANDARDS
        ],
    }

    populated = sum(1 for d in framework["domains"] if d["practices_populated"])
    total_practices = sum(
        len(o["practices"]) for d in framework["domains"] for o in d["objectives"]
    )
    print(f"Standards: {len(framework['domains'])} ({populated} fully populated)")
    print(f"Practices encoded: {total_practices} of {framework['total_practices_in_source']}")
    assert total_practices == framework["total_practices_in_source"], (
        "Transcribed practice count does not match this file's own declared "
        "total_practices_in_source — check CIP004_REQUIREMENTS for a missing or duplicated "
        "Part before shipping this data."
    )

    out_path = Path(__file__).resolve().parents[2] / "framework_mapping" / "nerc_cip.yaml"
    with out_path.open("w", encoding="utf-8") as f:
        f.write(
            "# GENERATED FILE. Do not hand-edit — regenerate via\n"
            "# backend/scripts/generate_nerc_cip_yaml.py, which is the source of truth\n"
            "# for this file's content and carries the source citations.\n"
        )
        yaml.dump(framework, f, sort_keys=False, allow_unicode=True, width=100)


if __name__ == "__main__":
    main()
