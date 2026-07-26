"""Canonical framework ontology feasibility probe (Sprint 18,
controlled-pilot readiness §F.5). Not part of the application (see
scripts/benchmark_scalability.py's module docstring convention: this
directory is for humans to run directly). Run manually:

    cd backend && source .venv/bin/activate
    python scripts/probe_canonical_ontology.py

**A bounded, prototype-scale experiment, not a commitment to build a
full ontology** — per this sprint's own explicit instruction not to
launch a large ontology project without first proving feasibility is
warranted (audit doc §F.5). Question: does tagging practices against a
small, fixed vocabulary of canonical concepts produce tag *overlap*
that predicts this project's own existing human-reviewed cross-framework
equivalence decisions, meaningfully better than chance?

Method:
1. A fixed 10-concept vocabulary (asset management, vulnerability
   management, IAM, patch management, incident response, recovery,
   vendor risk, training, monitoring/logging, network security) — named
   directly in the audit doc, not invented for this script.
2. Every NERC CIP and C2M2 practice that appears in the already-reviewed
   NERC CIP<->C2M2 equivalence pairing (`framework_mapping/
   cross_framework_equivalence.yaml`, 74 entries, 73 unique NERC CIP
   practices, 56 unique C2M2 practices) is hand-tagged against that
   vocabulary below, from the real, verified practice text in
   `framework_mapping/nerc_cip.yaml` / `c2m2_v2_1.yaml` — read and
   tagged independently of which pairings exist, not fit to the answer.
3. For each of the 74 reviewed pairs, check whether the two practices'
   tag sets overlap at all. Compare that hit rate against the same
   check run over every OTHER (NERC CIP, C2M2) combination from the same
   73x56 practice universe (a "presumed non-match" baseline — an
   approximation, since the equivalence file is a curated set of real
   matches, not an exhaustively negative-labeled one, so a few
   plausible-but-unreviewed matches may sit in the baseline pool).

This tagging is intentionally kept local to this script, not written
into framework_mapping/*.yaml — see models/framework.py's
`Practice.canonical_concepts` field docstring and ADR-0035. Populating
real framework data is a decision for *after* this probe's result is
reviewed, not a byproduct of running it.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_FRAMEWORK_MAPPING_DIR = _REPO_ROOT / "framework_mapping"

VOCABULARY = (
    "asset_management",
    "vulnerability_management",
    "iam",
    "patch_management",
    "incident_response",
    "recovery",
    "vendor_risk",
    "training",
    "monitoring_logging",
    "network_security",
)

# Hand-tagged from the real practice text in framework_mapping/nerc_cip.yaml,
# read directly (see this script's history for the extraction). Tags
# reflect a genuine reading of each practice's actual requirement, not
# the pairing it happens to appear in below.
NERC_CIP_TAGS: dict[str, list[str]] = {
    "CIP-003-1.1": ["training", "network_security", "incident_response", "recovery", "vulnerability_management"],
    "CIP-003-1.2": ["training", "iam", "incident_response", "vendor_risk", "network_security"],
    "CIP-004-1.1": ["training"],
    "CIP-004-2.2": ["training", "iam"],
    "CIP-004-3.1": ["iam"],
    "CIP-004-3.2": ["iam"],
    "CIP-004-3.4": ["iam", "vendor_risk"],
    "CIP-004-3.5": ["iam"],
    "CIP-004-4.1": ["iam"],
    "CIP-004-4.3": ["iam"],
    "CIP-004-5.1": ["iam"],
    "CIP-004-5.2": ["iam"],
    "CIP-004-5.3": ["iam"],
    "CIP-006-1.1": ["iam"],
    "CIP-006-1.2": ["iam"],
    "CIP-006-1.4": ["iam", "monitoring_logging"],
    "CIP-006-1.5": ["iam", "monitoring_logging"],
    "CIP-006-1.6": ["iam", "monitoring_logging"],
    "CIP-006-1.7": ["iam", "monitoring_logging"],
    "CIP-006-1.8": ["iam", "monitoring_logging"],
    "CIP-006-1.9": ["iam", "monitoring_logging"],
    "CIP-007-1.1": ["network_security"],
    "CIP-007-1.2": ["network_security"],
    "CIP-007-2.1": ["patch_management", "vulnerability_management"],
    "CIP-007-2.3": ["patch_management", "vulnerability_management"],
    "CIP-007-4.1": ["monitoring_logging", "incident_response"],
    "CIP-007-4.2": ["monitoring_logging"],
    "CIP-007-4.4": ["monitoring_logging"],
    "CIP-007-5.1": ["iam"],
    "CIP-007-5.3": ["iam"],
    "CIP-007-5.5": ["iam"],
    "CIP-007-5.6": ["iam"],
    "CIP-008-1.1": ["incident_response"],
    "CIP-008-1.2": ["incident_response"],
    "CIP-008-1.3": ["incident_response"],
    "CIP-008-1.4": ["incident_response"],
    "CIP-008-2.1": ["incident_response"],
    "CIP-008-2.3": ["incident_response", "monitoring_logging"],
    "CIP-008-3.1": ["incident_response"],
    "CIP-009-1.1": ["recovery"],
    "CIP-009-1.2": ["recovery", "incident_response"],
    "CIP-009-1.3": ["recovery"],
    "CIP-009-1.4": ["recovery"],
    "CIP-009-1.5": ["recovery", "incident_response"],
    "CIP-009-2.1": ["recovery"],
    "CIP-009-2.2": ["recovery"],
    "CIP-009-2.3": ["recovery"],
    "CIP-009-3.1": ["recovery"],
    "CIP-010-1.1": ["asset_management"],
    "CIP-010-1.2": ["asset_management"],
    "CIP-010-1.3": ["asset_management"],
    "CIP-010-1.4": ["asset_management", "network_security"],
    "CIP-010-1.5": ["asset_management"],
    "CIP-010-1.6": ["asset_management", "vendor_risk"],
    "CIP-010-2.1": ["asset_management", "monitoring_logging"],
    "CIP-010-3.1": ["vulnerability_management"],
    "CIP-010-3.2": ["vulnerability_management"],
    "CIP-010-3.3": ["vulnerability_management", "asset_management"],
    "CIP-010-4": ["asset_management", "network_security"],
    "CIP-011-1.1": ["asset_management"],
    "CIP-011-1.2": ["asset_management", "network_security"],
    "CIP-011-2.1": ["asset_management"],
    "CIP-011-2.2": ["asset_management"],
    "CIP-012-1.1": ["network_security"],
    "CIP-012-1.3": ["recovery", "network_security"],
    "CIP-012-1.5": ["network_security"],
    "CIP-013-1.1": ["vendor_risk"],
    "CIP-013-1.2": ["vendor_risk", "incident_response", "vulnerability_management"],
    "CIP-013-2": ["vendor_risk"],
    "CIP-014-2.1": ["vendor_risk"],
    "CIP-014-4.3": ["monitoring_logging"],
    "CIP-014-5.2": ["incident_response"],
    "CIP-014-6.1": ["vendor_risk"],
}

# Hand-tagged from the real practice text in framework_mapping/c2m2_v2_1.yaml.
C2M2_TAGS: dict[str, list[str]] = {
    "ACCESS-1a": ["iam"],
    "ACCESS-1d": ["iam"],
    "ACCESS-1f": ["iam"],
    "ACCESS-2a": ["iam"],
    "ACCESS-2b": ["iam"],
    "ACCESS-2c": ["iam"],
    "ACCESS-2h": ["iam"],
    "ACCESS-3a": ["iam"],
    "ACCESS-3c": ["iam", "monitoring_logging"],
    "ACCESS-3d": ["iam"],
    "ACCESS-3j": ["iam", "monitoring_logging"],
    "ARCHITECTURE-3d": ["network_security"],
    "ARCHITECTURE-3g": ["network_security", "asset_management"],
    "ARCHITECTURE-4g": ["asset_management", "vendor_risk"],
    "ARCHITECTURE-5a": ["asset_management"],
    "ARCHITECTURE-5c": ["network_security"],
    "ASSET-2a": ["asset_management"],
    "ASSET-2h": ["asset_management"],
    "ASSET-3a": ["asset_management"],
    "ASSET-3d": ["asset_management"],
    "ASSET-3e": ["asset_management", "monitoring_logging"],
    "ASSET-4a": ["asset_management"],
    "ASSET-4d": ["asset_management"],
    "ASSET-4h": ["asset_management"],
    "PROGRAM-1a": [],
    "RESPONSE-2a": ["incident_response"],
    "RESPONSE-2f": ["incident_response", "monitoring_logging"],
    "RESPONSE-3a": ["incident_response"],
    "RESPONSE-3e": ["incident_response"],
    "RESPONSE-3g": ["incident_response"],
    "RESPONSE-3h": ["incident_response"],
    "RESPONSE-3j": ["incident_response", "vendor_risk"],
    "RESPONSE-4a": ["recovery"],
    "RESPONSE-4b": ["recovery"],
    "RESPONSE-4h": ["recovery", "incident_response"],
    "RESPONSE-4i": ["recovery"],
    "RESPONSE-4o": ["recovery"],
    "RESPONSE-5d": ["incident_response"],
    "SITUATION-1a": ["monitoring_logging"],
    "SITUATION-2a": ["monitoring_logging"],
    "SITUATION-2e": ["monitoring_logging"],
    "THIRD-PARTIES-1c": ["vendor_risk"],
    "THIRD-PARTIES-2c": ["vendor_risk"],
    "THIRD-PARTIES-2f": ["vendor_risk"],
    "THREAT-1c": ["vulnerability_management"],
    "THREAT-1e": ["vulnerability_management", "monitoring_logging"],
    "THREAT-1f": ["vulnerability_management"],
    "THREAT-1h": ["patch_management", "vulnerability_management"],
    "THREAT-1k": ["vulnerability_management"],
    "THREAT-2h": ["monitoring_logging"],
    "WORKFORCE-1a": ["iam"],
    "WORKFORCE-1c": ["iam"],
    "WORKFORCE-1d": ["iam"],
    "WORKFORCE-1f": ["iam", "vendor_risk"],
    "WORKFORCE-2d": ["training"],
    "WORKFORCE-4d": ["training", "iam"],
}


def _load_reviewed_pairs() -> list[tuple[str, str]]:
    data = yaml.safe_load((_FRAMEWORK_MAPPING_DIR / "cross_framework_equivalence.yaml").read_text())
    return [
        (e["practice_a_id"], e["practice_b_id"]) if e["framework_a"] == "NERC CIP" else (e["practice_b_id"], e["practice_a_id"])
        for e in data
        if {e.get("framework_a"), e.get("framework_b")} == {"NERC CIP", "C2M2"}
    ]


def run_probe() -> dict:
    reviewed_pairs = _load_reviewed_pairs()
    tagged_nerc_ids = sorted(NERC_CIP_TAGS)
    tagged_c2m2_ids = sorted(C2M2_TAGS)

    missing_a = {a for a, _b in reviewed_pairs} - set(NERC_CIP_TAGS)
    missing_b = {b for _a, b in reviewed_pairs} - set(C2M2_TAGS)
    if missing_a or missing_b:
        raise AssertionError(f"Untagged practices in the reviewed set: {missing_a | missing_b}")

    def overlaps(a: str, b: str) -> bool:
        return bool(set(NERC_CIP_TAGS[a]) & set(C2M2_TAGS[b]))

    reviewed_hits = sum(overlaps(a, b) for a, b in reviewed_pairs)
    reviewed_rate = reviewed_hits / len(reviewed_pairs)

    reviewed_set = set(reviewed_pairs)
    baseline_pairs = [
        (a, b) for a in tagged_nerc_ids for b in tagged_c2m2_ids if (a, b) not in reviewed_set
    ]
    baseline_hits = sum(overlaps(a, b) for a, b in baseline_pairs)
    baseline_rate = baseline_hits / len(baseline_pairs)

    untagged_practices = sorted(
        pid for pid, tags in {**NERC_CIP_TAGS, **C2M2_TAGS}.items() if not tags
    )

    return {
        "vocabulary": list(VOCABULARY),
        "tagged_practice_count": {"nerc_cip": len(tagged_nerc_ids), "c2m2": len(tagged_c2m2_ids)},
        "untagged_practices": untagged_practices,
        "untagged_note": (
            "Practices with no tag from the fixed 10-concept vocabulary at all -- a real "
            "vocabulary-coverage gap, not a scoring error."
        ),
        "reviewed_pairs": {
            "count": len(reviewed_pairs),
            "tag_overlap_hit_rate": reviewed_rate,
        },
        "baseline_non_reviewed_pairs": {
            "count": len(baseline_pairs),
            "tag_overlap_hit_rate": baseline_rate,
            "note": (
                "Every other (NERC CIP, C2M2) combination from the same tagged practice "
                "universe, not in the reviewed set. An approximation of a negative baseline, "
                "not an exhaustively negative-labeled one -- some pairs in this pool may be "
                "plausible matches nobody has reviewed yet."
            ),
        },
        "lift": (reviewed_rate / baseline_rate) if baseline_rate > 0 else None,
        "interpretation_note": (
            "A lift > 1 means tag overlap fires more often on real reviewed equivalences than "
            "on the rest of the practice universe -- weak evidence FOR feasibility, not proof. "
            "This script deliberately does not render a go/no-go verdict; that judgment belongs "
            "to a human, informed by both this number and the untagged-practice gap above."
        ),
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    result = run_probe()
    print(json.dumps(result, indent=2))

    if args.output:
        args.output.write_text(json.dumps(result, indent=2))
        print(f"\nWrote results to {args.output}")


if __name__ == "__main__":
    main()
