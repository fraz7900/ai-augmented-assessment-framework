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
metadata, and all 13 are now fully transcribed into Requirements/Parts
(ADR-0021 started with CIP-004-7 only; ADR-0022 completed the
remaining 12), mirroring how C2M2 began partial (ADR-0009) before
later being completed (ADR-0018).

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

# CIP-002-5.1a — the impact-categorization standard. Structurally
# different from CIP-004's table pattern: no "Applicable Systems"
# column at all (this standard IS what defines high/medium/low impact
# tiers, which every other standard's Applicable Systems column then
# references) — applicability is empty throughout, honestly, not a
# missing-data gap.
CIP002_REQUIREMENTS = [
    (
        1,
        "R1 – BES Cyber System Categorization",
        (
            "Each Responsible Entity shall implement a process that considers each of the "
            "following assets for purposes of parts 1.1 through 1.3: Control Centers and backup "
            "Control Centers; Transmission stations and substations; Generation resources; "
            "systems and facilities critical to system restoration, including Blackstart "
            "Resources and Cranking Paths and initial switching requirements; Special Protection "
            "Systems that support the reliable operation of the Bulk Electric System; and, for "
            "Distribution Providers, Protection Systems specified in Applicability section 4.2.1."
        ),
        [
            (
                "1.1",
                "",
                (
                    "Identify each of the high impact BES Cyber Systems according to Attachment "
                    "1, Section 1, if any, at each asset."
                ),
            ),
            (
                "1.2",
                "",
                (
                    "Identify each of the medium impact BES Cyber Systems according to "
                    "Attachment 1, Section 2, if any, at each asset."
                ),
            ),
            (
                "1.3",
                "",
                (
                    "Identify each asset that contains a low impact BES Cyber System according "
                    "to Attachment 1, Section 3, if any (a discrete list of low impact BES Cyber "
                    "Systems is not required)."
                ),
            ),
        ],
    ),
    (
        2,
        "R2 – Review and Approval",
        "The Responsible Entity shall:",
        [
            (
                "2.1",
                "",
                (
                    "Review the identifications in Requirement R1 and its parts (and update "
                    "them if there are changes identified) at least once every 15 calendar "
                    "months, even if it has no identified items in Requirement R1."
                ),
            ),
            (
                "2.2",
                "",
                (
                    "Have its CIP Senior Manager or delegate approve the identifications "
                    "required by Requirement R1 at least once every 15 calendar months, even if "
                    "it has no identified items in Requirement R1."
                ),
            ),
        ],
    ),
]

# CIP-003-9 — policy-based requirements, not per-system-tier tables.
# R1's Parts 1.1/1.2 scope by impact tier (captured as applicability,
# extracted from the Part's own inline text rather than a table
# column); R2-R4 have no sub-parts at all — the Requirement itself is
# the atomic practice, so its ID has no decimal part number.
CIP003_REQUIREMENTS = [
    (
        1,
        "R1 – Cyber Security Policy",
        (
            "Each Responsible Entity shall review and obtain CIP Senior Manager approval at "
            "least once every 15 calendar months for one or more documented cyber security "
            "policies that collectively address the following topics:"
        ),
        [
            (
                "1.1",
                "High impact and medium impact BES Cyber Systems, if any",
                (
                    "Personnel and training (CIP-004); Electronic Security Perimeters (CIP-005) "
                    "including Interactive Remote Access; Physical security of BES Cyber Systems "
                    "(CIP-006); System security management (CIP-007); Incident reporting and "
                    "response planning (CIP-008); Recovery plans for BES Cyber Systems (CIP-009); "
                    "Configuration change management and vulnerability assessments (CIP-010); "
                    "Information protection (CIP-011); and Declaring and responding to CIP "
                    "Exceptional Circumstances."
                ),
            ),
            (
                "1.2",
                "Assets identified in CIP-002 containing low impact BES Cyber Systems, if any",
                (
                    "Cyber security awareness; Physical security controls; Electronic access "
                    "controls; Cyber Security Incident response; Transient Cyber Assets and "
                    "Removable Media malicious code risk mitigation; Vendor electronic remote "
                    "access security controls; and Declaring and responding to CIP Exceptional "
                    "Circumstances."
                ),
            ),
        ],
    ),
    (
        2,
        "R2 – Low Impact BES Cyber Systems Cyber Security Plan(s)",
        "",
        [
            (
                "2",
                "Assets identified in CIP-002 containing low impact BES Cyber Systems",
                (
                    "Each Responsible Entity with at least one asset identified in CIP-002 "
                    "containing low impact BES Cyber Systems shall implement one or more "
                    "documented cyber security plan(s) for its low impact BES Cyber Systems that "
                    "include the sections in Attachment 1."
                ),
            ),
        ],
    ),
    (
        3,
        "R3 – CIP Senior Manager",
        "",
        [
            (
                "3",
                "",
                (
                    "Each Responsible Entity shall identify a CIP Senior Manager by name and "
                    "document any change within 30 calendar days of the change."
                ),
            ),
        ],
    ),
    (
        4,
        "R4 – Delegations",
        "",
        [
            (
                "4",
                "",
                (
                    "The Responsible Entity shall implement a documented process to delegate "
                    "authority, unless no delegations are used. Where allowed by the CIP "
                    "Standards, the CIP Senior Manager may delegate authority for specific "
                    "actions to a delegate or delegates. These delegations shall be documented, "
                    "including the name or title of the delegate, the specific actions "
                    "delegated, and the date of the delegation; approved by the CIP Senior "
                    "Manager; and updated within 30 days of any change to the delegation. "
                    "Delegation changes do not need to be reinstated with a change to the "
                    "delegator."
                ),
            ),
        ],
    ),
]

