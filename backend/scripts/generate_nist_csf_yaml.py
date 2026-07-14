"""One-off generator for framework_mapping/nist_csf_2_0.yaml.

Not part of the application (see scripts/README.md). Mirrors
generate_c2m2_yaml.py's pattern (Sprint 3) for a second framework.

Source: The NIST Cybersecurity Framework (CSF) 2.0, NIST CSWP 29,
February 26, 2024. https://doi.org/10.6028/NIST.CSWP.29
https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf

Function purpose statements, all 22 category names/purpose statements,
and all 106 subcategory statements below were transcribed directly from
that PDF (parsed locally with pypdf after WebFetch could not decode it,
the same pattern used for C2M2 in Sprint 3 — see
docs/adr/ADR-0009-c2m2-structured-data.md and
docs/adr/ADR-0010-nist-csf-coverage-scoring.md). Unlike C2M2, NIST CSF
2.0's full Core (106 subcategories total, confirmed against NIST's own
stated total) fit within the fetched document, so all 6 functions are
fully populated here — no domain in this framework is left as a stub.

NIST CSF 2.0 does not natively define maturity levels; practices here
have no `mil` value, and this framework is scored by coverage, not
cumulative MIL (see models/framework.py's scoring_model field and
services/scoring_service.py's compute_domain_coverage).
"""

from __future__ import annotations

from pathlib import Path

import yaml

# (function_short_code, full_name, purpose)
FUNCTIONS = [
    (
        "GV",
        "Govern",
        "The organization's cybersecurity risk management strategy, expectations, and "
        "policy are established, communicated, and monitored",
    ),
    (
        "ID",
        "Identify",
        "The organization's current cybersecurity risks are understood",
    ),
    (
        "PR",
        "Protect",
        "Safeguards to manage the organization's cybersecurity risks are used",
    ),
    (
        "DE",
        "Detect",
        "Possible cybersecurity attacks and compromises are found and analyzed",
    ),
    (
        "RS",
        "Respond",
        "Actions regarding a detected cybersecurity incident are taken",
    ),
    (
        "RC",
        "Recover",
        "Assets and operations affected by a cybersecurity incident are restored",
    ),
]

