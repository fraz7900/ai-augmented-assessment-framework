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

Sprint 10 follow-up (US-3.1a): the remaining 8 domains (THREAT, RISK,
SITUATION, RESPONSE, THIRD-PARTIES, WORKFORCE, ARCHITECTURE, PROGRAM —
285 practices) were transcribed the same way: the PDF downloaded fresh
and parsed locally with pypdf, page-range-mapped per domain, and the
resulting practice count (285 new + 71 existing = 356) checked against
this file's own total_practices_in_source. Three objectives had a
MIL-level label silently dropped by pypdf's extraction (RESPONSE-4,
ARCHITECTURE-2, ARCHITECTURE-6); each is called out inline where it
occurs, with the correct MIL level confirmed either against a secondary
published summary of the same standard or, for ARCHITECTURE-6, by
matching the identical MIL2=a,b/MIL3=c,d,e,f pattern every other
domain's Management Activities objective already uses. C2M2 is now
fully transcribed: all 10 domains, `practices_populated: True`.
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

# Sprint 10 follow-up (US-3.1a): the remaining 8 domains, transcribed the same
# way as ASSET/ACCESS (ADR-0009) - the source PDF downloaded fresh and parsed
# locally with pypdf, cross-checked where the extraction showed a suspicious
# artifact. Three objectives (RESPONSE-4, ARCHITECTURE-2, ARCHITECTURE-6) had
# a MIL-level label silently dropped by pypdf's text extraction (detectable as
# a stray leading space before the next practice letter); all three were
# independently cross-checked against a secondary published summary of the
# same standard before being transcribed with the corrected MIL level.
THREAT_OBJECTIVES = [
    (
        1,
        "Reduce Cybersecurity Vulnerabilities",
        [
            ("a", 1, "Information sources to support cybersecurity vulnerability discovery are identified, at least in an ad hoc manner"),
            ("b", 1, "Cybersecurity vulnerability information is gathered and interpreted for the function, at least in an ad hoc manner"),
            ("c", 1, "Cybersecurity vulnerability assessments are performed, at least in an ad hoc manner"),
            ("d", 1, "Cybersecurity vulnerabilities that are relevant to the delivery of the function are mitigated, at least in an ad hoc manner"),
            ("e", 2, "Cybersecurity vulnerability information sources that collectively address higher priority assets are monitored"),
            ("f", 2, "Cybersecurity vulnerability assessments are performed periodically and according to defined triggers, such as system changes and external events"),
            ("g", 2, "Identified cybersecurity vulnerabilities are analyzed and prioritized, and are addressed accordingly"),
            ("h", 2, "Operational impact to the function is evaluated prior to deploying patches or other mitigations"),
            ("i", 2, "Information on discovered cybersecurity vulnerabilities is shared with organization-defined stakeholders"),
            ("j", 3, "Cybersecurity vulnerability information sources that collectively address all IT and OT assets within the function are monitored"),
            ("k", 3, "Cybersecurity vulnerability assessments are performed by parties that are independent of the operations of the function"),
            ("l", 3, "Vulnerability monitoring activities include review to confirm that actions taken in response to cybersecurity vulnerabilities were effective"),
            ("m", 3, "Mechanisms are established and maintained to receive and respond to reports from the public or external parties of potential vulnerabilities related to the organization's IT and OT assets, such as public-facing websites or mobile applications"),
        ],
    ),
    (
        2,
        "Respond to Threats and Share Threat Information",
        [
            ("a", 1, "Internal and external information sources to support threat management activities are identified, at least in an ad hoc manner"),
            ("b", 1, "Information about cybersecurity threats is gathered and interpreted for the function, at least in an ad hoc manner"),
            ("c", 1, "Threat objectives for the function are identified, at least in an ad hoc manner"),
            ("d", 1, "Threats that are relevant to the delivery of the function are addressed, at least in an ad hoc manner"),
            ("e", 2, "A threat profile for the function is established that includes threat objectives and additional threat characteristics (for example, threat actor types, motives, capabilities, and targets)"),
            ("f", 2, "Threat information sources that collectively address all components of the threat profile are prioritized and monitored"),
            ("g", 2, "Identified threats are analyzed and prioritized and are addressed accordingly"),
            ("h", 2, "Threat information is exchanged with stakeholders (for example, executives, operations staff, government, connected organizations, vendors, sector organizations, regulators, Information Sharing and Analysis Centers [ISACs])"),
            ("i", 3, "The threat profile for the function is updated periodically and according to defined triggers, such as system changes and external events"),
            ("j", 3, "Threat monitoring and response activities leverage and trigger predefined states of operation (SITUATION-3g)"),
            ("k", 3, "Secure, near-real-time methods are used for receiving and sharing threat information to enable rapid analysis and action"),
        ],
    ),
    (
        3,
        "Management Activities for the THREAT domain",
        [
            ("a", 2, "Documented procedures are established, followed, and maintained for activities in the THREAT domain"),
            ("b", 2, "Adequate resources (people, funding, and tools) are provided to support activities in the THREAT domain"),
            ("c", 3, "Up-to-date policies or other organizational directives define requirements for activities in the THREAT domain"),
            ("d", 3, "Responsibility, accountability, and authority for the performance of activities in the THREAT domain are assigned to personnel"),
            ("e", 3, "Personnel performing activities in the THREAT domain have the skills and knowledge needed to perform their assigned responsibilities"),
            ("f", 3, "The effectiveness of activities in the THREAT domain is evaluated and tracked"),
        ],
    ),
]

