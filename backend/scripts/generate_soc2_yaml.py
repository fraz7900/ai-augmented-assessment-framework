"""Generates framework_mapping/soc2_tsc.yaml (ADR-0026).

Like ISO 27001 (ADR-0024) — and unlike CIS Controls v8 (ADR-0025) — this
framework's real source text is copyrighted, all-rights-reserved content,
not freely licensed for reproduction. Confirmed directly: the AICPA's own
copyright page states permission is required to reproduce/redistribute
AICPA content, and the source PDF's own final page states "(c) 2020
Association of International Certified Professional Accountants. All
rights reserved." This is true even though (unlike ISO 27001) the
document itself is freely downloadable at no cost — "free to download"
and "licensed for reproduction" are different questions, and only the
second one determines this project's transcription scope.

Given that, this framework gets ISO 27001's titles-only-equivalent
treatment, adapted to how the AICPA Trust Services Criteria (TSC) is
actually structured: each criterion's own one-sentence (or occasionally
two-to-three-sentence) STATEMENT is transcribed verbatim (this is the
shortest real, meaningfully-identifying unit — the same role a title
plays for ISO 27001 controls, and the unit every third-party SOC 2
mapping tool and blog post reproduces as "the criterion"). The much
longer "points of focus" that follow every criterion in the real
document (illustrative bullet lists, often 5-15 per criterion) are
deliberately NOT transcribed — that is the substantial, clearly
copyrightable elaboration, the same kind of content ISO 27001's full
"shall" requirement text is for Annex A.

Source, verified directly (not assumed, and not reconstructed from
training-data memory): fetched the real "2017 Trust Services Criteria for
Security, Availability, Processing Integrity, Confidentiality, and
Privacy" PDF (includes the March 2020 update), confirmed via `pypdf` to
be genuine AICPA content (real "TSP Section 100" branding, the exact
copyright notice quoted above, 63 real pages). The AICPA's own official
download page (requiring free registration) additionally offers a
"With Revised Points of Focus - 2022" edition; per the AICPA's own
public statements, the 2022 revision touched ONLY the points of focus,
not the criteria statements themselves — since this transcription
excludes points of focus entirely, the criteria text below is accurate
regardless of which points-of-focus edition it came from.
"""

from __future__ import annotations

from pathlib import Path

import yaml

# Applicability values, verified from the source document's own "Trust
# Services Category / Common Criteria / Additional Category-Specific
# Criteria" table (TSP Section 100, para. .07): Common Criteria (CC
# series) are required in every SOC 2 report regardless of which trust
# services categories are in scope; each other category's criteria are
# required only when that specific category is included in the
# engagement.
COMMON_CRITERIA_APPLICABILITY = "Required in every SOC 2 report (Common Criteria / Security baseline)"


def _additional_applicability(category: str) -> str:
    return f"Required only when {category} is included in the engagement's scope"


