"""Generates framework_mapping/pci_dss_v4.yaml (ADR-0027).

Like ISO 27001 (ADR-0024) and SOC 2 (ADR-0026) — and unlike CIS Controls
v8 (ADR-0025) — this framework's real source text is copyrighted,
all-rights-reserved content, not freely licensed for reproduction.
Confirmed directly: the source PDF's own page 1 states "©2006 - 2024 PCI
Security Standards Council, LLC. All Rights Reserved," and no public PCI
SSC reproduction license was found. This is true even though the document
is freely downloadable at no cost (the same "free to download" vs.
"licensed for reproduction" distinction ADR-0026 established for SOC 2).

Given that, this framework gets the same statement-only-equivalent
treatment as ISO 27001/SOC 2 — but PCI DSS v4.0.1 has a real structural
difference from every other framework in this project: it is THREE
levels deep (Requirement -> Section -> Defined Approach Requirement),
not two. Requirement 1 alone ("Install and Maintain Network Security
Controls") has 5 Sections (1.1-1.5), which in turn contain 19 individual
numbered "Defined Approach Requirements" (1.1.1, 1.1.2, 1.2.1-1.2.8,
1.3.1-1.3.3, 1.4.1-1.4.5, 1.5.1) — and this pattern repeats, scaling to
roughly 205 leaf-level Defined Approach Requirements across all 12
top-level Requirements, each with its own "Testing Procedures,"
"Purpose," "Good Practice," "Examples," "Definitions," and "Customized
Approach Objective" elaboration (all clearly the substantial,
copyrightable content, out of scope here the same way CIS's "points of
focus" and NERC's "Measures" column are).

Given this genuinely exceptional depth (no other framework in this
project has three numbered levels, and 205 leaf items would be a
materially larger single-pass transcription than any framework
transcribed so far), this generator transcribes at the SECTION (N.N)
level — e.g., "1.1 Processes and mechanisms for installing and
maintaining network security controls are defined and understood." —
not the finer Defined Approach Requirement (N.N.N) level. Every Section
statement transcribed here is itself real, complete, verified text
(the PDF's own "Sections" summary block at the start of each
Requirement), not a paraphrase or summary — this is a genuine scope
decision (which level to treat as this project's atomic "Practice"),
disclosed explicitly, not a shortcut around the copyright question
(which is settled the same way as ISO 27001/SOC 2). See ADR-0027 for
the full disclosure, including the ~205 leaf-level items being named as
real, unstarted-deeper-granularity future work.

Source, verified directly: fetched the real "Payment Card Industry Data
Security Standard: Requirements and Testing Procedures, v4.0.1" PDF
(June 2024, the current active version — v4.0 was retired 31 December
2024), confirmed via `pypdf` to be genuine PCI SSC content (real title
page, the exact copyright notice quoted above, 397 real pages, the
correct "Sections" summary block for all 12 Requirements totaling
exactly 63 Sections, cross-checked against an independent grep-based
count of the document's own N.N-pattern numbering).
"""

from __future__ import annotations

from pathlib import Path

import yaml