RISK_OBJECTIVES = [
    (
        1,
        "Establish and Maintain Cyber Risk Management Strategy and Program",
        [
            ("a", 1, "The organization has a strategy for cyber risk management, which may be developed and managed in an ad hoc manner"),
            ("b", 2, "A strategy for cyber risk management is established and maintained in alignment with the organization's cybersecurity program strategy (PROGRAM-1b) and enterprise architecture"),
            ("c", 2, "The cyber risk management program is established and maintained to perform cyber risk management activities according to the cyber risk management strategy"),
            ("d", 2, "Information from RISK domain activities is communicated to relevant stakeholders"),
            ("e", 2, "Governance for the cyber risk management program is established and maintained"),
            ("f", 2, "Senior management sponsorship for the cyber risk management program is visible and active"),
            ("g", 3, "The cyber risk management program aligns with the organization's mission and objectives"),
            ("h", 3, "The cyber risk management program is coordinated with the organization's enterprise-wide risk management program"),
        ],
    ),
    (
        2,
        "Identify Cyber Risk",
        [
            ("a", 1, "Cyber risks are identified, at least in an ad hoc manner"),
            ("b", 2, "A defined method is used to identify cyber risks"),
            ("c", 2, "Stakeholders from appropriate operations and business areas participate in the identification of cyber risks"),
            ("d", 2, "Identified cyber risks are consolidated into categories (for example, data breaches, insider mistakes, ransomware, OT control takeover) to facilitate management at the category level"),
            ("e", 2, "Cyber risk categories and cyber risks are documented in a risk register or other artifact"),
            ("f", 2, "Cyber risk categories and cyber risks are assigned to risk owners"),
            ("g", 2, "Cyber risk identification activities are performed periodically and according to defined triggers, such as system changes and external events"),
            ("h", 3, "Cyber risk identification activities leverage asset inventory and prioritization information from the ASSET domain, such as IT and OT asset end of support, single points of failure, information asset risk of disclosure, tampering, or destruction"),
            ("i", 3, "Vulnerability management information from THREAT domain activities is used to update cyber risks and identify new risks (such as risks arising from vulnerabilities that pose an ongoing risk to the organization or newly identified vulnerabilities)"),
            ("j", 3, "Threat management information from THREAT domain activities is used to update cyber risks and identify new risks"),
            ("k", 3, "Information from THIRD-PARTIES domain activities is used to update cyber risks and identify new risks"),
            ("l", 3, "Information from ARCHITECTURE domain activities (such as unmitigated architectural conformance gaps) is used to update cyber risks and identify new risks"),
            ("m", 3, "Cyber risk identification considers risks that may arise from or impact critical infrastructure or other interdependent organizations"),
        ],
    ),
    (
        3,
        "Analyze Cyber Risk",
        [
            ("a", 1, "Cyber risks are prioritized based on estimated impact, at least in an ad hoc manner"),
            ("b", 2, "Defined criteria are used to prioritize cyber risks (for example, impact to the organization, impact to the community, likelihood, susceptibility, risk tolerance)"),
            ("c", 2, "A defined method is used to estimate impact for higher priority cyber risks (for example, comparison to actual events, risk quantification)"),
            ("d", 2, "Defined methods are used to analyze higher priority cyber risks (for example, analyzing the prevalence of types of attacks to estimate likelihood, using the results of controls assessments to estimate susceptibility)"),
            ("e", 2, "Organizational stakeholders from appropriate operations and business functions participate in the analysis of higher priority cyber risks"),
            ("f", 2, "Cyber risks are removed from the risk register or other artifact used to document and manage identified risks when they no longer require tracking or response"),
            ("g", 3, "Cyber risk analyses are updated periodically and according to defined triggers, such as system changes, external events, and information from other model domains"),
        ],
    ),
    (
        4,
        "Respond to Cyber Risk",
        [
            ("a", 1, "Risk responses (such as mitigate, accept, avoid, or transfer) are implemented to address cyber risks, at least in an ad hoc manner"),
            ("b", 2, "A defined method is used to select and implement risk responses based on analysis and prioritization"),
            ("c", 3, "Cybersecurity controls are evaluated to determine whether they are designed appropriately and are operating as intended to mitigate identified cyber risks"),
            ("d", 3, "Results from cyber risk impact analyses and cybersecurity control evaluations are reviewed together by enterprise leadership to determine whether cyber risks are sufficiently mitigated, and risk tolerances are not exceeded"),
            ("e", 3, "Risk responses (such as mitigate, accept, avoid, or transfer) are reviewed periodically by leadership to determine whether they are still appropriate"),
        ],
    ),
    (
        5,
        "Management Activities for the RISK domain",
        [
            ("a", 2, "Documented procedures are established, followed, and maintained for activities in the RISK domain"),
            ("b", 2, "Adequate resources (people, funding, and tools) are provided to support activities in the RISK domain"),
            ("c", 3, "Up-to-date policies or other organizational directives define requirements for activities in the RISK domain"),
            ("d", 3, "Responsibility, accountability, and authority for the performance of activities in the RISK domain are assigned to personnel"),
            ("e", 3, "Personnel performing activities in the RISK domain have the skills and knowledge needed to perform their assigned responsibilities"),
            ("f", 3, "The effectiveness of activities in the RISK domain is evaluated and tracked"),
        ],
    ),
]

