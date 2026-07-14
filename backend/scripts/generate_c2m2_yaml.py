"""One-off generator for framework_mapping/c2m2_v2_1.yaml.

Not part of the application (see scripts/README.md: this directory is
for humans to run directly, not for the app to import). Run once to
produce the committed YAML file; re-run only if the source content
below is corrected or extended (e.g. when a future contributor
transcribes another domain's practices from the source PDF).

Source: Cybersecurity Capability Maturity Model (C2M2), Version 2.1,
U.S. Department of Energy, June 2022.
https://www.energy.gov/sites/default/files/2022-06/C2M2%20Version%202.1%20June%202022.pdf
Verbatim domain purpose statements and the ASSET/ACCESS domain practice
text below were transcribed directly from that PDF (parsed locally with
pypdf after WebFetch could not decode it), not reconstructed from
memory — see docs/adr/ADR-0009-c2m2-structured-data.md.
"""

from __future__ import annotations

from pathlib import Path

import yaml

DOMAIN_PURPOSES = {
    "ASSET": (
        "Asset, Change, and Configuration Management",
        "Manage the organization's IT and OT assets, including both hardware and "
        "software, and information assets commensurate with the risk to critical "
        "infrastructure and organizational objectives.",
    ),
    "THREAT": (
        "Threat and Vulnerability Management",
        "Establish and maintain plans, procedures, and technologies to detect, "
        "identify, analyze, manage, and respond to cybersecurity threats and "
        "vulnerabilities, commensurate with the risk to the organization's "
        "infrastructure (such as critical, IT, and operational) and organizational "
        "objectives.",
    ),
    "RISK": (
        "Risk Management",
        "Establish, operate, and maintain an enterprise cyber risk management "
        "program to identify, analyze, and respond to cyber risk the organization "
        "is subject to, including its business units, subsidiaries, related "
        "interconnected infrastructure, and stakeholders.",
    ),
    "ACCESS": (
        "Identity and Access Management",
        "Create and manage identities for entities that may be granted logical or "
        "physical access to the organization's assets. Control access to the "
        "organization's assets, commensurate with the risk to critical "
        "infrastructure and organizational objectives.",
    ),
    "SITUATION": (
        "Situational Awareness",
        "Establish and maintain activities and technologies to collect, monitor, "
        "analyze, alarm, report, and use operational, security, and threat "
        "information, including status and summary information from the other "
        "model domains, to establish situational awareness for both the "
        "organization's operational state and cybersecurity state.",
    ),
    "RESPONSE": (
        "Event and Incident Response, Continuity of Operations",
        "Establish and maintain plans, procedures, and technologies to detect, "
        "analyze, mitigate, respond to, and recover from cybersecurity events and "
        "incidents and to sustain operations during cybersecurity incidents, "
        "commensurate with the risk to critical infrastructure and organizational "
        "objectives.",
    ),
    "THIRD-PARTIES": (
        "Third-Party Risk Management",
        "Establish and maintain controls to manage the cyber risks arising from "
        "suppliers and other third parties, commensurate with the risk to critical "
        "infrastructure and organizational objectives.",
    ),
    "WORKFORCE": (
        "Workforce Management",
        "Establish and maintain plans, procedures, technologies, and controls to "
        "create a culture of cybersecurity and to ensure the ongoing suitability "
        "and competence of personnel, commensurate with the risk to critical "
        "infrastructure and organizational objectives.",
    ),
    "ARCHITECTURE": (
        "Cybersecurity Architecture",
        "Establish and maintain the structure and behavior of the organization's "
        "cybersecurity architecture, including controls, processes, technologies, "
        "and other elements, commensurate with the risk to critical infrastructure "
        "and organizational objectives.",
    ),
    "PROGRAM": (
        "Cybersecurity Program Management",
        "Establish and maintain an enterprise cybersecurity program that provides "
        "governance, strategic planning, and sponsorship for the organization's "
        "cybersecurity activities in a manner that aligns cybersecurity objectives "
        "with both the organization's strategic objectives and the risk to "
        "critical infrastructure.",
    ),
}