# (short_code, full_name, purpose, [(section_id, section_statement), ...])
REQUIREMENTS: list[tuple[str, str, str, list[tuple[str, str]]]] = [
    (
        "REQ-01",
        "Install and Maintain Network Security Controls",
        (
            "Network security controls (NSCs), such as firewalls and other network security "
            "technologies, are network policy enforcement points that typically control network "
            "traffic between two or more logical or physical network segments (or subnets) based "
            "on pre-defined policies or rules."
        ),
        [
            ("1.1", "Processes and mechanisms for installing and maintaining network security controls are defined and understood."),
            ("1.2", "Network security controls (NSCs) are configured and maintained."),
            ("1.3", "Network access to and from the cardholder data environment is restricted."),
            ("1.4", "Network connections between trusted and untrusted networks are controlled."),
            ("1.5", "Risks to the CDE from computing devices that are able to connect to both untrusted networks and the CDE are mitigated."),
        ],
    ),
    (
        "REQ-02",
        "Apply Secure Configurations to All System Components",
        (
            "Malicious individuals, both external and internal to an entity, often use default "
            "passwords and other vendor default settings to compromise systems. Applying secure "
            "configurations to system components reduces the means available to an attacker to "
            "compromise the system."
        ),
        [
            ("2.1", "Processes and mechanisms for applying secure configurations to all system components are defined and understood."),
            ("2.2", "System components are configured and managed securely."),
            ("2.3", "Wireless environments are configured and managed securely."),
        ],
    ),
    (
        "REQ-03",
        "Protect Stored Account Data",
        (
            "Protection methods such as encryption, truncation, masking, and hashing are critical "
            "components of account data protection. If an intruder circumvents other security "
            "controls and gains access to encrypted account data, the data is unreadable without "
            "the proper cryptographic keys and is unusable to that intruder."
        ),
        [
            ("3.1", "Processes and mechanisms for protecting stored account data are defined and understood."),
            ("3.2", "Storage of account data is kept to a minimum."),
            ("3.3", "Sensitive authentication data (SAD) is not stored after authorization."),
            ("3.4", "Access to displays of full PAN and ability to copy PAN are restricted."),
            ("3.5", "Primary account number (PAN) is secured wherever it is stored."),
            ("3.6", "Cryptographic keys used to protect stored account data are secured."),
            ("3.7", "Where cryptography is used to protect stored account data, key management processes and procedures covering all aspects of the key lifecycle are defined and implemented."),
        ],
    ),
    (
        "REQ-04",
        "Protect Cardholder Data with Strong Cryptography During Transmission Over Open, Public Networks",
        (
            "The use of strong cryptography provides greater assurance in preserving data "
            "confidentiality, integrity, and non-repudiation. PAN must be encrypted during "
            "transmission over networks that are easily accessed by malicious individuals, "
            "including untrusted and public networks."
        ),
        [
            ("4.1", "Processes and mechanisms for protecting cardholder data with strong cryptography during transmission over open, public networks are defined and understood."),
            ("4.2", "PAN is protected with strong cryptography during transmission."),
        ],
    ),
    (
        "REQ-05",
        "Protect All Systems and Networks from Malicious Software",
        (
            "Malicious software (malware) is software or firmware designed to infiltrate or "
            "damage a computer system without the owner's knowledge or consent, with the intent "
            "of compromising the confidentiality, integrity, or availability of the owner's data, "
            "applications, or operating system."
        ),
        [
            ("5.1", "Processes and mechanisms for protecting all systems and networks from malicious software are defined and understood."),
            ("5.2", "Malicious software (malware) is prevented, or detected and addressed."),
            ("5.3", "Anti-malware mechanisms and processes are active, maintained, and monitored."),
            ("5.4", "Anti-phishing mechanisms protect users against phishing attacks."),
        ],
    ),
    (
        "REQ-06",
        "Develop and Maintain Secure Systems and Software",
        (
            "Actors with bad intentions can use security vulnerabilities to gain privileged "
            "access to systems. All system components must have all appropriate software patches "
            "to protect against the exploitation and compromise of account data by malicious "
            "individuals and malicious software."
        ),
        [
            ("6.1", "Processes and mechanisms for developing and maintaining secure systems and software are defined and understood."),
            ("6.2", "Bespoke and custom software are developed securely."),
            ("6.3", "Security vulnerabilities are identified and addressed."),
            ("6.4", "Public-facing web applications are protected against attacks."),
            ("6.5", "Changes to all system components are managed securely."),
        ],
    ),
    (
        "REQ-07",
        "Restrict Access to System Components and Cardholder Data by Business Need to Know",
        (
            "Unauthorized individuals may gain access to critical data or systems due to "
            "ineffective access control rules and definitions. To ensure critical data can only "
            "be accessed by authorized personnel, systems and processes must be in place to limit "
            "access based on need to know and according to job responsibilities."
        ),
        [
            ("7.1", "Processes and mechanisms for restricting access to system components and cardholder data by business need to know are defined and understood."),
            ("7.2", "Access to system components and data is appropriately defined and assigned."),
            ("7.3", "Access to system components and data is managed via an access control system(s)."),
        ],
    ),
    (
        "REQ-08",
        "Identify Users and Authenticate Access to System Components",
        (
            "Two fundamental principles of identifying and authenticating users are to 1) "
            "establish the identity of an individual or process on a computer system, and 2) "
            "prove or verify the user associated with the identity is who the user claims to be."
        ),
        [
            ("8.1", "Processes and mechanisms for identifying users and authenticating access to system components are defined and understood."),
            ("8.2", "User identification and related accounts for users and administrators are strictly managed throughout an account's lifecycle."),
            ("8.3", "Strong authentication for users and administrators is established and managed."),
            ("8.4", "Multi-factor authentication (MFA) is implemented to secure access into the CDE."),
            ("8.5", "Multi-factor authentication (MFA) systems are configured to prevent misuse."),
            ("8.6", "Use of application and system accounts and associated authentication factors is strictly managed."),
        ],
    ),
    (
        "REQ-09",
        "Restrict Physical Access to Cardholder Data",
        (
            "Any physical access to cardholder data or systems that store, process, or transmit "
            "cardholder data provides the opportunity for individuals to access and/or remove "
            "systems or hardcopies containing cardholder data; therefore, physical access should "
            "be appropriately restricted."
        ),
        [
            ("9.1", "Processes and mechanisms for restricting physical access to cardholder data are defined and understood."),
            ("9.2", "Physical access controls manage entry into facilities and systems containing cardholder data."),
            ("9.3", "Physical access for personnel and visitors is authorized and managed."),
            ("9.4", "Media with cardholder data is securely stored, accessed, distributed, and destroyed."),
            ("9.5", "Point of interaction (POI) devices are protected from tampering and unauthorized substitution."),
        ],
    ),
    (
        "REQ-10",
        "Log and Monitor All Access to System Components and Cardholder Data",
        (
            "Logging mechanisms and the ability to track user activities are critical in "
            "preventing, detecting, or minimizing the impact of a data compromise. The presence "
            "of logs on all system components and in the cardholder data environment (CDE) "
            "allows thorough tracking, alerting, and analysis when something does go wrong."
        ),
        [
            ("10.1", "Processes and mechanisms for logging and monitoring all access to system components and cardholder data are defined and understood."),
            ("10.2", "Audit logs are implemented to support the detection of anomalies and suspicious activity, and the forensic analysis of events."),
            ("10.3", "Audit logs are protected from destruction and unauthorized modifications."),
            ("10.4", "Audit logs are reviewed to identify anomalies or suspicious activity."),
            ("10.5", "Audit log history is retained and available for analysis."),
            ("10.6", "Time-synchronization mechanisms support consistent time settings across all systems."),
            ("10.7", "Failures of critical security control systems are detected, reported, and responded to promptly."),
        ],
    ),
    (
        "REQ-11",
        "Test Security of Systems and Networks Regularly",
        (
            "Vulnerabilities are being discovered continually by malicious individuals and "
            "researchers, as well as being introduced by new software. System components, "
            "processes, and bespoke and custom software should be tested frequently to ensure "
            "security controls continue to reflect a changing environment."
        ),
        [
            ("11.1", "Processes and mechanisms for regularly testing security of systems and networks are defined and understood."),
            ("11.2", "Wireless access points are identified and monitored, and unauthorized wireless access points are addressed."),
            ("11.3", "External and internal vulnerabilities are regularly identified, prioritized, and addressed."),
            ("11.4", "External and internal penetration testing is regularly performed, and exploitable vulnerabilities and security weaknesses are corrected."),
            ("11.5", "Network intrusions and unexpected file changes are detected and responded to."),
            ("11.6", "Unauthorized changes on payment pages are detected and responded to."),
        ],
    ),
    (
        "REQ-12",
        "Support Information Security with Organizational Policies and Programs",
        (
            "The organization's overall information security policy sets the tone for the whole "
            "entity and informs personnel what is expected of them. All personnel should be aware "
            "of the sensitivity of cardholder data and their responsibilities for protecting it."
        ),
        [
            ("12.1", "A comprehensive information security policy that governs and provides direction for protection of the entity's information assets is known and current."),
            ("12.2", "Acceptable use policies for end-user technologies are defined and implemented."),
            ("12.3", "Risks to the cardholder data environment are formally identified, evaluated, and managed."),
            ("12.4", "PCI DSS compliance is managed."),
            ("12.5", "PCI DSS scope is documented and validated."),
            ("12.6", "Security awareness education is an ongoing activity."),
            ("12.7", "Personnel are screened to reduce risks from insider threats."),
            ("12.8", "Risk to information assets associated with third-party service provider (TPSP) relationships is managed."),
            ("12.9", "Third-party service providers (TPSPs) support their customers' PCI DSS compliance."),
            ("12.10", "Suspected and confirmed security incidents that could impact the CDE are responded to immediately."),
        ],
    ),
]