SITUATION_OBJECTIVES = [
    (
        1,
        "Perform Logging",
        [
            ("a", 1, "Logging is occurring for assets that are important to the delivery of the function, at least in an ad hoc manner"),
            ("b", 2, "Logging is occurring for assets within the function that may be leveraged to achieve a threat objective, wherever feasible"),
            ("c", 2, "Logging requirements are established and maintained for IT and OT assets that are important to the delivery of the function and assets within the function that may be leveraged to achieve a threat objective"),
            ("d", 2, "Logging requirements are established and maintained for network and host monitoring infrastructure (for example, web gateways, endpoint detection and response software, intrusion detection and prevention systems)"),
            ("e", 2, "Log data are being aggregated within the function"),
            ("f", 3, "More rigorous logging is performed for higher priority assets"),
        ],
    ),
    (
        2,
        "Perform Monitoring",
        [
            ("a", 1, "Periodic reviews of log data or other cybersecurity monitoring activities are performed, at least in an ad hoc manner"),
            ("b", 1, "Data and alerts from network and host monitoring infrastructure assets are periodically reviewed, at least in an ad hoc manner"),
            ("c", 2, "Monitoring and analysis requirements are established and maintained for the function and address timely review of event data"),
            ("d", 2, "Indicators of anomalous activity are established and maintained based on system logs, data flows, network baselines, cybersecurity events, and architecture and are monitored across the IT and OT environments"),
            ("e", 2, "Alarms and alerts are configured and maintained to support the identification of cybersecurity events"),
            ("f", 2, "Monitoring activities are aligned with the threat profile (THREAT-2e)"),
            ("g", 3, "More rigorous monitoring is performed for higher priority assets"),
            ("h", 3, "Risk analysis information (RISK-3d) is used to identify indicators of anomalous activity"),
            ("i", 3, "Indicators of anomalous activity are evaluated and updated periodically and according to defined triggers, such as system changes and external events"),
        ],
    ),
    (
        3,
        "Establish and Maintain Situational Awareness",
        [
            ("a", 2, "Methods of communicating the current state of cybersecurity for the function are established and maintained"),
            ("b", 2, "Monitoring data are aggregated to provide an understanding of the operational state of the function"),
            ("c", 2, "Relevant information from across the organization is available to enhance situational awareness"),
            ("d", 3, "Situational awareness reporting requirements have been defined and address timely dissemination of cybersecurity information to organization-defined stakeholders"),
            ("e", 3, "Relevant information from outside the organization is collected and made available across the organization to enhance situational awareness"),
            ("f", 3, "A capability is established and maintained to aggregate, correlate, and analyze the outputs of cybersecurity monitoring activities and provide a near-real-time understanding of the cybersecurity state of the function"),
            ("g", 3, "Predefined states of operation are documented and can be implemented based on the cybersecurity state of the function or when triggered by activities in other domains"),
        ],
    ),
    (
        4,
        "Management Activities for the SITUATION domain",
        [
            ("a", 2, "Documented procedures are established, followed, and maintained for activities in the SITUATION domain"),
            ("b", 2, "Adequate resources (people, funding, and tools) are provided to support activities in the SITUATION domain"),
            ("c", 3, "Up-to-date policies or other organizational directives define requirements for activities in the SITUATION domain"),
            ("d", 3, "Responsibility, accountability, and authority for the performance of activities in the SITUATION domain are assigned to personnel"),
            ("e", 3, "Personnel performing activities in the SITUATION domain have the skills and knowledge needed to perform their assigned responsibilities"),
            ("f", 3, "The effectiveness of activities in the SITUATION domain is evaluated and tracked"),
        ],
    ),
]