CIP005_REQUIREMENTS = [
    (
        1,
        "R1 – Electronic Security Perimeter",
        (
            "Each Responsible Entity shall implement one or more documented processes that "
            "collectively include each of the applicable requirement parts in CIP-005-7 Table "
            "R1 – Electronic Security Perimeter."
        ),
        [
            (
                "1.1",
                (
                    "High Impact BES Cyber Systems and their associated: PCA\n"
                    "Medium Impact BES Cyber Systems and their associated: PCA"
                ),
                (
                    "All applicable Cyber Assets connected to a network via a routable protocol "
                    "shall reside within a defined ESP."
                ),
            ),
            (
                "1.2",
                (
                    "High Impact BES Cyber Systems with External Routable Connectivity and their "
                    "associated: PCA\nMedium Impact BES Cyber Systems with External Routable "
                    "Connectivity and their associated: PCA"
                ),
                "All External Routable Connectivity must be through an identified Electronic Access Point (EAP).",
            ),
            (
                "1.3",
                (
                    "Electronic Access Points for High Impact BES Cyber Systems\n"
                    "Electronic Access Points for Medium Impact BES Cyber Systems"
                ),
                (
                    "Require inbound and outbound access permissions, including the reason for "
                    "granting access, and deny all other access by default."
                ),
            ),
            (
                "1.4",
                (
                    "High Impact BES Cyber Systems with Dial-up Connectivity and their "
                    "associated: PCA\nMedium Impact BES Cyber Systems with Dial-up Connectivity "
                    "and their associated: PCA"
                ),
                (
                    "Where technically feasible, perform authentication when establishing "
                    "Dial-up Connectivity with applicable Cyber Assets."
                ),
            ),
            (
                "1.5",
                (
                    "Electronic Access Points for High Impact BES Cyber Systems\n"
                    "Electronic Access Points for Medium Impact BES Cyber Systems at Control "
                    "Centers"
                ),
                (
                    "Have one or more methods for detecting known or suspected malicious "
                    "communications for both inbound and outbound communications."
                ),
            ),
        ],
    ),
    (
        2,
        "R2 – Remote Access Management",
        (
            "Each Responsible Entity shall implement one or more documented processes that "
            "collectively include the applicable requirement parts, where technically "
            "feasible, in CIP-005-7 Table R2 – Remote Access Management."
        ),
        [
            (
                "2.1",
                (
                    "High Impact BES Cyber Systems and their associated: PCA\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: PCA"
                ),
                (
                    "For all Interactive Remote Access, utilize an Intermediate System such "
                    "that the Cyber Asset initiating Interactive Remote Access does not directly "
                    "access an applicable Cyber Asset."
                ),
            ),
            (
                "2.2",
                (
                    "High Impact BES Cyber Systems and their associated: PCA\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: PCA"
                ),
                "For all Interactive Remote Access sessions, utilize encryption that terminates at an Intermediate System.",
            ),
            (
                "2.3",
                (
                    "High Impact BES Cyber Systems and their associated: PCA\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: PCA"
                ),
                "Require multi-factor authentication for all Interactive Remote Access sessions.",
            ),
            (
                "2.4",
                (
                    "High Impact BES Cyber Systems and their associated: PCA\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: PCA"
                ),
                (
                    "Have one or more methods for determining active vendor remote access "
                    "sessions (including Interactive Remote Access and system-to-system remote "
                    "access)."
                ),
            ),
            (
                "2.5",
                (
                    "High Impact BES Cyber Systems and their associated: PCA\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: PCA"
                ),
                (
                    "Have one or more method(s) to disable active vendor remote access "
                    "(including Interactive Remote Access and system-to-system remote access)."
                ),
            ),
        ],
    ),
    (
        3,
        "R3 – Vendor Remote Access Management for EACMS and PACS",
        (
            "Each Responsible Entity shall implement one or more documented processes that "
            "collectively include the applicable requirement parts in CIP-005-7 Table R3 – "
            "Vendor Remote Access Management for EACMS and PACS."
        ),
        [
            (
                "3.1",
                (
                    "EACMS and PACS associated with High Impact BES Cyber Systems\n"
                    "EACMS and PACS associated with Medium Impact BES Cyber Systems with "
                    "External Routable Connectivity"
                ),
                "Have one or more method(s) to determine authenticated vendor-initiated remote connections.",
            ),
            (
                "3.2",
                (
                    "EACMS and PACS associated with High Impact BES Cyber Systems\n"
                    "EACMS and PACS associated with Medium Impact BES Cyber Systems with "
                    "External Routable Connectivity"
                ),
                (
                    "Have one or more method(s) to terminate authenticated vendor-initiated "
                    "remote connections and control the ability to reconnect."
                ),
            ),
        ],
    ),
]

CIP006_REQUIREMENTS = [
    (
        1,
        "R1 – Physical Security Plan",
        (
            "Each Responsible Entity shall implement one or more documented physical security "
            "plan(s) that collectively include all of the applicable requirement parts in "
            "CIP-006-6 Table R1 – Physical Security Plan."
        ),
        [
            (
                "1.1",
                (
                    "Medium Impact BES Cyber Systems without External Routable Connectivity\n"
                    "Physical Access Control Systems (PACS) associated with: High Impact BES "
                    "Cyber Systems, or Medium Impact BES Cyber Systems with External Routable "
                    "Connectivity"
                ),
                "Define operational or procedural controls to restrict physical access.",
            ),
            (
                "1.2",
                (
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: EACMS; PCA"
                ),
                (
                    "Utilize at least one physical access control to allow unescorted physical "
                    "access into each applicable Physical Security Perimeter to only those "
                    "individuals who have authorized unescorted physical access."
                ),
            ),
            (
                "1.3",
                "High Impact BES Cyber Systems and their associated: EACMS; PCA",
                (
                    "Where technically feasible, utilize two or more different physical access "
                    "controls (this does not require two completely independent physical access "
                    "control systems) to collectively allow unescorted physical access into "
                    "Physical Security Perimeters to only those individuals who have authorized "
                    "unescorted physical access."
                ),
            ),
            (
                "1.4",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PCA\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: EACMS; PCA"
                ),
                "Monitor for unauthorized access through a physical access point into a Physical Security Perimeter.",
            ),
            (
                "1.5",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PCA\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: EACMS; PCA"
                ),
                (
                    "Issue an alarm or alert in response to detected unauthorized access through "
                    "a physical access point into a Physical Security Perimeter to the personnel "
                    "identified in the BES Cyber Security Incident response plan within 15 "
                    "minutes of detection."
                ),
            ),
            (
                "1.6",
                (
                    "Physical Access Control Systems (PACS) associated with: High Impact BES "
                    "Cyber Systems, or Medium Impact BES Cyber Systems with External Routable "
                    "Connectivity"
                ),
                "Monitor each Physical Access Control System for unauthorized physical access to a Physical Access Control System.",
            ),
            (
                "1.7",
                (
                    "Physical Access Control Systems (PACS) associated with: High Impact BES "
                    "Cyber Systems, or Medium Impact BES Cyber Systems with External Routable "
                    "Connectivity"
                ),
                (
                    "Issue an alarm or alert in response to detected unauthorized physical "
                    "access to a Physical Access Control System to the personnel identified in "
                    "the BES Cyber Security Incident response plan within 15 minutes of the "
                    "detection."
                ),
            ),
            (
                "1.8",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PCA\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: EACMS; PCA"
                ),
                (
                    "Log (through automated means or by personnel who control entry) entry of "
                    "each individual with authorized unescorted physical access into each "
                    "Physical Security Perimeter, with information to identify the individual "
                    "and date and time of entry."
                ),
            ),
            (
                "1.9",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PCA\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: EACMS; PCA"
                ),
                (
                    "Retain physical access logs of entry of individuals with authorized "
                    "unescorted physical access into each Physical Security Perimeter for at "
                    "least ninety calendar days."
                ),
            ),
            (
                "1.10",
                (
                    "High Impact BES Cyber Systems and their associated: PCA\n"
                    "Medium Impact BES Cyber Systems at Control Centers and their associated: PCA"
                ),
                (
                    "Restrict physical access to cabling and other nonprogrammable "
                    "communication components used for connection between applicable Cyber "
                    "Assets within the same Electronic Security Perimeter in those instances "
                    "when such cabling and components are located outside of a Physical "
                    "Security Perimeter. Where physical access restrictions to such cabling and "
                    "components are not implemented, the Responsible Entity shall document and "
                    "implement one or more of the following: encryption of data that transits "
                    "such cabling and components; or monitoring the status of the communication "
                    "link composed of such cabling and components and issuing an alarm or alert "
                    "in response to detected communication failures to the personnel identified "
                    "in the BES Cyber Security Incident response plan within 15 minutes of "
                    "detection; or an equally effective logical protection."
                ),
            ),
        ],
    ),
    (
        2,
        "R2 – Visitor Control Program",
        (
            "Each Responsible Entity shall implement one or more documented visitor control "
            "program(s) that include each of the applicable requirement parts in CIP-006-6 "
            "Table R2 – Visitor Control Program."
        ),
        [
            (
                "2.1",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PCA\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: EACMS; PCA"
                ),
                (
                    "Require continuous escorted access of visitors (individuals who are "
                    "provided access but are not authorized for unescorted physical access) "
                    "within each Physical Security Perimeter, except during CIP Exceptional "
                    "Circumstances."
                ),
            ),
            (
                "2.2",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PCA\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: EACMS; PCA"
                ),
                (
                    "Require manual or automated logging of visitor entry into and exit from "
                    "the Physical Security Perimeter that includes date and time of the initial "
                    "entry and last exit, the visitor's name, and the name of an individual "
                    "point of contact responsible for the visitor, except during CIP Exceptional "
                    "Circumstances."
                ),
            ),
            (
                "2.3",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PCA\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: EACMS; PCA"
                ),
                "Retain visitor logs for at least ninety calendar days.",
            ),
        ],
    ),
    (
        3,
        "R3 – Physical Access Control System Maintenance and Testing Program",
        (
            "Each Responsible Entity shall implement one or more documented Physical Access "
            "Control System maintenance and testing program(s) that collectively include each "
            "of the applicable requirement parts in CIP-006-6 Table R3 – Maintenance and "
            "Testing Program."
        ),
        [
            (
                "3.1",
                (
                    "Physical Access Control Systems (PACS) associated with: High Impact BES "
                    "Cyber Systems, or Medium Impact BES Cyber Systems with External Routable "
                    "Connectivity\nLocally mounted hardware or devices at the Physical Security "
                    "Perimeter associated with: High Impact BES Cyber Systems, or Medium Impact "
                    "BES Cyber Systems with External Routable Connectivity"
                ),
                (
                    "Maintenance and testing of each Physical Access Control System and locally "
                    "mounted hardware or devices at the Physical Security Perimeter at least "
                    "once every 24 calendar months to ensure they function properly."
                ),
            ),
        ],
    ),
]