def build_domain(short_code: str, full_name: str, purpose: str, sections: list[tuple[str, str]]) -> dict:
    return {
        "short_code": short_code,
        "full_name": full_name,
        "purpose": purpose,
        "practices_populated": True,
        "objectives": [
            {
                "number": 1,
                "title": full_name,
                "purpose": "",
                "practices": [
                    {"id": section_id, "text": statement, "applicability": ""}
                    for section_id, statement in sections
                ],
            }
        ],
        "source_version": "",
        "source_url": "",
    }


def main() -> None:
    framework = {
        "name": "PCI DSS",
        "full_name": "Payment Card Industry Data Security Standard",
        "version": "4.0.1",
        "source_title": "Payment Card Industry Data Security Standard: Requirements and Testing Procedures, v4.0.1",
        "source_publisher": "PCI Security Standards Council, LLC (PCI SSC)",
        "source_date": "2024-06",
        "source_url": "https://www.pcisecuritystandards.org/document_library/",
        "retrieved_date": "2026-07-20",
        "total_practices_in_source": 63,
        "scoring_model": "coverage",
        "mil_levels": [],
        "scoring_note": (
            "PCI DSS has no native maturity-level concept, like NIST CSF 2.0/NERC CIP/ISO 27001/"
            "CIS Controls/SOC 2 — Practice.mil is always None here. Scores are the project-defined "
            "coverage measure via services/scoring_service.py's compute_domain_coverage. Like ISO "
            "27001 (ADR-0024) and SOC 2 (ADR-0026), and UNLIKE CIS Controls (ADR-0025), Practice."
            "text here is real, verified SECTION-level statement text only (e.g. '3.2 Storage of "
            "account data is kept to a minimum.') — PCI DSS v4.0.1 is copyrighted, all-rights-"
            "reserved content (confirmed directly: the source PDF's own page 1 states this "
            "explicitly), despite being freely downloadable, the same distinction ADR-0026 "
            "established for SOC 2. Additionally, PCI DSS is uniquely THREE levels deep "
            "(Requirement -> Section -> Defined Approach Requirement, ~205 leaf-level items) — no "
            "other framework in this project has this depth. This transcription deliberately stops "
            "at the Section level (63 total, one per Requirement's own real 'Sections' summary), "
            "not the finer Defined Approach Requirement level, a disclosed scope decision distinct "
            "from the copyright question — see ADR-0027. Practice.applicability is always empty "
            "here — no per-Section applicability-scope concept was verified in the source "
            "(PCI DSS's SAQ-type scoping operates at a different level not captured per-Section), "
            "unlike NERC CIP's impact tiers, CIS Controls' Implementation Groups, or SOC 2's "
            "Common/Additional-category distinction."
        ),
        "domains": [
            build_domain(short_code, full_name, purpose, sections)
            for short_code, full_name, purpose, sections in REQUIREMENTS
        ],
    }

    total_practices = sum(
        len(o["practices"]) for d in framework["domains"] for o in d["objectives"]
    )
    print(f"Requirements: {len(framework['domains'])} (all fully populated)")
    print(f"Sections encoded: {total_practices} of {framework['total_practices_in_source']}")
    assert total_practices == framework["total_practices_in_source"], (
        "Transcribed Section count does not match this file's own declared "
        "total_practices_in_source — check REQUIREMENTS for a missing or duplicated Section "
        "before shipping this data."
    )

    out_path = Path(__file__).resolve().parents[2] / "framework_mapping" / "pci_dss_v4.yaml"
    with out_path.open("w", encoding="utf-8") as f:
        f.write(
            "# GENERATED FILE. Do not hand-edit — regenerate via\n"
            "# backend/scripts/generate_pci_dss_yaml.py, which is the source of truth\n"
            "# for this file's content and carries the source citation.\n"
        )
        yaml.dump(framework, f, sort_keys=False, allow_unicode=True, width=100)


if __name__ == "__main__":
    main()