# (short_code, full_name, purpose, [(objective_number, objective_title, [(id, statement), ...])])
CATEGORIES: list[tuple[str, str, str, list[tuple[int, str, list[tuple[str, str]]]], str]] = [
    (
        "CC",
        "Security",
        (
            "Information and systems are protected against unauthorized access, unauthorized "
            "disclosure of information, and damage to systems that could compromise the "
            "availability, integrity, confidentiality, and privacy of information or systems and "
            "affect the entity's ability to achieve its objectives."
        ),
        [
            (
                1,
                "Control Environment",
                [
                    ("CC1.1", "COSO Principle 1: The entity demonstrates a commitment to integrity and ethical values."),
                    ("CC1.2", "COSO Principle 2: The board of directors demonstrates independence from management and exercises oversight of the development and performance of internal control."),
                    ("CC1.3", "COSO Principle 3: Management establishes, with board oversight, structures, reporting lines, and appropriate authorities and responsibilities in the pursuit of objectives."),
                    ("CC1.4", "COSO Principle 4: The entity demonstrates a commitment to attract, develop, and retain competent individuals in alignment with objectives."),
                    ("CC1.5", "COSO Principle 5: The entity holds individuals accountable for their internal control responsibilities in the pursuit of objectives."),
                ],
            ),
            (
                2,
                "Communication and Information",
                [
                    ("CC2.1", "COSO Principle 13: The entity obtains or generates and uses relevant, quality information to support the functioning of internal control."),
                    ("CC2.2", "COSO Principle 14: The entity internally communicates information, including objectives and responsibilities for internal control, necessary to support the functioning of internal control."),
                    ("CC2.3", "COSO Principle 15: The entity communicates with external parties regarding matters affecting the functioning of internal control."),
                ],
            ),
            (
                3,
                "Risk Assessment",
                [
                    ("CC3.1", "COSO Principle 6: The entity specifies objectives with sufficient clarity to enable the identification and assessment of risks relating to objectives."),
                    ("CC3.2", "COSO Principle 7: The entity identifies risks to the achievement of its objectives across the entity and analyzes risks as a basis for determining how the risks should be managed."),
                    ("CC3.3", "COSO Principle 8: The entity considers the potential for fraud in assessing risks to the achievement of objectives."),
                    ("CC3.4", "COSO Principle 9: The entity identifies and assesses changes that could significantly impact the system of internal control."),
                ],
            ),
            (
                4,
                "Monitoring Activities",
                [
                    ("CC4.1", "COSO Principle 16: The entity selects, develops, and performs ongoing and/or separate evaluations to ascertain whether the components of internal control are present and functioning."),
                    ("CC4.2", "COSO Principle 17: The entity evaluates and communicates internal control deficiencies in a timely manner to those parties responsible for taking corrective action, including senior management and the board of directors, as appropriate."),
                ],
            ),
            (
                5,
                "Control Activities",
                [
                    ("CC5.1", "COSO Principle 10: The entity selects and develops control activities that contribute to the mitigation of risks to the achievement of objectives to acceptable levels."),
                    ("CC5.2", "COSO Principle 11: The entity also selects and develops general control activities over technology to support the achievement of objectives."),
                    ("CC5.3", "COSO Principle 12: The entity deploys control activities through policies that establish what is expected and in procedures that put policies into action."),
                ],
            ),
            (
                6,
                "Logical and Physical Access Controls",
                [
                    ("CC6.1", "The entity implements logical access security software, infrastructure, and architectures over protected information assets to protect them from security events to meet the entity's objectives."),
                    ("CC6.2", "Prior to issuing system credentials and granting system access, the entity registers and authorizes new internal and external users whose access is administered by the entity. For those users whose access is administered by the entity, user system credentials are removed when user access is no longer authorized."),
                    ("CC6.3", "The entity authorizes, modifies, or removes access to data, software, functions, and other protected information assets based on roles, responsibilities, or the system design and changes, giving consideration to the concepts of least privilege and segregation of duties, to meet the entity's objectives."),
                    ("CC6.4", "The entity restricts physical access to facilities and protected information assets (for example, data center facilities, backup media storage, and other sensitive locations) to authorized personnel to meet the entity's objectives."),
                    ("CC6.5", "The entity discontinues logical and physical protections over physical assets only after the ability to read or recover data and software from those assets has been diminished and is no longer required to meet the entity's objectives."),
                    ("CC6.6", "The entity implements logical access security measures to protect against threats from sources outside its system boundaries."),
                    ("CC6.7", "The entity restricts the transmission, movement, and removal of information to authorized internal and external users and processes, and protects it during transmission, movement, or removal to meet the entity's objectives."),
                    ("CC6.8", "The entity implements controls to prevent or detect and act upon the introduction of unauthorized or malicious software to meet the entity's objectives."),
                ],
            ),
            (
                7,
                "System Operations",
                [
                    ("CC7.1", "To meet its objectives, the entity uses detection and monitoring procedures to identify (1) changes to configurations that result in the introduction of new vulnerabilities, and (2) susceptibilities to newly discovered vulnerabilities."),
                    ("CC7.2", "The entity monitors system components and the operation of those components for anomalies that are indicative of malicious acts, natural disasters, and errors affecting the entity's ability to meet its objectives; anomalies are analyzed to determine whether they represent security events."),
                    ("CC7.3", "The entity evaluates security events to determine whether they could or have resulted in a failure of the entity to meet its objectives (security incidents) and, if so, takes actions to prevent or address such failures."),
                    ("CC7.4", "The entity responds to identified security incidents by executing a defined incident-response program to understand, contain, remediate, and communicate security incidents, as appropriate."),
                    ("CC7.5", "The entity identifies, develops, and implements activities to recover from identified security incidents."),
                ],
            ),
            (
                8,
                "Change Management",
                [
                    ("CC8.1", "The entity authorizes, designs, develops or acquires, configures, documents, tests, approves, and implements changes to infrastructure, data, software, and procedures to meet its objectives."),
                ],
            ),
            (
                9,
                "Risk Mitigation",
                [
                    ("CC9.1", "The entity identifies, selects, and develops risk mitigation activities for risks arising from potential business disruptions."),
                    ("CC9.2", "The entity assesses and manages risks associated with vendors and business partners."),
                ],
            ),
        ],
        COMMON_CRITERIA_APPLICABILITY,
    ),
    (
        "A",
        "Availability",
        "Information and systems are available for operation and use to meet the entity's objectives.",
        [
            (
                1,
                "Additional Criteria for Availability",
                [
                    ("A1.1", "The entity maintains, monitors, and evaluates current processing capacity and use of system components (infrastructure, data, and software) to manage capacity demand and to enable the implementation of additional capacity to help meet its objectives."),
                    ("A1.2", "The entity authorizes, designs, develops or acquires, implements, operates, approves, maintains, and monitors environmental protections, software, data backup processes, and recovery infrastructure to meet its objectives."),
                    ("A1.3", "The entity tests recovery plan procedures supporting system recovery to meet its objectives."),
                ],
            ),
        ],
        "Availability",
    ),
    (
        "C",
        "Confidentiality",
        "Information designated as confidential is protected to meet the entity's objectives.",
        [
            (
                1,
                "Additional Criteria for Confidentiality",
                [
                    ("C1.1", "The entity identifies and maintains confidential information to meet the entity's objectives related to confidentiality."),
                    ("C1.2", "The entity disposes of confidential information to meet the entity's objectives related to confidentiality."),
                ],
            ),
        ],
        "Confidentiality",
    ),
    (
        "PI",
        "Processing Integrity",
        (
            "System processing is complete, valid, accurate, timely, and authorized to meet the "
            "entity's objectives (over the provision of services or the production, manufacturing, "
            "or distribution of goods)."
        ),
        [
            (
                1,
                "Additional Criteria for Processing Integrity",
                [
                    ("PI1.1", "The entity obtains or generates, uses, and communicates relevant, quality information regarding the objectives related to processing, including definitions of data processed and product and service specifications, to support the use of products and services."),
                    ("PI1.2", "The entity implements policies and procedures over system inputs, including controls over completeness and accuracy, to result in products, services, and reporting to meet the entity's objectives."),
                    ("PI1.3", "The entity implements policies and procedures over system processing to result in products, services, and reporting to meet the entity's objectives."),
                    ("PI1.4", "The entity implements policies and procedures to make available or deliver output completely, accurately, and timely in accordance with specifications to meet the entity's objectives."),
                    ("PI1.5", "The entity implements policies and procedures to store inputs, items in processing, and outputs completely, accurately, and timely in accordance with system specifications to meet the entity's objectives."),
                ],
            ),
        ],
        "Processing Integrity",
    ),
    (
        "P",
        "Privacy",
        "Personal information is collected, used, retained, disclosed, and disposed of to meet the entity's objectives.",
        [
            (1, "Notice and Communication of Objectives Related to Privacy", [
                ("P1.1", "The entity provides notice to data subjects about its privacy practices to meet the entity's objectives related to privacy. The notice is updated and communicated to data subjects in a timely manner for changes to the entity's privacy practices, including changes in the use of personal information, to meet the entity's objectives related to privacy."),
            ]),
            (2, "Choice and Consent", [
                ("P2.1", "The entity communicates choices available regarding the collection, use, retention, disclosure, and disposal of personal information to the data subjects and the consequences, if any, of each choice. Explicit consent for the collection, use, retention, disclosure, and disposal of personal information is obtained from data subjects or other authorized persons, if required. Such consent is obtained only for the intended purpose of the information to meet the entity's objectives related to privacy. The entity's basis for determining implicit consent for the collection, use, retention, disclosure, and disposal of personal information is documented."),
            ]),
            (3, "Collection", [
                ("P3.1", "Personal information is collected consistent with the entity's objectives related to privacy."),
                ("P3.2", "For information requiring explicit consent, the entity communicates the need for such consent as well as the consequences of a failure to provide consent for the request for personal information and obtains the consent prior to the collection of the information to meet the entity's objectives related to privacy."),
            ]),
            (4, "Use, Retention, and Disposal", [
                ("P4.1", "The entity limits the use of personal information to the purposes identified in the entity's objectives related to privacy."),
                ("P4.2", "The entity retains personal information consistent with the entity's objectives related to privacy."),
                ("P4.3", "The entity securely disposes of personal information to meet the entity's objectives related to privacy."),
            ]),
            (5, "Access", [
                ("P5.1", "The entity grants identified and authenticated data subjects the ability to access their stored personal information for review and, upon request, provides physical or electronic copies of that information to data subjects to meet the entity's objectives related to privacy. If access is denied, data subjects are informed of the denial and reason for such denial, as required, to meet the entity's objectives related to privacy."),
                ("P5.2", "The entity corrects, amends, or appends personal information based on information provided by data subjects and communicates such information to third parties, as committed or required, to meet the entity's objectives related to privacy. If a request for correction is denied, data subjects are informed of the denial and reason for such denial to meet the entity's objectives related to privacy."),
            ]),
            (6, "Disclosure and Notification", [
                ("P6.1", "The entity discloses personal information to third parties with the explicit consent of data subjects and such consent is obtained prior to disclosure to meet the entity's objectives related to privacy."),
                ("P6.2", "The entity creates and retains a complete, accurate, and timely record of authorized disclosures of personal information to meet the entity's objectives related to privacy."),
                ("P6.3", "The entity creates and retains a complete, accurate, and timely record of detected or reported unauthorized disclosures (including breaches) of personal information to meet the entity's objectives related to privacy."),
                ("P6.4", "The entity obtains privacy commitments from vendors and other third parties who have access to personal information to meet the entity's objectives related to privacy. The entity assesses those parties' compliance on a periodic and as-needed basis and takes corrective action, if necessary."),
                ("P6.5", "The entity obtains commitments from vendors and other third parties with access to personal information to notify the entity in the event of actual or suspected unauthorized disclosures of personal information. Such notifications are reported to appropriate personnel and acted on in accordance with established incident-response procedures to meet the entity's objectives related to privacy."),
                ("P6.6", "The entity provides notification of breaches and incidents to affected data subjects, regulators, and others to meet the entity's objectives related to privacy."),
                ("P6.7", "The entity provides data subjects with an accounting of the personal information held and disclosure of the data subjects' personal information, upon the data subjects' request, to meet the entity's objectives related to privacy."),
            ]),
            (7, "Quality", [
                ("P7.1", "The entity collects and maintains accurate, up-to-date, complete, and relevant personal information to meet the entity's objectives related to privacy."),
            ]),
            (8, "Monitoring and Enforcement", [
                ("P8.1", "The entity implements a process for receiving, addressing, resolving, and communicating the resolution of inquiries, complaints, and disputes from data subjects and others and periodically monitors compliance to meet the entity's objectives related to privacy. Corrections and other necessary actions related to identified deficiencies are made or taken in a timely manner."),
            ]),
        ],
        "Privacy",
    ),
]


