"""Generates framework_mapping/iso_27001.yaml (ADR-0024).

DELIBERATELY TITLES-ONLY. Unlike every other framework in this project
(C2M2: DOE, public domain; NIST CSF 2.0: NIST, public domain; NERC CIP:
NERC, freely published reliability standards), ISO/IEC 27001:2022 is a
paid, copyrighted publication (~CHF 546 / ~$600 from the ISO/IEC
webstores) with no free full-text access — confirmed directly (not
assumed) before writing any code: only a limited front-matter preview
is public at https://www.iso.org/obp/ui/en/#!iso:std:82875:en.

This project's standing discipline is "verified over fabricated" — the
full descriptive requirement text for each Annex A control is not
something this project can legally or honestly transcribe without
purchasing the standard. Reconstructing it from training-data memory
would violate that discipline and risks misreproducing copyrighted
text inaccurately.

What IS freely, legitimately available and used here: the 93 real
Annex A control IDs and their short official titles (e.g. "A.5.1
Policies for information security") — these are widely published as
factual short titles by ISO's own marketing material and numerous
secondary compliance sources, distinct from the full descriptive
"shall" requirement text. Verified directly (not summarized by an
intermediate model) by rendering multiple candidate source pages with
a headless browser and reading the real DOM text, since several of
these pages render their control tables via client-side JavaScript
that a plain HTTP fetch does not execute. One first-pass source
(hightable.io) was caught NOT actually rendering the full list on its
page despite an AI-summarization tool initially reporting a "complete"
list from it — a concrete instance of exactly the fabrication risk
this project's verification discipline exists to catch. The list
below is sourced from dataguard.com/iso-27001/annex-a/, confirmed to
literally render all 93 controls in its page DOM (not a summarizer
reconstruction), cross-checked against independent sources for ~20
overlapping entries, with one confirmed data-entry correction (5.37,
whose rendered text on that page had an erroneous appended fragment
from an adjacent heading; corrected to "Documented operating
procedures" per unanimous agreement across every other source
checked).

Given this project's own "verified over fabricated, don't build ahead
of actual need" discipline, this is a genuine, disclosed scope
decision (see ADR-0024): Practice.text below is the real, verified
control TITLE only, never a full requirement description. Every
consumer of this data (scoring, cross-framework equivalence, UI) must
treat it accordingly — see scoring_note below and the iso-27001-expert
skill.
"""

from __future__ import annotations

from pathlib import Path

import yaml

# (short_code, full_name, [(control_id, title), ...])
THEMES: list[tuple[str, str, list[tuple[str, str]]]] = [
    (
        "A.5",
        "Organizational controls",
        [
            ("A.5.1", "Policies for information security"),
            ("A.5.2", "Information security roles and responsibilities"),
            ("A.5.3", "Segregation of duties"),
            ("A.5.4", "Management responsibilities"),
            ("A.5.5", "Contact with authorities"),
            ("A.5.6", "Contact with special interest groups"),
            ("A.5.7", "Threat intelligence"),
            ("A.5.8", "Information security in project management"),
            ("A.5.9", "Inventory of information and other associated assets"),
            ("A.5.10", "Acceptable use of information and other associated assets"),
            ("A.5.11", "Return of assets"),
            ("A.5.12", "Classification of information"),
            ("A.5.13", "Labelling of information"),
            ("A.5.14", "Information transfer"),
            ("A.5.15", "Access control"),
            ("A.5.16", "Identity management"),
            ("A.5.17", "Authentication information"),
            ("A.5.18", "Access rights"),
            ("A.5.19", "Information security in supplier relationships"),
            ("A.5.20", "Addressing information security within supplier agreements"),
            ("A.5.21", "Managing information security in the ICT supply chain"),
            ("A.5.22", "Monitoring, review and change management of supplier services"),
            ("A.5.23", "Information security for use of cloud services"),
            ("A.5.24", "Information security incident management planning and preparation"),
            ("A.5.25", "Assessment and decision on information security events"),
            ("A.5.26", "Response to information security incidents"),
            ("A.5.27", "Learning from information security incidents"),
            ("A.5.28", "Collection of evidence"),
            ("A.5.29", "Information security during disruption"),
            ("A.5.30", "ICT readiness for business continuity"),
            ("A.5.31", "Legal, statutory, regulatory and contractual requirements"),
            ("A.5.32", "Intellectual property rights"),
            ("A.5.33", "Protection of records"),
            ("A.5.34", "Privacy and protection of PII"),
            ("A.5.35", "Independent review of information security"),
            ("A.5.36", "Compliance with policies, rules and standards for information security"),
            ("A.5.37", "Documented operating procedures"),
        ],
    ),
    (
        "A.6",
        "People controls",
        [
            ("A.6.1", "Screening"),
            ("A.6.2", "Terms and conditions of employment"),
            ("A.6.3", "Information security awareness, education and training"),
            ("A.6.4", "Disciplinary process"),
            ("A.6.5", "Responsibilities after termination or change of employment"),
            ("A.6.6", "Confidentiality or non-disclosure agreements"),
            ("A.6.7", "Remote working"),
            ("A.6.8", "Information security event reporting"),
        ],
    ),
    (
        "A.7",
        "Physical controls",
        [
            ("A.7.1", "Physical security perimeters"),
            ("A.7.2", "Physical entry"),
            ("A.7.3", "Securing offices, rooms and facilities"),
            ("A.7.4", "Physical security monitoring"),
            ("A.7.5", "Protecting against physical and environmental threats"),
            ("A.7.6", "Working in secure areas"),
            ("A.7.7", "Clear desk and clear screen"),
            ("A.7.8", "Equipment siting and protection"),
            ("A.7.9", "Security of assets off-premises"),
            ("A.7.10", "Storage media"),
            ("A.7.11", "Supporting utilities"),
            ("A.7.12", "Cabling security"),
            ("A.7.13", "Equipment maintenance"),
            ("A.7.14", "Secure disposal or re-use of equipment"),
        ],
    ),
    (
        "A.8",
        "Technological controls",
        [
            ("A.8.1", "User endpoint devices"),
            ("A.8.2", "Privileged access rights"),
            ("A.8.3", "Information access restriction"),
            ("A.8.4", "Access to source code"),
            ("A.8.5", "Secure authentication"),
            ("A.8.6", "Capacity management"),
            ("A.8.7", "Protection against malware"),
            ("A.8.8", "Management of technical vulnerabilities"),
            ("A.8.9", "Configuration management"),
            ("A.8.10", "Information deletion"),
            ("A.8.11", "Data masking"),
            ("A.8.12", "Data leakage prevention"),
            ("A.8.13", "Information backup"),
            ("A.8.14", "Redundancy of information processing facilities"),
            ("A.8.15", "Logging"),
            ("A.8.16", "Monitoring activities"),
            ("A.8.17", "Clock synchronization"),
            ("A.8.18", "Use of privileged utility programs"),
            ("A.8.19", "Installation of software on operational systems"),
            ("A.8.20", "Networks security"),
            ("A.8.21", "Security of network services"),
            ("A.8.22", "Segregation of networks"),
            ("A.8.23", "Web filtering"),
            ("A.8.24", "Use of cryptography"),
            ("A.8.25", "Secure development life cycle"),
            ("A.8.26", "Application security requirements"),
            ("A.8.27", "Secure system architecture and engineering principles"),
            ("A.8.28", "Secure coding"),
            ("A.8.29", "Security testing in development and acceptance"),
            ("A.8.30", "Outsourced development"),
            ("A.8.31", "Separation of development, test and production environments"),
            ("A.8.32", "Change management"),
            ("A.8.33", "Test information"),
            ("A.8.34", "Protection of information systems during audit testing"),
        ],
    ),
]