# Order matters: this is the order domains appear in the source document.
DOMAIN_ORDER = [
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
]

# (objective_number, objective_title, [(letter, mil, text), ...])
ASSET_OBJECTIVES = [
    (
        1,
        "Manage IT and OT Asset Inventory",
        [
            ("a", 1, "IT and OT assets that are important to the delivery of the function are inventoried, at least in an ad hoc manner"),
            ("b", 2, "The IT and OT asset inventory includes assets within the function that may be leveraged to achieve a threat objective"),
            ("c", 2, "Inventoried IT and OT assets are prioritized based on defined criteria that include importance to the delivery of the function"),
            ("d", 2, "Prioritization criteria include consideration of the degree to which an asset within the function may be leveraged to achieve a threat objective"),
            ("e", 2, "The IT and OT inventory includes attributes that support cybersecurity activities (for example, location, asset priority, asset owner, operating system, and firmware versions)"),
            ("f", 3, "The IT and OT asset inventory is complete (the inventory includes all assets within the function)"),
            ("g", 3, "The IT and OT asset inventory is current, that is, it is updated periodically and according to defined triggers, such as system changes"),
            ("h", 3, "Data is destroyed or securely removed from IT and OT assets prior to redeployment and at end of life"),
        ],
    ),
    (
        2,
        "Manage Information Asset Inventory",
        [
            ("a", 1, "Information assets that are important to the delivery of the function (for example, SCADA set points and customer information) are inventoried, at least in an ad hoc manner"),
            ("b", 2, "The information asset inventory includes information assets within the function that may be leveraged to achieve a threat objective"),
            ("c", 2, "Inventoried information assets are categorized based on defined criteria that includes importance to the delivery of the function"),
            ("d", 2, "Categorization criteria include consideration of the degree to which an asset within the function may be leveraged to achieve a threat objective"),
            ("e", 2, "The information asset inventory includes attributes that support cybersecurity activities (for example, asset category, backup locations and frequencies, storage locations, asset owner, cybersecurity requirements)"),
            ("f", 3, "The information asset inventory is complete (the inventory includes all assets within the function)"),
            ("g", 3, "The information asset inventory is current, that is, it is updated periodically and according to defined triggers, such as system changes"),
            ("h", 3, "Information assets are sanitized or destroyed at end of life using techniques appropriate to their cybersecurity requirements"),
        ],
    ),
    (
        3,
        "Manage IT and OT Asset Configuration",
        [
            ("a", 1, "Configuration baselines are established, at least in an ad hoc manner"),
            ("b", 2, "Configuration baselines are used to configure assets at deployment and restoration"),
            ("c", 2, "Configuration baselines incorporate applicable requirements from the cybersecurity architecture (ARCHITECTURE-1f)"),
            ("d", 2, "Configuration baselines are reviewed and updated periodically and according to defined triggers, such as system changes and changes to the cybersecurity architecture"),
            ("e", 3, "Asset configurations are monitored for consistency with baselines throughout the assets' lifecycles"),
        ],
    ),
    (
        4,
        "Manage Changes to IT and OT Assets",
        [
            ("a", 1, "Changes to assets are evaluated and approved before being implemented, at least in an ad hoc manner"),
            ("b", 1, "Changes to assets are documented, at least in an ad hoc manner"),
            ("c", 2, "Documentation requirements for asset changes are established and maintained"),
            ("d", 2, "Changes to higher priority assets are tested prior to being deployed"),
            ("e", 2, "Changes and updates are implemented in a secure manner"),
            ("f", 2, "The capability to reverse changes is established and maintained for assets that are important to the delivery of the function"),
            ("g", 2, "Change management practices address the full lifecycle of assets (for example, acquisition, deployment, operation, retirement)"),
            ("h", 3, "Changes to higher priority assets are tested for cybersecurity impact prior to being deployed"),
            ("i", 3, "Change logs include information about modifications that impact the cybersecurity requirements of assets"),
        ],
    ),
    (
        5,
        "Management Activities for the ASSET domain",
        [
            ("a", 2, "Documented procedures are established, followed, and maintained for activities in the ASSET domain"),
            ("b", 2, "Adequate resources (people, funding, and tools) are provided to support activities in the ASSET domain"),
            ("c", 3, "Up-to-date policies or other organizational directives define requirements for activities in the ASSET domain"),
            ("d", 3, "Responsibility, accountability, and authority for the performance of activities in the ASSET domain are assigned to personnel"),
            ("e", 3, "Personnel performing activities in the ASSET domain have the skills and knowledge needed to perform their assigned responsibilities"),
            ("f", 3, "The effectiveness of activities in the ASSET domain is evaluated and tracked"),
        ],
    ),
]