def build_domain(short_code, full_name, purpose, objectives_raw, applicability_category):
    is_common = short_code == "CC"
    applicability = COMMON_CRITERIA_APPLICABILITY if is_common else _additional_applicability(applicability_category)
    return {
        "short_code": short_code,
        "full_name": full_name,
        "purpose": purpose,
        "practices_populated": True,
        "objectives": [
            {
                "number": number,
                "title": title,
                "purpose": "",
                "practices": [
                    {"id": pid, "text": statement, "applicability": applicability}
                    for pid, statement in criteria
                ],
            }
            for number, title, criteria in objectives_raw
        ],
        "source_version": "",
        "source_url": "",
    }


def main() -> None:
    framework = {
        "name": "SOC 2",
        "full_name": (
            "AICPA Trust Services Criteria for Security, Availability, Processing Integrity, "
            "Confidentiality, and Privacy"
        ),
        "version": "2017 (criteria text, as amended March 2020)",
        "source_title": (
            "2017 Trust Services Criteria for Security, Availability, Processing Integrity, "
            "Confidentiality, and Privacy"
        ),
        "source_publisher": "Association of International Certified Professional Accountants (AICPA)",
        "source_date": "2017 (criteria unchanged by the 2022 revision, which touched only points of focus)",
        "source_url": "https://www.aicpa-cima.com/resources/download/2017-trust-services-criteria-with-revised-points-of-focus-2022",
        "retrieved_date": "2026-07-20",
        "total_practices_in_source": 61,
        "scoring_model": "coverage",
        "mil_levels": [],
        "scoring_note": (
            "SOC 2 (the AICPA Trust Services Criteria) has no native maturity-level concept, like "
            "NIST CSF 2.0/NERC CIP/ISO 27001/CIS Controls — Practice.mil is always None here. Scores "
            "are the project-defined coverage measure via services/scoring_service.py's "
            "compute_domain_coverage. Practice.applicability records whether a criterion is one of "
            "the 33 Common Criteria (required in every SOC 2 report, regardless of scope) or one of "
            "the 28 additional category-specific criteria (required only when that trust services "
            "category — Availability, Confidentiality, Processing Integrity, or Privacy — is in the "
            "engagement's scope), verified from the source document's own applicability table (TSP "
            "Section 100, para. .07) — the same real, disclosed-scope concept NERC CIP's impact-tier "
            "applicability (ADR-0021) and CIS Controls' Implementation Group applicability (ADR-0025) "
            "already represent, not a new one. Like ISO 27001 (ADR-0024), and UNLIKE CIS Controls "
            "(ADR-0025), Practice.text here is the real, verified criterion STATEMENT only — the "
            "shortest real identifying unit for a TSC criterion — never the much longer 'points of "
            "focus' elaboration that follows every criterion in the real source document, which "
            "remains the AICPA's all-rights-reserved copyrighted content (confirmed directly: the "
            "source PDF's own final page states the exact copyright notice, and the AICPA's own "
            "copyright policy page states permission is required to reproduce or redistribute AICPA "
            "content) — see ADR-0026."
        ),
        "domains": [
            build_domain(short_code, full_name, purpose, objectives_raw, applicability_category)
            for short_code, full_name, purpose, objectives_raw, applicability_category in CATEGORIES
        ],
    }

    total_practices = sum(
        len(o["practices"]) for d in framework["domains"] for o in d["objectives"]
    )
    print(f"Categories: {len(framework['domains'])} (all fully populated)")
    print(f"Criteria encoded: {total_practices} of {framework['total_practices_in_source']}")
    assert total_practices == framework["total_practices_in_source"], (
        "Transcribed criterion count does not match this file's own declared "
        "total_practices_in_source — check CATEGORIES for a missing or duplicated criterion "
        "before shipping this data."
    )

    out_path = Path(__file__).resolve().parents[2] / "framework_mapping" / "soc2_tsc.yaml"
    with out_path.open("w", encoding="utf-8") as f:
        f.write(
            "# GENERATED FILE. Do not hand-edit — regenerate via\n"
            "# backend/scripts/generate_soc2_yaml.py, which is the source of truth\n"
            "# for this file's content and carries the source citation.\n"
        )
        yaml.dump(framework, f, sort_keys=False, allow_unicode=True, width=100)


if __name__ == "__main__":
    main()