CIP007_REQUIREMENTS = [
    (
        1,
        "R1 – Ports and Services",
        (
            "Each Responsible Entity shall implement one or more documented process(es) that "
            "collectively include each of the applicable requirement parts in CIP-007-6 Table "
            "R1 – Ports and Services."
        ),
        [
            (
                "1.1",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: EACMS; PACS; and PCA"
                ),
                (
                    "Where technically feasible, enable only logical network accessible ports "
                    "that have been determined to be needed by the Responsible Entity, "
                    "including port ranges or services where needed to handle dynamic ports. If "
                    "a device has no provision for disabling or restricting logical ports on the "
                    "device then those ports that are open are deemed needed."
                ),
            ),
            (
                "1.2",
                (
                    "High Impact BES Cyber Systems and their associated: PCA; and "
                    "Nonprogrammable communication components located inside both a PSP and an "
                    "ESP.\nMedium Impact BES Cyber Systems at Control Centers and their "
                    "associated: PCA; and Nonprogrammable communication components located "
                    "inside both a PSP and an ESP."
                ),
                (
                    "Protect against the use of unnecessary physical input/output ports used "
                    "for network connectivity, console commands, or Removable Media."
                ),
            ),
        ],
    ),
    (
        2,
        "R2 – Security Patch Management",
        (
            "Each Responsible Entity shall implement one or more documented process(es) that "
            "collectively include each of the applicable requirement parts in CIP-007-6 Table "
            "R2 – Security Patch Management."
        ),
        [
            (
                "2.1",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA"
                ),
                (
                    "A patch management process for tracking, evaluating, and installing cyber "
                    "security patches for applicable Cyber Assets. The tracking portion shall "
                    "include the identification of a source or sources that the Responsible "
                    "Entity tracks for the release of cyber security patches for applicable "
                    "Cyber Assets that are updateable and for which a patching source exists."
                ),
            ),
            (
                "2.2",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA"
                ),
                (
                    "At least once every 35 calendar days, evaluate security patches for "
                    "applicability that have been released since the last evaluation from the "
                    "source or sources identified in Part 2.1."
                ),
            ),
            (
                "2.3",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA"
                ),
                (
                    "For applicable patches identified in Part 2.2, within 35 calendar days of "
                    "the evaluation completion, take one of the following actions: apply the "
                    "applicable patches; or create a dated mitigation plan; or revise an "
                    "existing mitigation plan. Mitigation plans shall include the Responsible "
                    "Entity's planned actions to mitigate the vulnerabilities addressed by each "
                    "security patch and a timeframe to complete these mitigations."
                ),
            ),
            (
                "2.4",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA"
                ),
                (
                    "For each mitigation plan created or revised in Part 2.3, implement the "
                    "plan within the timeframe specified in the plan, unless a revision to the "
                    "plan or an extension to the timeframe specified in Part 2.3 is approved by "
                    "the CIP Senior Manager or delegate."
                ),
            ),
        ],
    ),
    (
        3,
        "R3 – Malicious Code Prevention",
        (
            "Each Responsible Entity shall implement one or more documented process(es) that "
            "collectively include each of the applicable requirement parts in CIP-007-6 Table "
            "R3 – Malicious Code Prevention."
        ),
        [
            (
                "3.1",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA"
                ),
                "Deploy method(s) to deter, detect, or prevent malicious code.",
            ),
            (
                "3.2",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA"
                ),
                "Mitigate the threat of detected malicious code.",
            ),
            (
                "3.3",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA"
                ),
                (
                    "For those methods identified in Part 3.1 that use signatures or patterns, "
                    "have a process for the update of the signatures or patterns. The process "
                    "must address testing and installing the signatures or patterns."
                ),
            ),
        ],
    ),
    (
        4,
        "R4 – Security Event Monitoring",
        (
            "Each Responsible Entity shall implement one or more documented process(es) that "
            "collectively include each of the applicable requirement parts in CIP-007-6 Table "
            "R4 – Security Event Monitoring."
        ),
        [
            (
                "4.1",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA"
                ),
                (
                    "Log events at the BES Cyber System level (per BES Cyber System capability) "
                    "or at the Cyber Asset level (per Cyber Asset capability) for identification "
                    "of, and after-the-fact investigations of, Cyber Security Incidents that "
                    "includes, as a minimum, each of the following types of events: detected "
                    "successful login attempts; detected failed access attempts and failed "
                    "login attempts; detected malicious code."
                ),
            ),
            (
                "4.2",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: EACMS; PACS; and PCA"
                ),
                (
                    "Generate alerts for security events that the Responsible Entity determines "
                    "necessitates an alert, that includes, as a minimum, each of the following "
                    "types of events (per Cyber Asset or BES Cyber System capability): detected "
                    "malicious code from Part 4.1; and detected failure of Part 4.1 event "
                    "logging."
                ),
            ),
            (
                "4.3",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems at Control Centers and their associated: "
                    "EACMS; PACS; and PCA"
                ),
                (
                    "Where technically feasible, retain applicable event logs identified in "
                    "Part 4.1 for at least the last 90 consecutive calendar days except under "
                    "CIP Exceptional Circumstances."
                ),
            ),
            (
                "4.4",
                "High Impact BES Cyber Systems and their associated: EACMS; and PCA",
                (
                    "Review a summarization or sampling of logged events as determined by the "
                    "Responsible Entity at intervals no greater than 15 calendar days to "
                    "identify undetected Cyber Security Incidents."
                ),
            ),
        ],
    ),
    (
        5,
        "R5 – System Access Control",
        (
            "Each Responsible Entity shall implement one or more documented process(es) that "
            "collectively include each of the applicable requirement parts in CIP-007-6 Table "
            "R5 – System Access Controls."
        ),
        [
            (
                "5.1",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems at Control Centers and their associated: "
                    "EACMS; PACS; and PCA\nMedium Impact BES Cyber Systems with External "
                    "Routable Connectivity and their associated: EACMS; PACS; and PCA"
                ),
                "Have a method(s) to enforce authentication of interactive user access, where technically feasible.",
            ),
            (
                "5.2",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA"
                ),
                (
                    "Identify and inventory all known enabled default or other generic account "
                    "types, either by system, by groups of systems, by location, or by system "
                    "type(s)."
                ),
            ),
            (
                "5.3",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: EACMS; PACS; and PCA"
                ),
                "Identify individuals who have authorized access to shared accounts.",
            ),
            (
                "5.4",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA"
                ),
                "Change known default passwords, per Cyber Asset capability.",
            ),
            (
                "5.5",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA"
                ),
                (
                    "For password-only authentication for interactive user access, either "
                    "technically or procedurally enforce the following password parameters: "
                    "password length that is, at least, the lesser of eight characters or the "
                    "maximum length supported by the Cyber Asset; and minimum password "
                    "complexity that is the lesser of three or more different types of "
                    "characters (e.g., uppercase alphabetic, lowercase alphabetic, numeric, "
                    "non-alphanumeric) or the maximum complexity supported by the Cyber Asset."
                ),
            ),
            (
                "5.6",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems with External Routable Connectivity and "
                    "their associated: EACMS; PACS; and PCA"
                ),
                (
                    "Where technically feasible, for password-only authentication for "
                    "interactive user access, either technically or procedurally enforce "
                    "password changes or an obligation to change the password at least once "
                    "every 15 calendar months."
                ),
            ),
            (
                "5.7",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems at Control Centers and their associated: "
                    "EACMS; PACS; and PCA"
                ),
                (
                    "Where technically feasible, either: limit the number of unsuccessful "
                    "authentication attempts; or generate alerts after a threshold of "
                    "unsuccessful authentication attempts."
                ),
            ),
        ],
    ),
]