RESPONSE_OBJECTIVES = [
    (
        1,
        "Detect Cybersecurity Events",
        [
            ("a", 1, "Detected cybersecurity events are reported to a specified person or role and documented, at least in an ad hoc manner"),
            ("b", 2, "Criteria are established for cybersecurity event detection (for example, what constitutes a cybersecurity event, where to look for cybersecurity events)"),
            ("c", 2, "Cybersecurity events are documented based on the established criteria"),
            ("d", 3, "Event information is correlated to support incident analysis by identifying patterns, trends, and other common features"),
            ("e", 3, "Cybersecurity event detection activities are adjusted based on identified risks and the organization's threat profile (THREAT-2e)"),
            ("f", 3, "Situational awareness for the function is monitored to support the identification of cybersecurity events"),
        ],
    ),
    (
        2,
        "Analyze Cybersecurity Events and Declare Incidents",
        [
            ("a", 1, "Criteria for declaring cybersecurity incidents are established, at least in an ad hoc manner"),
            ("b", 1, "Cybersecurity events are analyzed to support the declaration of cybersecurity incidents, at least in an ad hoc manner"),
            ("c", 2, "Cybersecurity incident declaration criteria are formally established based on potential impact to the function"),
            ("d", 2, "Cybersecurity events are declared to be incidents based on established criteria"),
            ("e", 2, "Cybersecurity incident declaration criteria are updated periodically and according to defined triggers, such as organizational changes, lessons learned from plan execution, or newly identified threats"),
            ("f", 2, "There is a repository where cybersecurity events and incidents are documented and tracked to closure"),
            ("g", 2, "Internal and external stakeholders (for example, executives, attorneys, government agencies, connected organizations, vendors, sector organizations, regulators) are identified and notified of incidents based on situational awareness reporting requirements (SITUATION-3d)"),
            ("h", 3, "Criteria for cybersecurity incident declaration are aligned with cyber risk prioritization criteria (RISK-3b)"),
            ("i", 3, "Cybersecurity incidents are correlated to identify patterns, trends, and other common features across multiple incidents"),
        ],
    ),
    (
        3,
        "Respond to Cybersecurity Incidents",
        [
            ("a", 1, "Cybersecurity incident response personnel are identified, and roles are assigned, at least in an ad hoc manner"),
            ("b", 1, "Responses to cybersecurity incidents are executed, at least in an ad hoc manner, to limit impact to the function and restore normal operations"),
            ("c", 1, "Reporting of incidents is performed (for example, internal reporting, ICS-CERT, relevant ISACs), at least in an ad hoc manner"),
            ("d", 2, "Cybersecurity incident response plans that address all phases of the incident lifecycle are established and maintained"),
            ("e", 2, "Cybersecurity incident response is executed according to defined plans and procedures"),
            ("f", 2, "Cybersecurity incident response plans include a communications plan for internal and external stakeholders"),
            ("g", 2, "Cybersecurity incident response plan exercises are conducted periodically and according to defined triggers, such as system changes and external events"),
            ("h", 2, "Cybersecurity incident lessons-learned activities are performed and corrective actions are taken, including updates to the incident response plan"),
            ("i", 3, "Cybersecurity incident root-cause analysis is performed and corrective actions are taken, including updates to the incident response plan"),
            ("j", 3, "Cybersecurity incident responses are coordinated with vendors, law enforcement, and other external entities as appropriate, including support for evidence collection and preservation"),
            ("k", 3, "Cybersecurity incident response personnel participate in joint cybersecurity exercises with other organizations"),
            ("l", 3, "Cybersecurity incident responses leverage and trigger predefined states of operation (SITUATION-3g)"),
        ],
    ),
    (
        4,
        "Address Cybersecurity in Continuity of Operations",
        [
            ("a", 1, "Continuity plans are developed to sustain and restore operation of the function if a cybersecurity event or incident occurs, at least in an ad hoc manner"),
            ("b", 1, "Data backups are available and tested, at least in an ad hoc manner"),
            ("c", 1, "IT and OT assets requiring spares are identified, at least in an ad hoc manner"),
            ("d", 2, "Continuity plans address potential impacts from cybersecurity incidents"),
            ("e", 2, "The assets and activities necessary to sustain minimum operations of the function are identified and documented in continuity plans"),
            ("f", 2, "Continuity plans address IT, OT, and information assets that are important to the delivery of the function, including the availability of backup data and replacement, redundant, and spare IT and OT assets"),
            ("g", 2, "Recovery time objectives (RTOs) and recovery point objectives (RPOs) for assets that are important to the delivery of the function are incorporated into continuity plans"),
            ("h", 2, "Cybersecurity incident criteria that trigger the execution of continuity plans are established and communicated to incident response and continuity management personnel"),
            ("i", 2, "Continuity plans are tested through evaluations and exercises periodically and according to defined triggers, such as system changes and external events"),
            ("j", 2, "Cybersecurity controls protecting backup data are equivalent to or more rigorous than controls protecting source data"),
            ("k", 2, "Data backups are logically or physically separated from source data"),
            ("l", 2, "Spares for selected IT and OT assets are available"),
            # MIL3 label dropped in extraction here - cross-checked against a
            # secondary published summary of C2M2 v2.1 RESPONSE-4 before
            # transcribing m-p as MIL3 (see the module docstring note above).
            ("m", 3, "Continuity plans are aligned with identified risks and the organization's threat profile (THREAT-2e) to ensure coverage of identified risk categories and threats"),
            ("n", 3, "Continuity plan exercises address higher priority risks"),
            ("o", 3, "The results of continuity plan testing or activation are compared to recovery objectives, and plans are improved accordingly"),
            ("p", 3, "Continuity plans are periodically reviewed and updated"),
        ],
    ),
    (
        5,
        "Management Activities for the RESPONSE domain",
        [
            ("a", 2, "Documented procedures are established, followed, and maintained for activities in the RESPONSE domain"),
            ("b", 2, "Adequate resources (people, funding, and tools) are provided to support activities in the RESPONSE domain"),
            ("c", 3, "Up-to-date policies or other organizational directives define requirements for activities in the RESPONSE domain"),
            ("d", 3, "Responsibility, accountability, and authority for the performance of activities in the RESPONSE domain are assigned to personnel"),
            ("e", 3, "Personnel performing activities in the RESPONSE domain have the skills and knowledge needed to perform their assigned responsibilities"),
            ("f", 3, "The effectiveness of activities in the RESPONSE domain is evaluated and tracked"),
        ],
    ),
]

