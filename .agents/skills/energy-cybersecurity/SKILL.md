---
name: energy-cybersecurity
description: Use when writing documentation, demo narrative, or feature descriptions that need to connect this platform to the energy sector (utilities, generation, transmission, oil and gas, OT/IT integration) and to why consulting firms build this category of tool.
---

# Energy Sector Cybersecurity Context

Domain framing to keep this platform's documentation, demo scripts, and MBA/consulting narrative grounded in real energy-sector context rather than generic "AI compliance tool" language.

## Who actually uses something like this

- **Utilities and transmission operators** subject to NERC CIP as bulk electric system entities — binding regulatory compliance, audited by NERC/regional entities, with real penalties for gaps.
- **Generation companies**, whose OT environments (SCADA, ICS) are the primary asset this entire compliance category exists to protect — control-system cybersecurity, not just corporate IT security, is the actual subject matter of C2M2 and NERC CIP.
- **Oil and gas / broader critical infrastructure**, where C2M2 was originally designed to be sector-adaptable (it originated from an electricity-subsector model but is explicitly built for cross-sector use).

## The IT/OT distinction, stated precisely

Do not describe this platform's subject matter as generic "cybersecurity" without acknowledging the IT/OT split: Operational Technology (control systems, SCADA, physical process equipment) has different risk profiles, patching constraints (a control system often cannot be patched on IT's schedule without a safety review), and threat models than IT. C2M2 and NERC CIP are meaningful specifically because they address this OT-aware maturity, not because they're a rebrand of general IT security frameworks. Getting this distinction right in documentation is a credibility signal to anyone in the sector who reviews this project.

## Why consulting firms build tools like this

Firms with energy/utilities practices (McKinsey, BCG, Deloitte, Accenture) build compliance-acceleration tooling because: (1) the underlying assessment work is billable-hour-intensive and consultants have a direct incentive to make their own delivery more efficient without reducing engagement value, and (2) a proprietary tool becomes a differentiator in competitive RFPs for regulatory advisory work. When writing MBA/consulting narrative content (see `executive-reporting` for the report-facing version of this discipline), frame this platform explicitly as "the kind of accelerator a firm's energy practice would build for its own delivery teams," not as a generic SaaS pitch — that framing is what makes the project legible to a consulting interviewer.

## Example usage

Writing any `docs/consulting/` deliverable, demo script, or MBA application narrative section that needs to explain why this project matters to someone outside the energy sector.