CIP008_REQUIREMENTS = [
    (
        1,
        "R1 – Cyber Security Incident Response Plan Specifications",
        (
            "Each Responsible Entity shall document one or more Cyber Security Incident "
            "response plan(s) that collectively include each of the applicable requirement "
            "parts in CIP-008-6 Table R1 – Cyber Security Incident Response Plan "
            "Specifications."
        ),
        [
            (
                "1.1",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS"
                ),
                "One or more processes to identify, classify, and respond to Cyber Security Incidents.",
            ),
            (
                "1.2",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS"
                ),
                (
                    "One or more processes: that include criteria to evaluate and define "
                    "attempts to compromise; to determine if an identified Cyber Security "
                    "Incident is a Reportable Cyber Security Incident or an attempt to "
                    "compromise, as determined by applying the criteria from Part 1.2.1, one or "
                    "more systems identified in the \"Applicable Systems\" column for this Part; "
                    "and to provide notification per Requirement R4."
                ),
            ),
            (
                "1.3",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS"
                ),
                "The roles and responsibilities of Cyber Security Incident response groups or individuals.",
            ),
            (
                "1.4",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS"
                ),
                "Incident handling procedures for Cyber Security Incidents.",
            ),
        ],
    ),
    (
        2,
        "R2 – Cyber Security Incident Response Plan Implementation and Testing",
        (
            "Each Responsible Entity shall implement each of its documented Cyber Security "
            "Incident response plans to collectively include each of the applicable "
            "requirement parts in CIP-008-6 Table R2 – Cyber Security Incident Response Plan "
            "Implementation and Testing."
        ),
        [
            (
                "2.1",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS"
                ),
                (
                    "Test each Cyber Security Incident response plan(s) at least once every 15 "
                    "calendar months: by responding to an actual Reportable Cyber Security "
                    "Incident; with a paper drill or tabletop exercise of a Reportable Cyber "
                    "Security Incident; or with an operational exercise of a Reportable Cyber "
                    "Security Incident."
                ),
            ),
            (
                "2.2",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS"
                ),
                (
                    "Use the Cyber Security Incident response plan(s) under Requirement R1 when "
                    "responding to a Reportable Cyber Security Incident, responding to a Cyber "
                    "Security Incident that attempted to compromise a system identified in the "
                    "\"Applicable Systems\" column for this Part, or performing an exercise of a "
                    "Reportable Cyber Security Incident. Document deviations from the plan(s) "
                    "taken during the response to the incident or exercise."
                ),
            ),
            (
                "2.3",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS"
                ),
                (
                    "Retain records related to Reportable Cyber Security Incidents and Cyber "
                    "Security Incidents that attempted to compromise a system identified in the "
                    "\"Applicable Systems\" column for this Part as per the Cyber Security "
                    "Incident response plan(s) under Requirement R1."
                ),
            ),
        ],
    ),
    (
        3,
        "R3 – Cyber Security Incident Response Plan Review, Update, and Communication",
        (
            "Each Responsible Entity shall maintain each of its Cyber Security Incident "
            "response plans according to each of the applicable requirement parts in CIP-008-6 "
            "Table R3 – Cyber Security Incident Response Plan Review, Update, and "
            "Communication."
        ),
        [
            (
                "3.1",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS"
                ),
                (
                    "No later than 90 calendar days after completion of a Cyber Security "
                    "Incident response plan(s) test or actual Reportable Cyber Security "
                    "Incident response: document any lessons learned or document the absence of "
                    "any lessons learned; update the Cyber Security Incident response plan based "
                    "on any documented lessons learned associated with the plan; and notify each "
                    "person or group with a defined role in the Cyber Security Incident response "
                    "plan of the updates based on any documented lessons learned."
                ),
            ),
            (
                "3.2",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS"
                ),
                (
                    "No later than 60 calendar days after a change to the roles or "
                    "responsibilities, Cyber Security Incident response groups or individuals, "
                    "or technology that the Responsible Entity determines would impact the "
                    "ability to execute the plan: update the Cyber Security Incident response "
                    "plan(s); and notify each person or group with a defined role in the Cyber "
                    "Security Incident response plan of the updates."
                ),
            ),
        ],
    ),
    (
        4,
        "R4 – Notifications and Reporting for Cyber Security Incidents",
        (
            "Each Responsible Entity shall notify the Electricity Information Sharing and "
            "Analysis Center (E-ISAC) and, if subject to the jurisdiction of the United "
            "States, the United States National Cybersecurity and Communications Integration "
            "Center (NCCIC), or their successors, of a Reportable Cyber Security Incident and "
            "a Cyber Security Incident that was an attempt to compromise, as determined by "
            "applying the criteria from Requirement R1, Part 1.2.1, a system identified in the "
            "\"Applicable Systems\" column, unless prohibited by law, in accordance with each "
            "of the applicable requirement parts in CIP-008-6 Table R4 – Notifications and "
            "Reporting for Cyber Security Incidents."
        ),
        [
            (
                "4.1",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS"
                ),
                (
                    "Initial notifications and updates shall include the following attributes, "
                    "at a minimum, to the extent known: the functional impact; the attack vector "
                    "used; and the level of intrusion that was achieved or attempted."
                ),
            ),
            (
                "4.2",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS"
                ),
                (
                    "After the Responsible Entity's determination made pursuant to documented "
                    "process(es) in Requirement R1, Part 1.2, provide initial notification "
                    "within the following timelines: one hour after the determination of a "
                    "Reportable Cyber Security Incident; by the end of the next calendar day "
                    "after determination that a Cyber Security Incident was an attempt to "
                    "compromise a system identified in the \"Applicable Systems\" column for "
                    "this Part."
                ),
            ),
            (
                "4.3",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS"
                ),
                "Provide updates, if any, within 7 calendar days of determination of new or changed attribute information required in Part 4.1.",
            ),
        ],
    ),
]