THIRD_PARTIES_OBJECTIVES = [
    (
        1,
        "Identify and Prioritize Third Parties",
        [
            ("a", 1, "Important IT and OT third-party dependencies are identified (that is, internal and external parties on which the delivery of the function depends, including operating partners), at least in an ad hoc manner"),
            ("b", 1, "Third parties that have access to, control of, or custody of any IT, OT, or information assets that are important to the delivery of the function are identified, at least in an ad hoc manner"),
            ("c", 2, "A defined method is followed to identify risks arising from suppliers and other third parties"),
            ("d", 2, "Third parties are prioritized according to established criteria (for example, importance to the delivery of the function, impact of a compromise or disruption, ability to negotiate cybersecurity requirements within contracts)"),
            ("e", 2, "Escalated prioritization is assigned to suppliers and other third parties whose compromise or disruption could cause significant consequences (for example, single-source suppliers, suppliers with privileged access)"),
            ("f", 3, "Prioritization of suppliers and other third parties is updated periodically and according to defined triggers, such as system changes and external events"),
        ],
    ),
    (
        2,
        "Manage Third-Party Risk",
        [
            ("a", 1, "The selection of suppliers and other third parties includes consideration of their cybersecurity qualifications, at least in an ad hoc manner"),
            ("b", 1, "The selection of products and services includes consideration of their cybersecurity capabilities, at least in an ad hoc manner"),
            ("c", 2, "A defined method is followed to identify cybersecurity requirements and implement associated controls that protect against the risks arising from suppliers and other third parties"),
            ("d", 2, "A defined method is followed to evaluate and select suppliers and other third parties"),
            ("e", 2, "More rigorous cybersecurity controls are implemented for higher priority suppliers and other third parties"),
            ("f", 2, "Cybersecurity requirements (for example, vulnerability notification, incident-related SLA requirements) are formalized in agreements with suppliers and other third parties"),
            ("g", 2, "Suppliers and other third parties periodically attest to their ability to meet cybersecurity requirements"),
            ("h", 3, "Cybersecurity requirements for suppliers and other third parties include secure software and secure product development requirements where appropriate"),
            ("i", 3, "Selection criteria for products include consideration of end-of-life and end-of-support timelines"),
            ("j", 3, "Selection criteria include consideration of safeguards against counterfeit or compromised software, hardware, and services"),
            ("k", 3, "Selection criteria for higher priority assets include evaluation of bills of material for key asset elements, such as hardware and software"),
            ("l", 3, "Selection criteria for higher priority assets include evaluation of any associated third-party hosting environments and source data"),
            ("m", 3, "Acceptance testing of procured assets includes consideration of cybersecurity requirements"),
        ],
    ),
    (
        3,
        "Management Activities for the THIRD-PARTIES domain",
        [
            ("a", 2, "Documented procedures are established, followed, and maintained for activities in the THIRD-PARTIES domain"),
            ("b", 2, "Adequate resources (people, funding, and tools) are provided to support activities in the THIRD-PARTIES domain"),
            ("c", 3, "Up-to-date policies or other organizational directives define requirements for activities in the THIRD-PARTIES domain"),
            ("d", 3, "Responsibility, accountability, and authority for the performance of activities in the THIRD-PARTIES domain are assigned to personnel"),
            ("e", 3, "Personnel performing activities in the THIRD-PARTIES domain have the skills and knowledge needed to perform their assigned responsibilities"),
            ("f", 3, "The effectiveness of activities in the THIRD-PARTIES domain is evaluated and tracked"),
        ],
    ),
]