# function_short_code -> list of (category_code, category_title, category_purpose,
#   [(subcategory_number_suffix, text), ...])
CATEGORIES: dict[str, list[tuple[str, str, str, list[tuple[str, str]]]]] = {
    "GV": [
        (
            "GV.OC",
            "Organizational Context",
            "The circumstances — mission, stakeholder expectations, dependencies, and legal, "
            "regulatory, and contractual requirements — surrounding the organization's "
            "cybersecurity risk management decisions are understood",
            [
                ("01", "The organizational mission is understood and informs cybersecurity risk management"),
                ("02", "Internal and external stakeholders are understood, and their needs and expectations regarding cybersecurity risk management are understood and considered"),
                ("03", "Legal, regulatory, and contractual requirements regarding cybersecurity — including privacy and civil liberties obligations — are understood and managed"),
                ("04", "Critical objectives, capabilities, and services that external stakeholders depend on or expect from the organization are understood and communicated"),
                ("05", "Outcomes, capabilities, and services that the organization depends on are understood and communicated"),
            ],
        ),
        (
            "GV.RM",
            "Risk Management Strategy",
            "The organization's priorities, constraints, risk tolerance and appetite statements, "
            "and assumptions are established, communicated, and used to support operational risk "
            "decisions",
            [
                ("01", "Risk management objectives are established and agreed to by organizational stakeholders"),
                ("02", "Risk appetite and risk tolerance statements are established, communicated, and maintained"),
                ("03", "Cybersecurity risk management activities and outcomes are included in enterprise risk management processes"),
                ("04", "Strategic direction that describes appropriate risk response options is established and communicated"),
                ("05", "Lines of communication across the organization are established for cybersecurity risks, including risks from suppliers and other third parties"),
                ("06", "A standardized method for calculating, documenting, categorizing, and prioritizing cybersecurity risks is established and communicated"),
                ("07", "Strategic opportunities (i.e., positive risks) are characterized and are included in organizational cybersecurity risk discussions"),
            ],
        ),
        (
            "GV.RR",
            "Roles, Responsibilities, and Authorities",
            "Cybersecurity roles, responsibilities, and authorities to foster accountability, "
            "performance assessment, and continuous improvement are established and communicated",
            [
                ("01", "Organizational leadership is responsible and accountable for cybersecurity risk and fosters a culture that is risk-aware, ethical, and continually improving"),
                ("02", "Roles, responsibilities, and authorities related to cybersecurity risk management are established, communicated, understood, and enforced"),
                ("03", "Adequate resources are allocated commensurate with the cybersecurity risk strategy, roles, responsibilities, and policies"),
                ("04", "Cybersecurity is included in human resources practices"),
            ],
        ),
        (
            "GV.PO",
            "Policy",
            "Organizational cybersecurity policy is established, communicated, and enforced",
            [
                ("01", "Policy for managing cybersecurity risks is established based on organizational context, cybersecurity strategy, and priorities and is communicated and enforced"),
                ("02", "Policy for managing cybersecurity risks is reviewed, updated, communicated, and enforced to reflect changes in requirements, threats, technology, and organizational mission"),
            ],
        ),
        (
            "GV.OV",
            "Oversight",
            "Results of organization-wide cybersecurity risk management activities and "
            "performance are used to inform, improve, and adjust the risk management strategy",
            [
                ("01", "Cybersecurity risk management strategy outcomes are reviewed to inform and adjust strategy and direction"),
                ("02", "The cybersecurity risk management strategy is reviewed and adjusted to ensure coverage of organizational requirements and risks"),
                ("03", "Organizational cybersecurity risk management performance is evaluated and reviewed for adjustments needed"),
            ],
        ),
        (
            "GV.SC",
            "Cybersecurity Supply Chain Risk Management",
            "Cyber supply chain risk management processes are identified, established, managed, "
            "monitored, and improved by organizational stakeholders",
            [
                ("01", "A cybersecurity supply chain risk management program, strategy, objectives, policies, and processes are established and agreed to by organizational stakeholders"),
                ("02", "Cybersecurity roles and responsibilities for suppliers, customers, and partners are established, communicated, and coordinated internally and externally"),
                ("03", "Cybersecurity supply chain risk management is integrated into cybersecurity and enterprise risk management, risk assessment, and improvement processes"),
                ("04", "Suppliers are known and prioritized by criticality"),
                ("05", "Requirements to address cybersecurity risks in supply chains are established, prioritized, and integrated into contracts and other types of agreements with suppliers and other relevant third parties"),
                ("06", "Planning and due diligence are performed to reduce risks before entering into formal supplier or other third-party relationships"),
                ("07", "The risks posed by a supplier, their products and services, and other third parties are understood, recorded, prioritized, assessed, responded to, and monitored over the course of the relationship"),
                ("08", "Relevant suppliers and other third parties are included in incident planning, response, and recovery activities"),
                ("09", "Supply chain security practices are integrated into cybersecurity and enterprise risk management programs, and their performance is monitored throughout the technology product and service life cycle"),
                ("10", "Cybersecurity supply chain risk management plans include provisions for activities that occur after the conclusion of a partnership or service agreement"),
            ],
        ),
    ],
    "ID": [
        (
            "ID.AM",
            "Asset Management",
            "Assets (e.g., data, hardware, software, systems, facilities, services, people) that "
            "enable the organization to achieve business purposes are identified and managed "
            "consistent with their relative importance to organizational objectives and the "
            "organization's risk strategy",
            [
                ("01", "Inventories of hardware managed by the organization are maintained"),
                ("02", "Inventories of software, services, and systems managed by the organization are maintained"),
                ("03", "Representations of the organization's authorized network communication and internal and external network data flows are maintained"),
                ("04", "Inventories of services provided by suppliers are maintained"),
                ("05", "Assets are prioritized based on classification, criticality, resources, and impact on the mission"),
                ("07", "Inventories of data and corresponding metadata for designated data types are maintained"),
                ("08", "Systems, hardware, software, services, and data are managed throughout their life cycles"),
            ],
        ),
        (
            "ID.RA",
            "Risk Assessment",
            "The cybersecurity risk to the organization, assets, and individuals is understood "
            "by the organization",
            [
                ("01", "Vulnerabilities in assets are identified, validated, and recorded"),
                ("02", "Cyber threat intelligence is received from information sharing forums and sources"),
                ("03", "Internal and external threats to the organization are identified and recorded"),
                ("04", "Potential impacts and likelihoods of threats exploiting vulnerabilities are identified and recorded"),
                ("05", "Threats, vulnerabilities, likelihoods, and impacts are used to understand inherent risk and inform risk response prioritization"),
                ("06", "Risk responses are chosen, prioritized, planned, tracked, and communicated"),
                ("07", "Changes and exceptions are managed, assessed for risk impact, recorded, and tracked"),
                ("08", "Processes for receiving, analyzing, and responding to vulnerability disclosures are established"),
                ("09", "The authenticity and integrity of hardware and software are assessed prior to acquisition and use"),
                ("10", "Critical suppliers are assessed prior to acquisition"),
            ],
        ),
        (
            "ID.IM",
            "Improvement",
            "Improvements to organizational cybersecurity risk management processes, procedures "
            "and activities are identified across all CSF Functions",
            [
                ("01", "Improvements are identified from evaluations"),
                ("02", "Improvements are identified from security tests and exercises, including those done in coordination with suppliers and relevant third parties"),
                ("03", "Improvements are identified from execution of operational processes, procedures, and activities"),
                ("04", "Incident response plans and other cybersecurity plans that affect operations are established, communicated, maintained, and improved"),
            ],
        ),
    ],
    "PR": [
        (
            "PR.AA",
            "Identity Management, Authentication, and Access Control",
            "Access to physical and logical assets is limited to authorized users, services, and "
            "hardware and managed commensurate with the assessed risk of unauthorized access",
            [
                ("01", "Identities and credentials for authorized users, services, and hardware are managed by the organization"),
                ("02", "Identities are proofed and bound to credentials based on the context of interactions"),
                ("03", "Users, services, and hardware are authenticated"),
                ("04", "Identity assertions are protected, conveyed, and verified"),
                ("05", "Access permissions, entitlements, and authorizations are defined in a policy, managed, enforced, and reviewed, and incorporate the principles of least privilege and separation of duties"),
                ("06", "Physical access to assets is managed, monitored, and enforced commensurate with risk"),
            ],
        ),
        (
            "PR.AT",
            "Awareness and Training",
            "The organization's personnel are provided with cybersecurity awareness and training "
            "so that they can perform their cybersecurity-related tasks",
            [
                ("01", "Personnel are provided with awareness and training so that they possess the knowledge and skills to perform general tasks with cybersecurity risks in mind"),
                ("02", "Individuals in specialized roles are provided with awareness and training so that they possess the knowledge and skills to perform relevant tasks with cybersecurity risks in mind"),
            ],
        ),
        (
            "PR.DS",
            "Data Security",
            "Data are managed consistent with the organization's risk strategy to protect the "
            "confidentiality, integrity, and availability of information",
            [
                ("01", "The confidentiality, integrity, and availability of data-at-rest are protected"),
                ("02", "The confidentiality, integrity, and availability of data-in-transit are protected"),
                ("10", "The confidentiality, integrity, and availability of data-in-use are protected"),
                ("11", "Backups of data are created, protected, maintained, and tested"),
            ],
        ),
        (
            "PR.PS",
            "Platform Security",
            "The hardware, software (e.g., firmware, operating systems, applications), and "
            "services of physical and virtual platforms are managed consistent with the "
            "organization's risk strategy to protect their confidentiality, integrity, and "
            "availability",
            [
                ("01", "Configuration management practices are established and applied"),
                ("02", "Software is maintained, replaced, and removed commensurate with risk"),
                ("03", "Hardware is maintained, replaced, and removed commensurate with risk"),
                ("04", "Log records are generated and made available for continuous monitoring"),
                ("05", "Installation and execution of unauthorized software are prevented"),
                ("06", "Secure software development practices are integrated, and their performance is monitored throughout the software development life cycle"),
            ],
        ),
        (
            "PR.IR",
            "Technology Infrastructure Resilience",
            "Security architectures are managed with the organization's risk strategy to protect "
            "asset confidentiality, integrity, and availability, and organizational resilience",
            [
                ("01", "Networks and environments are protected from unauthorized logical access and usage"),
                ("02", "The organization's technology assets are protected from environmental threats"),
                ("03", "Mechanisms are implemented to achieve resilience requirements in normal and adverse situations"),
                ("04", "Adequate resource capacity to ensure availability is maintained"),
            ],
        ),
    ],
    "DE": [
        (
            "DE.CM",
            "Continuous Monitoring",
            "Assets are monitored to find anomalies, indicators of compromise, and other "
            "potentially adverse events",
            [
                ("01", "Networks and network services are monitored to find potentially adverse events"),
                ("02", "The physical environment is monitored to find potentially adverse events"),
                ("03", "Personnel activity and technology usage are monitored to find potentially adverse events"),
                ("06", "External service provider activities and services are monitored to find potentially adverse events"),
                ("09", "Computing hardware and software, runtime environments, and their data are monitored to find potentially adverse events"),
            ],
        ),
        (
            "DE.AE",
            "Adverse Event Analysis",
            "Anomalies, indicators of compromise, and other potentially adverse events are "
            "analyzed to characterize the events and detect cybersecurity incidents",
            [
                ("02", "Potentially adverse events are analyzed to better understand associated activities"),
                ("03", "Information is correlated from multiple sources"),
                ("04", "The estimated impact and scope of adverse events are understood"),
                ("06", "Information on adverse events is provided to authorized staff and tools"),
                ("07", "Cyber threat intelligence and other contextual information are integrated into the analysis"),
                ("08", "Incidents are declared when adverse events meet the defined incident criteria"),
            ],
        ),
    ],
    "RS": [
        (
            "RS.MA",
            "Incident Management",
            "Responses to detected cybersecurity incidents are managed",
            [
                ("01", "The incident response plan is executed in coordination with relevant third parties once an incident is declared"),
                ("02", "Incident reports are triaged and validated"),
                ("03", "Incidents are categorized and prioritized"),
                ("04", "Incidents are escalated or elevated as needed"),
                ("05", "The criteria for initiating incident recovery are applied"),
            ],
        ),
        (
            "RS.AN",
            "Incident Analysis",
            "Investigations are conducted to ensure effective response and support forensics and "
            "recovery activities",
            [
                ("03", "Analysis is performed to establish what has taken place during an incident and the root cause of the incident"),
                ("06", "Actions performed during an investigation are recorded, and the records' integrity and provenance are preserved"),
                ("07", "Incident data and metadata are collected, and their integrity and provenance are preserved"),
                ("08", "An incident's magnitude is estimated and validated"),
            ],
        ),
        (
            "RS.CO",
            "Incident Response Reporting and Communication",
            "Response activities are coordinated with internal and external stakeholders as "
            "required by laws, regulations, or policies",
            [
                ("02", "Internal and external stakeholders are notified of incidents"),
                ("03", "Information is shared with designated internal and external stakeholders"),
            ],
        ),
        (
            "RS.MI",
            "Incident Mitigation",
            "Activities are performed to prevent expansion of an event and mitigate its effects",
            [
                ("01", "Incidents are contained"),
                ("02", "Incidents are eradicated"),
            ],
        ),
    ],
    "RC": [
        (
            "RC.RP",
            "Incident Recovery Plan Execution",
            "Restoration activities are performed to ensure operational availability of systems "
            "and services affected by cybersecurity incidents",
            [
                ("01", "The recovery portion of the incident response plan is executed once initiated from the incident response process"),
                ("02", "Recovery actions are selected, scoped, prioritized, and performed"),
                ("03", "The integrity of backups and other restoration assets is verified before using them for restoration"),
                ("04", "Critical mission functions and cybersecurity risk management are considered to establish post-incident operational norms"),
                ("05", "The integrity of restored assets is verified, systems and services are restored, and normal operating status is confirmed"),
                ("06", "The end of incident recovery is declared based on criteria, and incident-related documentation is completed"),
            ],
        ),
        (
            "RC.CO",
            "Incident Recovery Communication",
            "Restoration activities are coordinated with internal and external parties",
            [
                ("03", "Recovery activities and progress in restoring operational capabilities are communicated to designated internal and external stakeholders"),
                ("04", "Public updates on incident recovery are shared using approved methods and messaging"),
            ],
        ),
    ],
}