def build_domain(short_code: str, full_name: str, controls: list[tuple[str, str]]) -> dict:
    return {
        "short_code": short_code,
        "full_name": full_name,
        "purpose": f"The {full_name} theme of ISO/IEC 27001:2022 Annex A ({len(controls)} controls).",
        "practices_populated": True,
        "objectives": [
            {
                "number": 1,
                "title": full_name,
                "purpose": "",
                "practices": [
                    {"id": control_id, "text": title} for control_id, title in controls
                ],
            }
        ],
        "source_version": "",
        "source_url": "",
    }


def main() -> None:
    framework = {
        "name": "ISO 27001",
        "full_name": (
            "ISO/IEC 27001:2022 Information security, cybersecurity and privacy protection — "
            "Information security management systems — Requirements, Annex A (control titles only "
            "— see scoring_note)"
        ),
        "version": "2022",
        "source_title": "ISO/IEC 27001:2022, Annex A (reference control titles)",
        "source_publisher": (
            "International Organization for Standardization (ISO) / International Electrotechnical "
            "Commission (IEC)"
        ),
        "source_date": "2022-10-25",
        "source_url": "https://www.iso.org/standard/27001",
        "retrieved_date": "2026-07-19",
        "total_practices_in_source": 93,
        "scoring_model": "coverage",
        "mil_levels": [],
        "scoring_note": (
            "ISO/IEC 27001:2022 is a paid, copyrighted standard (~CHF 546) with no free full-text "
            "access, unlike every other framework in this project. Practice.text below is the real, "
            "verified official control TITLE ONLY (e.g. 'Use of cryptography') — NOT the full "
            "descriptive 'shall' requirement text the standard itself contains, which is not freely "
            "available and has not been transcribed here (see ADR-0024, the iso-27001-expert skill, "
            "and this project's standing verified-over-fabricated discipline). This has two real "
            "consequences every consumer of this data must respect: (1) coverage scoring here is "
            "necessarily coarser than for C2M2/NIST CSF 2.0/NERC CIP, since a reviewer can only judge "
            "evidence against a short title, not a specific documented obligation; (2) cross-framework "
            "equivalence entries involving ISO 27001 are topical/title-based judgments, not the full "
            "text-based semantic comparison used for every other framework pairing in "
            "cross_framework_equivalence.yaml, and are explicitly labeled as such."
        ),
        "domains": [build_domain(code, name, controls) for code, name, controls in THEMES],
    }

    total_practices = sum(
        len(o["practices"]) for d in framework["domains"] for o in d["objectives"]
    )
    print(f"Themes: {len(framework['domains'])} (all title-only, fully populated)")
    print(f"Controls encoded: {total_practices} of {framework['total_practices_in_source']}")
    assert total_practices == framework["total_practices_in_source"], (
        "Transcribed control count does not match this file's own declared "
        "total_practices_in_source — check THEMES for a missing or duplicated control before "
        "shipping this data."
    )

    out_path = Path(__file__).resolve().parents[2] / "framework_mapping" / "iso_27001.yaml"
    with out_path.open("w", encoding="utf-8") as f:
        f.write(
            "# GENERATED FILE. Do not hand-edit — regenerate via\n"
            "# backend/scripts/generate_iso_27001_yaml.py, which is the source of truth\n"
            "# for this file's content and carries the source citation and its limitations.\n"
        )
        yaml.dump(framework, f, sort_keys=False, allow_unicode=True, width=100)


if __name__ == "__main__":
    main()