WORKFORCE_OBJECTIVES = [
    (
        1,
        "Implement Workforce Controls",
        [
            ("a", 1, "Personnel vetting (for example, background checks, drug tests) is performed at hire, at least in an ad hoc manner"),
            ("b", 1, "Personnel separation procedures address cybersecurity, at least in an ad hoc manner"),
            ("c", 2, "Personnel vetting is performed at hire and periodically for positions that have access to assets that are important to the delivery of the function"),
            ("d", 2, "Personnel separation and transfer procedures address cybersecurity, including supplementary vetting as appropriate"),
            ("e", 2, "Personnel are made aware of their responsibilities for protection and acceptable use of IT, OT, and information assets"),
            ("f", 3, "Vetting is performed for all positions (including employees, vendors, and contractors) at a level commensurate with position risk"),
            ("g", 3, "A formal accountability process that includes disciplinary actions is implemented for personnel who fail to comply with established security policies and procedures"),
        ],
    ),
    (
        2,
        "Increase Cybersecurity Awareness",
        [
            ("a", 1, "Cybersecurity awareness activities occur, at least in an ad hoc manner"),
            ("b", 2, "Cybersecurity awareness objectives are established and maintained"),
            ("c", 2, "Cybersecurity awareness objectives are aligned with the defined threat profile (THREAT-2e)"),
            ("d", 2, "Cybersecurity awareness activities are conducted periodically"),
            ("e", 3, "Cybersecurity awareness activities are tailored to job role"),
            ("f", 3, "Cybersecurity awareness activities address predefined states of operation (SITUATION-3g)"),
            ("g", 3, "The effectiveness of cybersecurity awareness activities is evaluated periodically and according to defined triggers, such as system changes and external events, and improvements are made as appropriate"),
        ],
    ),
    (
        3,
        "Assign Cybersecurity Responsibilities",
        [
            ("a", 1, "Cybersecurity responsibilities for the function are identified, at least in an ad hoc manner"),
            ("b", 1, "Cybersecurity responsibilities are assigned to specific people, at least in an ad hoc manner"),
            ("c", 2, "Cybersecurity responsibilities are assigned to specific roles, including external service providers"),
            ("d", 2, "Cybersecurity responsibilities are documented"),
            ("e", 3, "Cybersecurity responsibilities and job requirements are reviewed and updated periodically and according to defined triggers, such as system changes and changes to organizational structure"),
            ("f", 3, "Assigned cybersecurity responsibilities are managed to ensure adequacy and redundancy of coverage, including succession planning"),
        ],
    ),
    (
        4,
        "Develop Cybersecurity Workforce",
        [
            ("a", 1, "Cybersecurity training is made available to personnel with assigned cybersecurity responsibilities, at least in an ad hoc manner"),
            ("b", 1, "Cybersecurity knowledge, skill, and ability requirements and gaps are identified for both current and future operational needs, at least in an ad hoc manner"),
            ("c", 2, "Identified cybersecurity knowledge, skill, and ability gaps are addressed through training, recruiting, and retention efforts"),
            ("d", 2, "Cybersecurity training is provided as a prerequisite to granting access to assets that are important to the delivery of the function"),
            ("e", 3, "The effectiveness of training programs is evaluated periodically, and improvements are made as appropriate"),
            ("f", 3, "Training programs include continuing education and professional development opportunities for personnel with significant cybersecurity responsibilities"),
        ],
    ),
    (
        5,
        "Management Activities for the WORKFORCE domain",
        [
            ("a", 2, "Documented procedures are established, followed, and maintained for activities in the WORKFORCE domain"),
            ("b", 2, "Adequate resources (people, funding, and tools) are provided to support activities in the WORKFORCE domain"),
            ("c", 3, "Up-to-date policies or other organizational directives define requirements for activities in the WORKFORCE domain"),
            ("d", 3, "Responsibility, accountability, and authority for the performance of activities in the WORKFORCE domain are assigned to personnel"),
            ("e", 3, "Personnel performing activities in the WORKFORCE domain have the skills and knowledge needed to perform their assigned responsibilities"),
            ("f", 3, "The effectiveness of activities in the WORKFORCE domain is evaluated and tracked"),
        ],
    ),
]