def build_domain(short_code: str, full_name: str, purpose: str) -> dict:
    categories = CATEGORIES[short_code]
    objectives = []
    for number, (category_code, category_title, category_purpose, subcats) in enumerate(
        categories, start=1
    ):
        objectives.append(
            {
                "number": number,
                "title": f"{category_title} ({category_code})",
                "purpose": category_purpose,
                "practices": [
                    {"id": f"{category_code}-{suffix}", "text": text}
                    for suffix, text in subcats
                ],
            }
        )
    return {
        "short_code": short_code,
        "full_name": full_name,
        "purpose": purpose,
        "practices_populated": True,
        "objectives": objectives,
    }


def main() -> None:
    framework = {
        "name": "NIST CSF 2.0",
        "full_name": "NIST Cybersecurity Framework",
        "version": "2.0",
        "source_title": "The NIST Cybersecurity Framework (CSF) 2.0 (NIST CSWP 29)",
        "source_publisher": "National Institute of Standards and Technology",
        "source_date": "2024-02-26",
        "source_url": "https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf",
        "retrieved_date": "2026-07-14",
        "total_practices_in_source": 106,
        "scoring_model": "coverage",
        "mil_levels": [],
        "scoring_note": (
            "NIST CSF 2.0 does not natively define maturity levels for its Functions, "
            "Categories, or Subcategories (see the nist-csf-expert skill). Scores for this "
            "framework are a project-defined coverage measure: the fraction of a Function's "
            "Subcategories with accepted or edited evidence, computed by "
            "services/scoring_service.py's compute_domain_coverage. This is NOT part of the "
            "NIST standard itself and must always be presented as such."
        ),
        "domains": [build_domain(code, name, purpose) for code, name, purpose in FUNCTIONS],
    }

    total_practices = sum(
        len(o["practices"]) for d in framework["domains"] for o in d["objectives"]
    )
    print(f"Functions: {len(framework['domains'])} (all fully populated)")
    print(f"Subcategories encoded: {total_practices} of {framework['total_practices_in_source']}")
    assert total_practices == framework["total_practices_in_source"], (
        "Transcribed subcategory count does not match NIST's own stated total of 106 — "
        "check CATEGORIES for a missing or duplicated entry before shipping this data."
    )

    out_path = (
        Path(__file__).resolve().parents[2] / "framework_mapping" / "nist_csf_2_0.yaml"
    )
    with out_path.open("w", encoding="utf-8") as f:
        f.write(
            "# GENERATED FILE. Do not hand-edit — regenerate via\n"
            "# backend/scripts/generate_nist_csf_yaml.py, which is the source of truth\n"
            "# for this file's content and carries the source citation.\n"
        )
        yaml.dump(framework, f, sort_keys=False, allow_unicode=True, width=100)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