CIP009_REQUIREMENTS = [
    (
        1,
        "R1 – Recovery Plan Specifications",
        (
            "Each Responsible Entity shall have one or more documented recovery plan(s) that "
            "collectively include each of the applicable requirement parts in CIP-009-6 Table "
            "R1 – Recovery Plan Specifications."
        ),
        [
            (
                "1.1",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; and PACS\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; and PACS"
                ),
                "Conditions for activation of the recovery plan(s).",
            ),
            (
                "1.2",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; and PACS\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; and PACS"
                ),
                "Roles and responsibilities of responders.",
            ),
            (
                "1.3",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; and PACS\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; and PACS"
                ),
                "One or more processes for the backup and storage of information required to recover BES Cyber System functionality.",
            ),
            (
                "1.4",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; and PACS\n"
                    "Medium Impact BES Cyber Systems at Control Centers and their associated: "
                    "EACMS; and PACS"
                ),
                "One or more processes to verify the successful completion of the backup processes in Part 1.3 and to address any backup failures.",
            ),
            (
                "1.5",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; and PACS\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; and PACS"
                ),
                (
                    "One or more processes to preserve data, per Cyber Asset capability, for "
                    "determining the cause of a Cyber Security Incident that triggers "
                    "activation of the recovery plan(s). Data preservation should not impede or "
                    "restrict recovery."
                ),
            ),
        ],
    ),
    (
        2,
        "R2 – Recovery Plan Implementation and Testing",
        (
            "Each Responsible Entity shall implement its documented recovery plan(s) to "
            "collectively include each of the applicable requirement parts in CIP-009-6 Table "
            "R2 – Recovery Plan Implementation and Testing."
        ),
        [
            (
                "2.1",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; and PACS\n"
                    "Medium Impact BES Cyber Systems at Control Centers and their associated: "
                    "EACMS; and PACS"
                ),
                (
                    "Test each of the recovery plans referenced in Requirement R1 at least once "
                    "every 15 calendar months: by recovering from an actual incident; with a "
                    "paper drill or tabletop exercise; or with an operational exercise."
                ),
            ),
            (
                "2.2",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; and PACS\n"
                    "Medium Impact BES Cyber Systems at Control Centers and their associated: "
                    "EACMS; and PACS"
                ),
                (
                    "Test a representative sample of information used to recover BES Cyber "
                    "System functionality at least once every 15 calendar months to ensure that "
                    "the information is useable and is compatible with current configurations. "
                    "An actual recovery that incorporates the information used to recover BES "
                    "Cyber System functionality substitutes for this test."
                ),
            ),
            (
                "2.3",
                "High Impact BES Cyber Systems",
                (
                    "Test each of the recovery plans referenced in Requirement R1 at least once "
                    "every 36 calendar months through an operational exercise of the recovery "
                    "plans in an environment representative of the production environment. An "
                    "actual recovery response may substitute for an operational exercise."
                ),
            ),
        ],
    ),
    (
        3,
        "R3 – Recovery Plan Review, Update and Communication",
        (
            "Each Responsible Entity shall maintain each of its recovery plan(s) in accordance "
            "with each of the applicable requirement parts in CIP-009-6 Table R3 – Recovery "
            "Plan Review, Update and Communication."
        ),
        [
            (
                "3.1",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; and PACS\n"
                    "Medium Impact BES Cyber Systems at Control Centers and their associated: "
                    "EACMS; and PACS"
                ),
                (
                    "No later than 90 calendar days after completion of a recovery plan test or "
                    "actual recovery: document any lessons learned associated with a recovery "
                    "plan test or actual recovery or document the absence of any lessons "
                    "learned; update the recovery plan based on any documented lessons learned "
                    "associated with the plan; and notify each person or group with a defined "
                    "role in the recovery plan of the updates based on any documented lessons "
                    "learned."
                ),
            ),
            (
                "3.2",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; and PACS\n"
                    "Medium Impact BES Cyber Systems at Control Centers and their associated: "
                    "EACMS; and PACS"
                ),
                (
                    "No later than 60 calendar days after a change to the roles or "
                    "responsibilities, responders, or technology that the Responsible Entity "
                    "determines would impact the ability to execute the recovery plan: update "
                    "the recovery plan; and notify each person or group with a defined role in "
                    "the recovery plan of the updates."
                ),
            ),
        ],
    ),
]