ARCHITECTURE_OBJECTIVES = [
    (
        1,
        "Establish and Maintain Cybersecurity Architecture Strategy and Program",
        [
            ("a", 1, "The organization has a strategy for cybersecurity architecture, which may be developed and managed in an ad hoc manner"),
            ("b", 2, "A strategy for cybersecurity architecture is established and maintained in alignment with the organization's cybersecurity program strategy (PROGRAM-1b) and enterprise architecture"),
            ("c", 2, "A documented cybersecurity architecture is established and maintained that includes IT and OT systems and networks and aligns with system and asset categorization and prioritization"),
            ("d", 2, "Governance for cybersecurity architecture (such as an architecture review process) is established and maintained that includes provisions for periodic architectural reviews and an exceptions process"),
            ("e", 2, "Senior management sponsorship for the cybersecurity architecture program is visible and active"),
            ("f", 2, "The cybersecurity architecture establishes and maintains cybersecurity requirements for the organization's assets"),
            ("g", 2, "Cybersecurity controls are selected and implemented to meet cybersecurity requirements"),
            ("h", 3, "The cybersecurity architecture strategy and program are aligned with the organization's enterprise architecture strategy and program"),
            ("i", 3, "Conformance of the organization's systems and networks to the cybersecurity architecture is evaluated periodically and according to defined triggers, such as system changes and external events"),
            ("j", 3, "The cybersecurity architecture is guided by the organization's risk analysis information (RISK-3d) and threat profile (THREAT-2e)"),
            ("k", 3, "The cybersecurity architecture addresses predefined states of operation (SITUATION-3g)"),
        ],
    ),
    (
        2,
        "Implement Network Protections as an Element of the Cybersecurity Architecture",
        [
            ("a", 1, "Network protections are implemented, at least in an ad hoc manner"),
            ("b", 1, "The organization's IT systems are separated from OT systems through segmentation, either through physical means or logical means, at least in an ad hoc manner"),
            ("c", 2, "Network protections are defined and enforced for selected asset types according to asset risk and priority (for example, internal assets, perimeter assets, assets connected to the organization's Wi-Fi, cloud assets, remote access, and externally owned devices)"),
            ("d", 2, "Assets that are important to the delivery of the function are logically or physically segmented into distinct security zones based on asset cybersecurity requirements"),
            ("e", 2, "Network protections incorporate the principles of least privilege and least functionality"),
            ("f", 2, "Network protections include monitoring, analysis, and control of network traffic for selected security zones (for example, firewalls, allowlisting, intrusion detection and prevention systems (IDPS))"),
            ("g", 2, "Web traffic and email are monitored, analyzed, and controlled (for example, malicious link blocking, suspicious download blocking, email authentication techniques, IP address blocking)"),
            # MIL3 label dropped in extraction here - cross-checked against a
            # secondary published summary of C2M2 v2.1 ARCHITECTURE-2 before
            # transcribing h-l as MIL3.
            ("h", 3, "All assets are segmented into distinct security zones based on cybersecurity requirements"),
            ("i", 3, "Separate networks are implemented, where warranted, that logically or physically segment assets into security zones with independent authentication"),
            ("j", 3, "OT systems are operationally independent from IT systems so that OT operations can be sustained during an outage of IT systems"),
            ("k", 3, "Device connections to the network are controlled to ensure that only authorized devices can connect (for example, network access control (NAC))"),
            ("l", 3, "The cybersecurity architecture enables the isolation of compromised assets"),
        ],
    ),
    (
        3,
        "Implement IT and OT Asset Security as an Element of the Cybersecurity Architecture",
        [
            ("a", 1, "Logical and physical access controls are implemented to protect assets that are important to the delivery of the function, where feasible, at least in an ad hoc manner"),
            ("b", 1, "Endpoint protections (such as secure configuration, security applications, and host monitoring) are implemented to protect assets that are important to the delivery of the function, where feasible, at least in an ad hoc manner"),
            ("c", 2, "The principle of least privilege (for example, limiting administrative access for users and service accounts) is enforced"),
            ("d", 2, "The principle of least functionality (for example, limiting services, limiting applications, limiting ports, limiting connected devices) is enforced"),
            ("e", 2, "Secure configurations are established and maintained as part of the asset deployment process where feasible"),
            ("f", 2, "Security applications are required as an element of device configuration where feasible (for example, endpoint detection and response, host-based firewalls)"),
            ("g", 2, "The use of removeable media is controlled (for example, limiting the use of USB devices, managing external hard drives)"),
            ("h", 2, "Cybersecurity controls are implemented for all assets within the function either at the asset level or as compensating controls where asset-level controls are not feasible"),
            ("i", 2, "Maintenance and capacity management activities are performed for all assets within the function"),
            ("j", 2, "The physical operating environment is controlled to protect the operation of assets within the function"),
            ("k", 2, "More rigorous cybersecurity controls are implemented for higher priority assets"),
            ("l", 3, "Configuration of and changes to firmware are controlled throughout the asset lifecycle"),
            ("m", 3, "Controls (such as allowlists, blocklists, and configuration settings) are implemented to prevent the execution of unauthorized code"),
        ],
    ),
    (
        4,
        "Implement Software Security as an Element of the Cybersecurity Architecture",
        [
            ("a", 2, "Software developed in-house for deployment on higher priority assets is developed using secure software development practices"),
            ("b", 2, "The selection of procured software for deployment on higher priority assets includes consideration of the vendor's secure software development practices"),
            ("c", 2, "Secure software configurations are required as part of the software deployment process for both procured software and software developed in-house"),
            ("d", 3, "All software developed in-house is developed using secure software development practices"),
            ("e", 3, "The selection of all procured software includes consideration of the vendor's secure software development practices"),
            ("f", 3, "The architecture review process evaluates the security of new and revised applications prior to deployment"),
            ("g", 3, "The authenticity of all software and firmware is validated prior to deployment"),
            ("h", 3, "Security testing (for example, static testing, dynamic testing, fuzz testing, penetration testing) is performed for in-house-developed and in-house-tailored applications periodically and according to defined triggers, such as system changes and external events"),
        ],
    ),
    (
        5,
        "Implement Data Security as an Element of the Cybersecurity Architecture",
        [
            ("a", 1, "Sensitive data is protected at rest, at least in an ad hoc manner"),
            ("b", 2, "All data at rest is protected for selected data categories"),
            ("c", 2, "All data in transit is protected for selected data categories"),
            ("d", 2, "Cryptographic controls are implemented for data at rest and data in transit for selected data categories"),
            ("e", 2, "Key management infrastructure (that is, key generation, key storage, key destruction, key update, and key revocation) is implemented to support cryptographic controls"),
            ("f", 2, "Controls to restrict the exfiltration of data (for example, data loss prevention tools) are implemented"),
            ("g", 3, "The cybersecurity architecture includes protections (such as full disk encryption) for data that is stored on assets that may be lost or stolen"),
            ("h", 3, "The cybersecurity architecture includes protections against unauthorized changes to software, firmware, and data"),
        ],
    ),
    (
        6,
        "Management Activities for the ARCHITECTURE domain",
        [
            ("a", 2, "Documented procedures are established, followed, and maintained for activities in the ARCHITECTURE domain"),
            ("b", 2, "Adequate resources (people, funding, and tools) are provided to support activities in the ARCHITECTURE domain"),
            # MIL3 label dropped in extraction here - matches the identical,
            # already-verified MIL2=a,b / MIL3=c,d,e,f pattern every other
            # domain's Management Activities objective uses (ASSET/ACCESS
            # included), so no separate secondary-source cross-check was
            # needed for this one.
            ("c", 3, "Up-to-date policies or other organizational directives define requirements for activities in the ARCHITECTURE domain"),
            ("d", 3, "Responsibility, accountability, and authority for the performance of activities in the ARCHITECTURE domain are assigned to personnel"),
            ("e", 3, "Personnel performing activities in the ARCHITECTURE domain have the skills and knowledge needed to perform their assigned responsibilities"),
            ("f", 3, "The effectiveness of activities in the ARCHITECTURE domain is evaluated and tracked"),
        ],
    ),
]

