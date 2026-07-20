"""Candidate generator for framework_mapping/cross_framework_equivalence.yaml.

Not part of the application (see scripts/README.md). This is Step 1 of a
two-step process — see docs/adr/ADR-0019-cross-framework-equivalence.md,
docs/adr/ADR-0023-nerc-cip-cross-framework-equivalence.md, and
.claude/skills/framework-mapping/SKILL.md point 3: "Cross-framework
equivalence is additive, not automatic... not inferred by embedding
similarity alone... embedding similarity can seed a candidate mapping
for human review; it should not silently become an accepted mapping."

This script only prints candidates (the top-3 most semantically similar
practices in one framework for every practice in another, via the same
local embedder used everywhere else in this project) to stdout for a
human review pass. It does NOT write framework_mapping/
cross_framework_equivalence.yaml directly — that file is hand-curated
(Step 2) from a subset of this output, each accepted entry carrying a
rationale sentence, not just a similarity score. Run with:

    cd backend && source .venv/bin/activate && python scripts/generate_cross_framework_equivalence.py [pair]

where [pair] is "nist" (NIST CSF 2.0 reviewed against C2M2, ADR-0019,
the default), "nerc" (NERC CIP reviewed against C2M2, ADR-0023), "iso"
(NERC CIP reviewed against ISO 27001, ADR-0024), "cis" (NERC CIP
reviewed against CIS Controls v8, ADR-0025), or "soc2" (NERC CIP
reviewed against SOC 2, ADR-0026). The "iso" and "soc2" pairs are
methodologically weaker than the others: ISO 27001's side is a short
official control TITLE only, and SOC 2's side is a short official
criterion STATEMENT only (see generate_iso_27001_yaml.py's and
generate_soc2_yaml.py's module docstrings — the full requirement/
points-of-focus text is copyrighted, all-rights-reserved content not
available to this project to reproduce), so these candidate lists are
a title-or-statement-vs-full-text comparison, not the
full-text-vs-full-text comparison every other pairing uses. Treat
their candidates with correspondingly more skepticism during review.
The "cis" pair does not have this weakness — CIS Controls v8's side is
full official Safeguard text, the same full-text-vs-full-text
comparison as "nist"/"nerc".
"""

from __future__ import annotations

import sys
from pathlib import Path

from compliance_platform.ai.embeddings import get_embedder
from compliance_platform.core.config import get_settings
from compliance_platform.services.framework_loader import FrameworkRegistry


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _print_top3_candidates(reviewed_practices, reviewed_label, target_practices, target_label, embedder) -> None:
    print(f"Embedding {len(target_practices)} {target_label} practices and {len(reviewed_practices)} {reviewed_label} practices...")
    target_vectors = embedder.embed([p.text for p in target_practices])
    reviewed_vectors = embedder.embed([p.text for p in reviewed_practices])

    print(f"\n{'=' * 100}")
    for reviewed_practice, reviewed_vector in zip(reviewed_practices, reviewed_vectors, strict=True):
        scored = [
            (_cosine_similarity(reviewed_vector, target_vector), target_practice)
            for target_practice, target_vector in zip(target_practices, target_vectors, strict=True)
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        print(f"\n{reviewed_practice.id}: {reviewed_practice.text}")
        for similarity, target_practice in scored[:3]:
            print(f"    {similarity:.3f}  {target_practice.id}: {target_practice.text}")


def main() -> None:
    pair = sys.argv[1] if len(sys.argv) > 1 else "nist"
    settings = get_settings()
    registry = FrameworkRegistry(settings.framework_mapping_dir)
    c2m2 = registry.require("C2M2")
    c2m2_practices = [
        practice
        for domain in c2m2.domains
        if domain.practices_populated
        for practice in domain.all_practices()
    ]
    embedder = get_embedder("semantic_local_onnx", cache_dir=Path(settings.embedding_model_cache_dir))

    if pair == "nist":
        nist = registry.require("NIST CSF 2.0")
        nist_practices = [practice for domain in nist.domains for practice in domain.all_practices()]
        _print_top3_candidates(nist_practices, "NIST CSF 2.0", c2m2_practices, "C2M2", embedder)
    elif pair == "nerc":
        nerc = registry.require("NERC CIP")
        nerc_practices = [practice for domain in nerc.domains for practice in domain.all_practices()]
        _print_top3_candidates(nerc_practices, "NERC CIP", c2m2_practices, "C2M2", embedder)
    elif pair == "iso":
        nerc = registry.require("NERC CIP")
        nerc_practices = [practice for domain in nerc.domains for practice in domain.all_practices()]
        iso = registry.require("ISO 27001")
        iso_practices = [practice for domain in iso.domains for practice in domain.all_practices()]
        _print_top3_candidates(nerc_practices, "NERC CIP", iso_practices, "ISO 27001", embedder)
    elif pair == "cis":
        nerc = registry.require("NERC CIP")
        nerc_practices = [practice for domain in nerc.domains for practice in domain.all_practices()]
        cis = registry.require("CIS Controls")
        cis_practices = [practice for domain in cis.domains for practice in domain.all_practices()]
        _print_top3_candidates(nerc_practices, "NERC CIP", cis_practices, "CIS Controls", embedder)
    elif pair == "soc2":
        nerc = registry.require("NERC CIP")
        nerc_practices = [practice for domain in nerc.domains for practice in domain.all_practices()]
        soc2 = registry.require("SOC 2")
        soc2_practices = [practice for domain in soc2.domains for practice in domain.all_practices()]
        _print_top3_candidates(nerc_practices, "NERC CIP", soc2_practices, "SOC 2", embedder)
    else:
        raise SystemExit(f"Unknown pair {pair!r} — expected 'nist', 'nerc', 'iso', 'cis', or 'soc2'.")


if __name__ == "__main__":
    main()