CIP010_REQUIREMENTS = [
    (
        1,
        "R1 – Configuration Change Management",
        (
            "Each Responsible Entity shall implement one or more documented process(es) that "
            "collectively include each of the applicable requirement parts in CIP-010-4 Table "
            "R1 – Configuration Change Management."
        ),
        [
            (
                "1.1",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA"
                ),
                (
                    "Develop a baseline configuration, individually or by group, which shall "
                    "include the following items: operating system(s) (including version) or "
                    "firmware where no independent operating system exists; any commercially "
                    "available or open-source application software (including version) "
                    "intentionally installed; any custom software installed; any logical "
                    "network accessible ports; and any security patches applied."
                ),
            ),
            (
                "1.2",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA"
                ),
                "Authorize and document changes that deviate from the existing baseline configuration.",
            ),
            (
                "1.3",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA"
                ),
                "For a change that deviates from the existing baseline configuration, update the baseline configuration as necessary within 30 calendar days of completing the change.",
            ),
            (
                "1.4",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA"
                ),
                (
                    "For a change that deviates from the existing baseline configuration: prior "
                    "to the change, determine required cyber security controls in CIP-005 and "
                    "CIP-007 that could be impacted by the change; following the change, verify "
                    "that required cyber security controls determined are not adversely "
                    "affected; and document the results of the verification."
                ),
            ),
            (
                "1.5",
                "High Impact BES Cyber Systems",
                (
                    "Where technically feasible, for each change that deviates from the "
                    "existing baseline configuration: prior to implementing any change in the "
                    "production environment, test the changes in a test environment or test the "
                    "changes in a production environment where the test is performed in a "
                    "manner that minimizes adverse effects, that models the baseline "
                    "configuration to ensure that required cyber security controls in CIP-005 "
                    "and CIP-007 are not adversely affected; and document the results of the "
                    "testing and, if a test environment was used, the differences between the "
                    "test environment and the production environment, including a description "
                    "of the measures used to account for any differences in operation between "
                    "the test and production environments."
                ),
            ),
            (
                "1.6",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; and PACS\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; and PACS"
                ),
                (
                    "Prior to a change that deviates from the existing baseline configuration "
                    "associated with baseline items in Parts 1.1.1, 1.1.2, and 1.1.5, and when "
                    "the method to do so is available to the Responsible Entity from the "
                    "software source: verify the identity of the software source; and verify "
                    "the integrity of the software obtained from the software source."
                ),
            ),
        ],
    ),
    (
        2,
        "R2 – Configuration Monitoring",
        (
            "Each Responsible Entity shall implement one or more documented process(es) that "
            "collectively include each of the applicable requirement parts in CIP-010-4 Table "
            "R2 – Configuration Monitoring."
        ),
        [
            (
                "2.1",
                "High Impact BES Cyber Systems and their associated: EACMS; and PCA",
                (
                    "Monitor at least once every 35 calendar days for changes to the baseline "
                    "configuration (as described in Requirement R1, Part 1.1). Document and "
                    "investigate detected unauthorized changes."
                ),
            ),
        ],
    ),
    (
        3,
        "R3 – Vulnerability Assessments",
        (
            "Each Responsible Entity shall implement one or more documented process(es) that "
            "collectively include each of the applicable requirement parts in CIP-010-4 Table "
            "R3 – Vulnerability Assessments."
        ),
        [
            (
                "3.1",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA"
                ),
                "At least once every 15 calendar months, conduct a paper or active vulnerability assessment.",
            ),
            (
                "3.2",
                "High Impact BES Cyber Systems",
                (
                    "Where technically feasible, at least once every 36 calendar months: "
                    "perform an active vulnerability assessment in a test environment, or "
                    "perform an active vulnerability assessment in a production environment "
                    "where the test is performed in a manner that minimizes adverse effects, "
                    "that models the baseline configuration of the BES Cyber System in a "
                    "production environment; and document the results of the testing and, if a "
                    "test environment was used, the differences between the test environment "
                    "and the production environment, including a description of the measures "
                    "used to account for any differences in operation between the test and "
                    "production environments."
                ),
            ),
            (
                "3.3",
                "High Impact BES Cyber Systems and their associated: EACMS; and PCA",
                (
                    "Prior to adding a new applicable Cyber Asset to a production environment, "
                    "perform an active vulnerability assessment of the new Cyber Asset, except "
                    "for CIP Exceptional Circumstances and like replacements of the same type of "
                    "Cyber Asset with a baseline configuration that models an existing baseline "
                    "configuration of the previous or other existing Cyber Asset."
                ),
            ),
            (
                "3.4",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA"
                ),
                (
                    "Document the results of the assessments conducted according to Parts 3.1, "
                    "3.2, and 3.3 and the action plan to remediate or mitigate vulnerabilities "
                    "identified in the assessments including the planned date of completing the "
                    "action plan and the execution status of any remediation or mitigation "
                    "action items."
                ),
            ),
        ],
    ),
    (
        4,
        "R4 – Transient Cyber Assets and Removable Media",
        "",
        [
            (
                "4",
                "High impact and medium impact BES Cyber Systems and associated Protected Cyber Assets",
                (
                    "Each Responsible Entity, for its high impact and medium impact BES Cyber "
                    "Systems and associated Protected Cyber Assets, shall implement, except "
                    "under CIP Exceptional Circumstances, one or more documented plan(s) for "
                    "Transient Cyber Assets and Removable Media that include the sections in "
                    "Attachment 1."
                ),
            ),
        ],
    ),
]

CIP011_REQUIREMENTS = [
    (
        1,
        "R1 – Information Protection Program",
        (
            "Each Responsible Entity shall implement one or more documented information "
            "protection program(s) for BES Cyber System Information (BCSI) pertaining to "
            "\"Applicable Systems\" identified in CIP-011-3 Table R1 – Information Protection "
            "Program that collectively includes each of the applicable requirement parts in "
            "CIP-011-3 Table R1 – Information Protection Program."
        ),
        [
            (
                "1.1",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; and PACS\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; and PACS"
                ),
                "Method(s) to identify BCSI.",
            ),
            (
                "1.2",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; and PACS\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; and PACS"
                ),
                "Method(s) to protect and securely handle BCSI to mitigate risks of compromising confidentiality.",
            ),
        ],
    ),
    (
        2,
        "R2 – BES Cyber Asset Reuse and Disposal",
        (
            "Each Responsible Entity shall implement one or more documented process(es) that "
            "collectively include the applicable requirement parts in CIP-011-3 Table R2 – BES "
            "Cyber Asset Reuse and Disposal."
        ),
        [
            (
                "2.1",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA"
                ),
                (
                    "Prior to the release for reuse of applicable Cyber Assets that contain "
                    "BCSI (except for reuse within other systems identified in the \"Applicable "
                    "Systems\" column), the Responsible Entity shall take action to prevent the "
                    "unauthorized retrieval of BCSI from the Cyber Asset data storage media."
                ),
            ),
            (
                "2.2",
                (
                    "High Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA\n"
                    "Medium Impact BES Cyber Systems and their associated: EACMS; PACS; and PCA"
                ),
                (
                    "Prior to the disposal of applicable Cyber Assets that contain BCSI, the "
                    "Responsible Entity shall take action to prevent the unauthorized retrieval "
                    "of BCSI from the Cyber Asset or destroy the data storage media."
                ),
            ),
        ],
    ),
]

# CIP-012-2 — no Applicable Systems table; applies uniformly to
# Control Centers per the Applicability section, not scoped per-Part
# by impact tier, so applicability is empty throughout.
CIP012_REQUIREMENTS = [
    (
        1,
        "R1 – Communications between Control Centers",
        (
            "The Responsible Entity shall implement, except under CIP Exceptional "
            "Circumstances, one or more documented plan(s) to mitigate the risks posed by "
            "unauthorized disclosure, unauthorized modification, and loss of availability, of "
            "data used in Real-time Assessment and Real-time monitoring while such data is "
            "being transmitted between any applicable Control Centers. The Responsible Entity "
            "is not required to include oral communications in its plan."
        ),
        [
            (
                "1.1",
                "",
                (
                    "Identification of method(s) used to mitigate the risk(s) posed by "
                    "unauthorized disclosure and unauthorized modification of data used in "
                    "Real-time Assessment and Real-time monitoring while such data is being "
                    "transmitted between Control Centers."
                ),
            ),
            (
                "1.2",
                "",
                (
                    "Identification of method(s) used to mitigate the risk(s) posed by the loss "
                    "of the ability to communicate Real-time Assessment and Real-time "
                    "monitoring data between Control Centers."
                ),
            ),
            (
                "1.3",
                "",
                (
                    "Identification of method(s) used to initiate the recovery of communication "
                    "links used to transmit Real-time Assessment and Real-time monitoring data "
                    "between Control Centers."
                ),
            ),
            (
                "1.4",
                "",
                "Identification of where the Responsible Entity implemented method(s) as required in Parts 1.1 and 1.2.",
            ),
            (
                "1.5",
                "",
                (
                    "If the Control Centers are owned or operated by different Responsible "
                    "Entities, identification of the responsibilities of each Responsible "
                    "Entity for implementing method(s) as required in Parts 1.1, 1.2, and 1.3."
                ),
            ),
        ],
    ),
]