PROGRAM_OBJECTIVES = [
    (
        1,
        "Establish Cybersecurity Program Strategy",
        [
            ("a", 1, "The organization has a cybersecurity program strategy, which may be developed and managed in an ad hoc manner"),
            ("b", 2, "The cybersecurity program strategy defines goals and objectives for the organization's cybersecurity activities"),
            ("c", 2, "The cybersecurity program strategy and priorities are documented and aligned with the organization's mission, strategic objectives, and risk to critical infrastructure"),
            ("d", 2, "The cybersecurity program strategy defines the organization's approach to provide program oversight and governance for cybersecurity activities"),
            ("e", 2, "The cybersecurity program strategy defines the structure and organization of the cybersecurity program"),
            ("f", 2, "The cybersecurity program strategy identifies standards and guidelines intended to be followed by the program"),
            ("g", 2, "The cybersecurity program strategy identifies any applicable compliance requirements that must be satisfied by the program (for example, NERC CIP, TSA Pipeline Security Guidelines, PCI DSS, ISO, DoD CMMC)"),
            ("h", 3, "The cybersecurity program strategy is updated periodically and according to defined triggers, such as business changes, changes in the operating environment, and changes in the threat profile (THREAT-2e)"),
        ],
    ),
    (
        2,
        "Establish and Maintain Cybersecurity Program",
        [
            ("a", 1, "Senior management with proper authority provides support for the cybersecurity program, at least in an ad hoc manner"),
            ("b", 2, "The cybersecurity program is established according to the cybersecurity program strategy"),
            ("c", 2, "Senior management sponsorship for the cybersecurity program is visible and active"),
            ("d", 2, "Senior management sponsorship is provided for the development, maintenance, and enforcement of cybersecurity policies"),
            ("e", 2, "Responsibility for the cybersecurity program is assigned to a role with sufficient authority"),
            ("f", 2, "Stakeholders for cybersecurity program management activities are identified and involved"),
            ("g", 3, "Cybersecurity program activities are periodically reviewed to ensure that they align with the cybersecurity program strategy"),
            ("h", 3, "Cybersecurity activities are independently reviewed to ensure conformance with cybersecurity policies and procedures, periodically and according to defined triggers, such as process changes"),
            ("i", 3, "The cybersecurity program addresses and enables the achievement of legal and regulatory compliance, as appropriate"),
            ("j", 3, "The organization collaborates with external entities to contribute to the development and implementation of cybersecurity standards, guidelines, leading practices, lessons learned, and emerging technologies"),
        ],
    ),
    (
        3,
        "Management Activities for the PROGRAM domain",
        [
            ("a", 2, "Documented procedures are established, followed, and maintained for activities in the PROGRAM domain"),
            ("b", 2, "Adequate resources (people, funding, and tools) are provided to support activities in the PROGRAM domain"),
            ("c", 3, "Up-to-date policies or other organizational directives define requirements for activities in the PROGRAM domain"),
            ("d", 3, "Responsibility, accountability, and authority for the performance of activities in the PROGRAM domain are assigned to personnel"),
            ("e", 3, "Personnel performing activities in the PROGRAM domain have the skills and knowledge needed to perform their assigned responsibilities"),
            ("f", 3, "The effectiveness of activities in the PROGRAM domain is evaluated and tracked"),
        ],
    ),
]

POPULATED_OBJECTIVES = {
    "ASSET": ASSET_OBJECTIVES,
    "THREAT": THREAT_OBJECTIVES,
    "RISK": RISK_OBJECTIVES,
    "ACCESS": ACCESS_OBJECTIVES,
    "SITUATION": SITUATION_OBJECTIVES,
    "RESPONSE": RESPONSE_OBJECTIVES,
    "THIRD-PARTIES": THIRD_PARTIES_OBJECTIVES,
    "WORKFORCE": WORKFORCE_OBJECTIVES,
    "ARCHITECTURE": ARCHITECTURE_OBJECTIVES,
    "PROGRAM": PROGRAM_OBJECTIVES,
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