ACCESS_OBJECTIVES = [
    (
        1,
        "Establish Identities and Manage Authentication",
        [
            ("a", 1, "Identities are provisioned, at least in an ad hoc manner, for personnel and other entities such as services and devices that require access to assets (note that this does not preclude shared identities)"),
            ("b", 1, "Credentials (such as passwords, smartcards, certificates, and keys) are issued for personnel and other entities that require access to assets, at least in an ad hoc manner"),
            ("c", 1, "Identities are deprovisioned, at least in an ad hoc manner, when no longer required"),
            ("d", 2, "Password strength and reuse restrictions are defined and enforced"),
            ("e", 2, "Identity repositories are reviewed and updated periodically and according to defined triggers, such as system changes and changes to organizational structure"),
            ("f", 2, "Identities are deprovisioned within organization-defined time thresholds when no longer required"),
            ("g", 2, "The use of privileged credentials is limited to processes for which they are required"),
            ("h", 2, "Stronger credentials, multifactor authentication, or single use credentials are required for higher risk access (such as privileged accounts, service accounts, shared accounts, and remote access)"),
            ("i", 3, "Multifactor authentication is required for all access, where feasible"),
            ("j", 3, "Identities are disabled after a defined period of inactivity, where feasible"),
        ],
    ),
    (
        2,
        "Control Logical Access",
        [
            ("a", 1, "Logical access controls are implemented, at least in an ad hoc manner"),
            ("b", 1, "Logical access privileges are revoked when no longer needed, at least in an ad hoc manner"),
            ("c", 2, "Logical access requirements are established and maintained (for example, rules for which types of entities are allowed to access an asset, limits of allowed access, constraints on remote access, authentication parameters)"),
            ("d", 2, "Logical access requirements incorporate the principle of least privilege"),
            ("e", 2, "Logical access requirements incorporate the principle of separation of duties"),
            ("f", 2, "Logical access requests are reviewed and approved by the asset owner"),
            ("g", 2, "Logical access privileges that pose higher risk to the function receive additional scrutiny and monitoring"),
            ("h", 3, "Logical access privileges are reviewed and updated to ensure conformance with access requirements periodically and according to defined triggers, such as changes to organizational structure, and after any temporary elevation of privileges"),
            ("i", 3, "Anomalous logical access attempts are monitored as indicators of cybersecurity events"),
        ],
    ),
    (
        3,
        "Control Physical Access",
        [
            ("a", 1, "Physical access controls (such as fences, locks, and signage) are implemented, at least in an ad hoc manner"),
            ("b", 1, "Physical access privileges are revoked when no longer needed, at least in an ad hoc manner"),
            ("c", 1, "Physical access logs are maintained, at least in an ad hoc manner"),
            ("d", 2, "Physical access requirements are established and maintained (for example, rules for who is allowed to access an asset, how access is granted, limits of allowed access)"),
            ("e", 2, "Physical access requirements incorporate the principle of least privilege"),
            ("f", 2, "Physical access requirements incorporate the principle of separation of duties"),
            ("g", 2, "Physical access requests are reviewed and approved by the asset owner"),
            ("h", 2, "Physical access privileges that pose higher risk to the function receive additional scrutiny and monitoring"),
            ("i", 3, "Physical access privileges are reviewed and updated"),
            ("j", 3, "Physical access is monitored to identify potential cybersecurity events"),
        ],
    ),
    (
        4,
        "Management Activities for the ACCESS domain",
        [
            ("a", 2, "Documented procedures are established, followed, and maintained for activities in the ACCESS domain"),
            ("b", 2, "Adequate resources (people, funding, and tools) are provided to support activities in the ACCESS domain"),
            ("c", 3, "Up-to-date policies or other organizational directives define requirements for activities in the ACCESS domain"),
            ("d", 3, "Responsibility, accountability, and authority for the performance of activities in the ACCESS domain are assigned to personnel"),
            ("e", 3, "Personnel performing activities in the ACCESS domain have the skills and knowledge needed to perform their assigned responsibilities"),
            ("f", 3, "The effectiveness of activities in the ACCESS domain is evaluated and tracked"),
        ],
    ),
]