CIP013_REQUIREMENTS = [
    (
        1,
        "R1 – Supply Chain Cyber Security Risk Management Plan(s)",
        (
            "Each Responsible Entity shall develop one or more documented supply chain cyber "
            "security risk management plan(s) for high and medium impact BES Cyber Systems "
            "and their associated Electronic Access Control or Monitoring Systems (EACMS) and "
            "Physical Access Control Systems (PACS)."
        ),
        [
            (
                "1.1",
                "High and medium impact BES Cyber Systems and their associated EACMS and PACS",
                (
                    "One or more process(es) used in planning for the procurement of BES Cyber "
                    "Systems and their associated EACMS and PACS to identify and assess cyber "
                    "security risk(s) to the Bulk Electric System from vendor products or "
                    "services resulting from: procuring and installing vendor equipment and "
                    "software; and transitions from one vendor(s) to another vendor(s)."
                ),
            ),
            (
                "1.2",
                "High and medium impact BES Cyber Systems and their associated EACMS and PACS",
                (
                    "One or more process(es) used in procuring BES Cyber Systems, and their "
                    "associated EACMS and PACS, that address the following, as applicable: "
                    "notification by the vendor of vendor-identified incidents related to the "
                    "products or services provided that pose cyber security risk; coordination "
                    "of responses to vendor-identified incidents; notification by vendors when "
                    "remote or onsite access should no longer be granted to vendor "
                    "representatives; disclosure by vendors of known vulnerabilities related to "
                    "the products or services provided; verification of software integrity and "
                    "authenticity of all software and patches provided by the vendor; and "
                    "coordination of controls for vendor-initiated remote access."
                ),
            ),
        ],
    ),
    (
        2,
        "R2 – Implementation",
        "",
        [
            (
                "2",
                "High and medium impact BES Cyber Systems and their associated EACMS and PACS",
                "Each Responsible Entity shall implement its supply chain cyber security risk management plan(s) specified in Requirement R1.",
            ),
        ],
    ),
    (
        3,
        "R3 – Plan Review and Approval",
        "",
        [
            (
                "3",
                "",
                (
                    "Each Responsible Entity shall review and obtain CIP Senior Manager or "
                    "delegate approval of its supply chain cyber security risk management "
                    "plan(s) specified in Requirement R1 at least once every 15 calendar months."
                ),
            ),
        ],
    ),
]

# CIP-014-3 — Physical Security, structurally the most different
# standard in the suite: scoped to Transmission Owner/Operator
# Transmission stations/substations meeting a risk-assessment
# criterion, not BES Cyber Systems by impact tier — no Applicable
# Systems table, applicability empty throughout.
CIP014_REQUIREMENTS = [
    (
        1,
        "R1 – Risk Assessment",
        (
            "Each Transmission Owner shall perform an initial risk assessment and subsequent "
            "risk assessments of its Transmission stations and Transmission substations "
            "(existing and planned to be in service within 24 months) that meet the criteria "
            "specified in Applicability Section 4.1.1. The initial and subsequent risk "
            "assessments shall consist of a transmission analysis or transmission analyses "
            "designed to identify the Transmission station(s) and Transmission substation(s) "
            "that if rendered inoperable or damaged could result in instability, uncontrolled "
            "separation, or Cascading within an Interconnection."
        ),
        [
            (
                "1.1",
                "",
                (
                    "Subsequent risk assessments shall be performed: at least once every 30 "
                    "calendar months for a Transmission Owner that has identified in its "
                    "previous risk assessment (as verified according to Requirement R2) one or "
                    "more Transmission stations or Transmission substations that if rendered "
                    "inoperable or damaged could result in instability, uncontrolled "
                    "separation, or Cascading within an Interconnection; or at least once every "
                    "60 calendar months for a Transmission Owner that has not identified any "
                    "such stations or substations in its previous risk assessment."
                ),
            ),
            (
                "1.2",
                "",
                (
                    "The Transmission Owner shall identify the primary control center that "
                    "operationally controls each Transmission station or Transmission "
                    "substation identified in the Requirement R1 risk assessment."
                ),
            ),
        ],
    ),
    (
        2,
        "R2 – Verification",
        (
            "Each Transmission Owner shall have an unaffiliated third party verify the risk "
            "assessment performed under Requirement R1. The verification may occur concurrent "
            "with or after the risk assessment performed under Requirement R1."
        ),
        [
            (
                "2.1",
                "",
                (
                    "Each Transmission Owner shall select an unaffiliated verifying entity that "
                    "is either: a registered Planning Coordinator, Transmission Planner, or "
                    "Reliability Coordinator; or an entity that has transmission planning or "
                    "analysis experience."
                ),
            ),
            (
                "2.2",
                "",
                (
                    "The unaffiliated third party verification shall verify the Transmission "
                    "Owner's risk assessment performed under Requirement R1, which may include "
                    "recommendations for the addition or deletion of a Transmission station(s) "
                    "or Transmission substation(s). The Transmission Owner shall ensure the "
                    "verification is completed within 90 calendar days following the completion "
                    "of the Requirement R1 risk assessment."
                ),
            ),
            (
                "2.3",
                "",
                (
                    "If the unaffiliated verifying entity recommends that the Transmission "
                    "Owner add a Transmission station(s) or Transmission substation(s) to, or "
                    "remove a Transmission station(s) or Transmission substation(s) from, its "
                    "identification under Requirement R1, the Transmission Owner shall either, "
                    "within 60 calendar days of completion of the verification, for each "
                    "recommended addition or removal: modify its identification under "
                    "Requirement R1 consistent with the recommendation; or document the "
                    "technical basis for not modifying the identification in accordance with "
                    "the recommendation."
                ),
            ),
            (
                "2.4",
                "",
                (
                    "Each Transmission Owner shall implement procedures, such as the use of "
                    "non-disclosure agreements, for protecting sensitive or confidential "
                    "information made available to the unaffiliated third party verifier and to "
                    "protect or exempt sensitive or confidential information developed pursuant "
                    "to this Reliability Standard from public disclosure."
                ),
            ),
        ],
    ),
    (
        3,
        "R3 – Notification of Primary Control Center",
        "",
        [
            (
                "3",
                "",
                (
                    "For a primary control center(s) identified by the Transmission Owner "
                    "according to Requirement R1, Part 1.2 that (a) operationally controls an "
                    "identified Transmission station or Transmission substation verified "
                    "according to Requirement R2, and (b) is not under the operational control "
                    "of the Transmission Owner: the Transmission Owner shall, within seven "
                    "calendar days following completion of Requirement R2, notify the "
                    "Transmission Operator that has operational control of the primary control "
                    "center of such identification and the date of completion of Requirement R2."
                ),
            ),
            (
                "3.1",
                "",
                (
                    "If a Transmission station or Transmission substation previously identified "
                    "under Requirement R1 and verified according to Requirement R2 is removed "
                    "from the identification during a subsequent risk assessment performed "
                    "according to Requirement R1 or a verification according to Requirement R2, "
                    "then the Transmission Owner shall, within seven calendar days following the "
                    "verification or the subsequent risk assessment, notify the Transmission "
                    "Operator that has operational control of the primary control center of the "
                    "removal."
                ),
            ),
        ],
    ),
    (
        4,
        "R4 – Threat and Vulnerability Evaluation",
        (
            "Each Transmission Owner that identified a Transmission station, Transmission "
            "substation, or a primary control center in Requirement R1 and verified according "
            "to Requirement R2, and each Transmission Operator notified by a Transmission "
            "Owner according to Requirement R3, shall conduct an evaluation of the potential "
            "threats and vulnerabilities of a physical attack to each of their respective "
            "Transmission station(s), Transmission substation(s), and primary control "
            "center(s) identified in Requirement R1 and verified according to Requirement R2. "
            "The evaluation shall consider the following:"
        ),
        [
            (
                "4.1",
                "",
                "Unique characteristics of the identified and verified Transmission station(s), Transmission substation(s), and primary control center(s).",
            ),
            (
                "4.2",
                "",
                (
                    "Prior history of attack on similar facilities taking into account the "
                    "frequency, geographic proximity, and severity of past physical security "
                    "related events."
                ),
            ),
            (
                "4.3",
                "",
                (
                    "Intelligence or threat warnings received from sources such as law "
                    "enforcement, the Electric Reliability Organization (ERO), the Electricity "
                    "Sector Information Sharing and Analysis Center (ES-ISAC), U.S. federal "
                    "and/or Canadian governmental agencies, or their successors."
                ),
            ),
        ],
    ),
    (
        5,
        "R5 – Physical Security Plan",
        (
            "Each Transmission Owner that identified a Transmission station, Transmission "
            "substation, or primary control center in Requirement R1 and verified according "
            "to Requirement R2, and each Transmission Operator notified by a Transmission "
            "Owner according to Requirement R3, shall develop and implement a documented "
            "physical security plan(s) that covers their respective Transmission station(s), "
            "Transmission substation(s), and primary control center(s). The physical security "
            "plan(s) shall be developed within 120 calendar days following the completion of "
            "Requirement R2 and executed according to the timeline specified in the physical "
            "security plan(s). The physical security plan(s) shall include the following "
            "attributes:"
        ),
        [
            (
                "5.1",
                "",
                (
                    "Resiliency or security measures designed collectively to deter, detect, "
                    "delay, assess, communicate, and respond to potential physical threats and "
                    "vulnerabilities identified during the evaluation conducted in Requirement "
                    "R4."
                ),
            ),
            ("5.2", "", "Law enforcement contact and coordination information."),
            (
                "5.3",
                "",
                "A timeline for executing the physical security enhancements and modifications specified in the physical security plan.",
            ),
            (
                "5.4",
                "",
                (
                    "Provisions to evaluate evolving physical threats, and their corresponding "
                    "security measures, to the Transmission station(s), Transmission "
                    "substation(s), or primary control center(s)."
                ),
            ),
        ],
    ),
    (
        6,
        "R6 – Third-Party Review",
        (
            "Each Transmission Owner that identified a Transmission station, Transmission "
            "substation, or primary control center in Requirement R1 and verified according "
            "to Requirement R2, and each Transmission Operator notified by a Transmission "
            "Owner according to Requirement R3, shall have an unaffiliated third party review "
            "the evaluation performed under Requirement R4 and the security plan(s) developed "
            "under Requirement R5. The review may occur concurrently with or after completion "
            "of the evaluation performed under Requirement R4 and the security plan "
            "development under Requirement R5."
        ),
        [
            (
                "6.1",
                "",
                (
                    "Each Transmission Owner and Transmission Operator shall select an "
                    "unaffiliated third party reviewer from the following: an entity or "
                    "organization with electric industry physical security experience and whose "
                    "review staff has at least one member who holds either a Certified "
                    "Protection Professional (CPP) or Physical Security Professional (PSP) "
                    "certification; an entity or organization approved by the ERO; a "
                    "governmental agency with physical security expertise; or an entity or "
                    "organization with demonstrated law enforcement, government, or military "
                    "physical security expertise."
                ),
            ),
            (
                "6.2",
                "",
                (
                    "The Transmission Owner or Transmission Operator, respectively, shall "
                    "ensure that the unaffiliated third party review is completed within 90 "
                    "calendar days of completing the security plan(s) developed in Requirement "
                    "R5. The unaffiliated third party review may, but is not required to, "
                    "include recommended changes to the evaluation performed under Requirement "
                    "R4 or the security plan(s) developed under Requirement R5."
                ),
            ),
            (
                "6.3",
                "",
                (
                    "If the unaffiliated third party reviewer recommends changes to the "
                    "evaluation performed under Requirement R4 or security plan(s) developed "
                    "under Requirement R5, the Transmission Owner or Transmission Operator "
                    "shall, within 60 calendar days of the completion of the unaffiliated third "
                    "party review, for each recommendation: modify its evaluation or security "
                    "plan(s) consistent with the recommendation; or document the reason(s) for "
                    "not modifying the evaluation or security plan(s) consistent with the "
                    "recommendation."
                ),
            ),
            (
                "6.4",
                "",
                (
                    "Each Transmission Owner and Transmission Operator shall implement "
                    "procedures, such as the use of non-disclosure agreements, for protecting "
                    "sensitive or confidential information made available to the unaffiliated "
                    "third party reviewer and to protect or exempt sensitive or confidential "
                    "information developed pursuant to this Reliability Standard from public "
                    "disclosure."
                ),
            ),
        ],
    ),
]

