"""Candidate generator for framework_mapping/cross_framework_equivalence.yaml.

Not part of the application (see scripts/README.md). This is Step 1 of a
two-step process — see docs/adr/ADR-0019-cross-framework-equivalence.md
and .claude/skills/framework-mapping/SKILL.md point 3: "Cross-framework
equivalence is additive, not automatic... not inferred by embedding
similarity alone... embedding similarity can seed a candidate mapping
for human review; it should not silently become an accepted mapping."

This script only prints candidates (the top-3 most semantically similar
C2M2 practices for every NIST CSF 2.0 subcategory, via the same local
embedder used everywhere else in this project) to stdout for a human
review pass. It does NOT write framework_mapping/cross_framework_equivalence.yaml
directly — that file is hand-curated (Step 2) from a subset of this
output, each accepted entry carrying a rationale sentence, not just a
similarity score. Run with:

    cd backend && source .venv/bin/activate && python scripts/generate_cross_framework_equivalence.py
"""

from __future__ import annotations

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


def main() -> None:
    settings = get_settings()
    registry = FrameworkRegistry(settings.framework_mapping_dir)
    c2m2 = registry.require("C2M2")
    nist = registry.require("NIST CSF 2.0")

    c2m2_practices = [
        practice
        for domain in c2m2.domains
        if domain.practices_populated
        for practice in domain.all_practices()
    ]
    nist_practices = [practice for domain in nist.domains for practice in domain.all_practices()]

    print(f"Embedding {len(c2m2_practices)} C2M2 practices and {len(nist_practices)} NIST subcategories...")
    embedder = get_embedder("semantic_local_onnx", cache_dir=Path(settings.embedding_model_cache_dir))
    c2m2_vectors = embedder.embed([p.text for p in c2m2_practices])
    nist_vectors = embedder.embed([p.text for p in nist_practices])

    print(f"\n{'=' * 100}")
    for nist_practice, nist_vector in zip(nist_practices, nist_vectors, strict=True):
        scored = [
            (_cosine_similarity(nist_vector, c2m2_vector), c2m2_practice)
            for c2m2_practice, c2m2_vector in zip(c2m2_practices, c2m2_vectors, strict=True)
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        print(f"\n{nist_practice.id}: {nist_practice.text}")
        for similarity, c2m2_practice in scored[:3]:
            print(f"    {similarity:.3f}  {c2m2_practice.id}: {c2m2_practice.text}")


if __name__ == "__main__":
    main()