POPULATED_OBJECTIVES = {
    "ASSET": ASSET_OBJECTIVES,
    "ACCESS": ACCESS_OBJECTIVES,
}


def build_domain(short_code: str) -> dict:
    full_name, purpose = DOMAIN_PURPOSES[short_code]
    objectives_source = POPULATED_OBJECTIVES.get(short_code)
    if objectives_source is None:
        return {
            "short_code": short_code,
            "full_name": full_name,
            "purpose": purpose,
            "practices_populated": False,
            "objectives": [],
        }

    objectives = []
    for number, title, practices in objectives_source:
        objectives.append(
            {
                "number": number,
                "title": title,
                "practices": [
                    {"id": f"{short_code}-{number}{letter}", "mil": mil, "text": text}
                    for letter, mil, text in practices
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
        "name": "C2M2",
        "full_name": "Cybersecurity Capability Maturity Model",
        "version": "2.1",
        "source_title": "Cybersecurity Capability Maturity Model (C2M2), Version 2.1",
        "source_publisher": "U.S. Department of Energy",
        "source_date": "2022-06",
        "source_url": (
            "https://www.energy.gov/sites/default/files/2022-06/"
            "C2M2%20Version%202.1%20June%202022.pdf"
        ),
        "retrieved_date": "2026-07-14",
        "total_practices_in_source": 356,
        "scoring_model": "cumulative_mil",
        "mil_levels": [
            {"level": 0, "name": "Not Performed", "description": "Practices are not performed."},
            {
                "level": 1,
                "name": "Initiated",
                "description": "Initial practices are performed but may be ad hoc.",
            },
            {
                "level": 2,
                "name": "Performed",
                "description": (
                    "Management characteristics: practices are documented and adequate "
                    "resources are provided. Approach characteristic: practices are more "
                    "complete or advanced than at MIL1."
                ),
            },
            {
                "level": 3,
                "name": "Managed",
                "description": (
                    "Management characteristics: activities are guided by policy, "
                    "responsibility/accountability/authority are assigned, personnel have "
                    "adequate skills and knowledge, and effectiveness is evaluated and "
                    "tracked. Approach characteristic: practices are more complete or "
                    "advanced than at MIL2."
                ),
            },
        ],
        "scoring_note": (
            "MILs are cumulative within each domain and apply independently across "
            "domains: to earn a MIL in a domain, an organization must perform all "
            "practices in that level and every preceding level in that same domain. "
            "See services/scoring_service.py."
        ),
        "domains": [build_domain(code) for code in DOMAIN_ORDER],
    }

    populated = sum(1 for d in framework["domains"] if d["practices_populated"])
    total_practices = sum(
        len(o["practices"]) for d in framework["domains"] for o in d["objectives"]
    )
    print(f"Domains: {len(framework['domains'])} ({populated} fully populated)")
    print(f"Practices encoded: {total_practices} of {framework['total_practices_in_source']}")

    out_path = (
        Path(__file__).resolve().parents[2] / "framework_mapping" / "c2m2_v2_1.yaml"
    )
    with out_path.open("w", encoding="utf-8") as f:
        f.write(
            "# GENERATED FILE. Do not hand-edit — regenerate via\n"
            "# backend/scripts/generate_c2m2_yaml.py, which is the source of truth\n"
            "# for this file's content and carries the source citation.\n"
        )
        yaml.dump(framework, f, sort_keys=False, allow_unicode=True, width=100)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