REQUIREMENTS_BY_CODE: dict[str, list] = {
    "CIP-002": CIP002_REQUIREMENTS,
    "CIP-003": CIP003_REQUIREMENTS,
    "CIP-004": CIP004_REQUIREMENTS,
    "CIP-005": CIP005_REQUIREMENTS,
    "CIP-006": CIP006_REQUIREMENTS,
    "CIP-007": CIP007_REQUIREMENTS,
    "CIP-008": CIP008_REQUIREMENTS,
    "CIP-009": CIP009_REQUIREMENTS,
    "CIP-010": CIP010_REQUIREMENTS,
    "CIP-011": CIP011_REQUIREMENTS,
    "CIP-012": CIP012_REQUIREMENTS,
    "CIP-013": CIP013_REQUIREMENTS,
    "CIP-014": CIP014_REQUIREMENTS,
}


def build_domain(short_code: str, source_version: str, full_name: str, purpose: str, source_url: str) -> dict:
    if short_code not in REQUIREMENTS_BY_CODE:
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
    for number, title, req_purpose, parts in REQUIREMENTS_BY_CODE[short_code]:
        objectives.append(
            {
                "number": number,
                "title": title,
                "purpose": req_purpose,
                "practices": [
                    {
                        "id": f"{short_code}-{part_number}",
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
        # Real, verified count of transcribed Requirement Parts across all 13
        # currently-mandatory standards (ADR-0022 completed the 12 that
        # ADR-0021 left as stubs). Asserted against this file's own
        # REQUIREMENTS_BY_CODE below at write time, mirroring
        # generate_c2m2_yaml.py's/generate_nist_csf_yaml.py's precedent.
        "total_practices_in_source": 141,
        "scoring_model": "coverage",
        "mil_levels": [],
        "scoring_note": (
            "NERC CIP is a compliance/audit standard, not a native maturity model — like NIST "
            "CSF 2.0 (ADR-0010), it has no MIL concept, so Practice.mil is always None here. "
            "Scores are the project-defined coverage measure (fraction of a standard's Parts "
            "with accepted/edited evidence), via services/scoring_service.py's "
            "compute_domain_coverage. All 13 currently-mandatory standards are fully "
            "transcribed as of ADR-0022; CIP-015 (approved but not yet in force) is "
            "deliberately excluded — see the nerc-cip-expert skill."
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
        "total_practices_in_source — check REQUIREMENTS_BY_CODE for a missing or duplicated "
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
