"""One-off generator for the NIST CSF 1.1 <-> NIST CSF 2.0 section of
framework_mapping/cross_framework_equivalence.yaml.

Not part of the application (see scripts/README.md).

Why this pairing is different from every other one in that file
---------------------------------------------------------------
Every existing pairing (ADR-0019, ADR-0023 through ADR-0029) was produced
the same way: embedding similarity proposed candidates, and a human
reviewed each one and wrote a rationale. `framework-mapping.mdc` requires
exactly that -- "equivalence is additive, not automatic... not inferred by
embedding similarity alone."

This pairing is not inferred at all. NIST publishes the mapping itself:
every CSF 2.0 Subcategory carries an Informative Reference naming the CSF
1.1 Subcategories it derives from, in NIST's own CSF 2.0 Reference Tool
export ("CSF v1.1: ID.BE-2, ID.BE-3"). Transcribing an authoritative
crosswalk published by the standard's own author is a stronger basis than
this project's own review, not a weaker one -- so the rationale on every
entry below cites NIST rather than paraphrasing a judgment nobody made.

Similarity is still computed with this project's own embedder, because
the file's schema carries it and its header requires scores to be real
rather than hand-written. It is disclosed context here, not the basis for
acceptance -- for several genuinely-renumbered pairs the score is low
while the mapping is nonetheless NIST's own.

Source: NIST Cybersecurity Framework (CSF) 2.0 Reference Tool export,
https://csrc.nist.gov/extensions/nudp/services/json/csf/download?olirids=all
(XLSX, sheet "CSF 2.0", column "Informative References").

Usage:
    python scripts/generate_nist_csf_version_crosswalk.py [path-to-olir.xlsx]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import openpyxl
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from compliance_platform.ai.embeddings import get_embedder  # noqa: E402
from compliance_platform.core.config import Settings  # noqa: E402
from compliance_platform.services.framework_loader import load_framework_file  # noqa: E402

MAPPING_DIR = REPO_ROOT / "framework_mapping"
EQUIVALENCE_PATH = MAPPING_DIR / "cross_framework_equivalence.yaml"
SOURCE_URL = "https://csrc.nist.gov/extensions/nudp/services/json/csf/download?olirids=all"

# A CSF Subcategory id: two-letter function, two-letter category, number.
_SUBCATEGORY_RE = re.compile(r"^[A-Z]{2}\.[A-Z]{2}-\d+$")
_REFERENCE_PREFIX = "CSF v1.1:"


def _practice_texts(filename: str) -> dict[str, str]:
    framework = load_framework_file(MAPPING_DIR / filename)
    return {p.id: p.text for d in framework.domains for p in d.all_practices()}


def _extract_references(xlsx_path: Path) -> dict[str, set[str]]:
    """{csf_2_0_subcategory_id: {csf_1_1_subcategory_id, ...}}.

    Rows repeat per Implementation Example, so references accumulate into
    a set rather than being read once per row.
    """
    workbook = openpyxl.load_workbook(xlsx_path, data_only=True)
    sheet = workbook["CSF 2.0"]
    references: dict[str, set[str]] = {}
    for row in sheet.iter_rows(values_only=True):
        subcategory, informative = row[2], row[4]
        if not subcategory or not informative:
            continue
        identifier = str(subcategory).split(":")[0].strip()
        if not _SUBCATEGORY_RE.match(identifier):
            continue
        for line in str(informative).splitlines():
            line = line.strip()
            if not line.startswith(_REFERENCE_PREFIX):
                continue
            for reference in line[len(_REFERENCE_PREFIX) :].split(","):
                reference = reference.strip()
                if reference:
                    references.setdefault(identifier, set()).add(reference)
    workbook.close()
    return references


def main() -> None:
    xlsx_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/nist_olir.xlsx")
    if not xlsx_path.exists():
        raise SystemExit(
            f"NIST CSF 2.0 reference export not found at {xlsx_path}. Download it first:\n"
            f"  curl -sL -A 'Mozilla/5.0' -o {xlsx_path} '{SOURCE_URL}'"
        )

    texts_11 = _practice_texts("nist_csf_1_1.yaml")
    texts_20 = _practice_texts("nist_csf_2_0.yaml")
    references = _extract_references(xlsx_path)

    pairs: list[tuple[str, str]] = []
    dropped: list[tuple[str, str, str]] = []
    for id_20, ids_11 in sorted(references.items()):
        if id_20 not in texts_20:
            dropped.append((id_20, "-", "2.0 id not present in this project's transcription"))
            continue
        for id_11 in sorted(ids_11):
            if id_11 not in texts_11:
                # NIST references a whole CATEGORY in a couple of places
                # (e.g. "PR.DS") rather than a Subcategory. A category is
                # not a Practice in this project's schema, so there is no
                # practice-to-practice equivalence to record -- dropped
                # with the reason stated rather than silently skipped, and
                # never "resolved" by inventing a leaf.
                dropped.append((id_20, id_11, "1.1 reference is not a Subcategory-level id"))
                continue
            pairs.append((id_11, id_20))

    settings = Settings()
    embedder = get_embedder(
        settings.embedding_backend,
        n_features=settings.embedding_dimensions,
        model_name=settings.embedding_model_name,
        cache_dir=settings.embedding_model_cache_dir,
    )
    left = embedder.embed([texts_11[a] for a, _ in pairs])
    right = embedder.embed([texts_20[b] for _, b in pairs])

    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b, strict=True))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(y * y for y in b) ** 0.5
        return dot / (na * nb) if na and nb else 0.0

    entries = [
        {
            "framework_a": "NIST CSF 1.1",
            "practice_a_id": id_11,
            "framework_b": "NIST CSF 2.0",
            "practice_b_id": id_20,
            "similarity": round(_cosine(left[i], right[i]), 3),
            "rationale": (
                f"NIST's own CSF 2.0 Informative References list CSF v1.1 {id_11} as a source "
                f"for {id_20}. Transcribed from that published crosswalk, not inferred here."
            ),
        }
        for i, (id_11, id_20) in enumerate(pairs)
    ]

    header = f"""
# --- NIST CSF 1.1 <-> NIST CSF 2.0 (ADR-0055, Sprint 19) ---
# The only pairing in this file NOT produced by this project's own
# similarity-then-human-review process. NIST publishes this mapping
# itself: each CSF 2.0 Subcategory's Informative References name the CSF
# 1.1 Subcategories it derives from. Transcribed from NIST's CSF 2.0
# Reference Tool export ({SOURCE_URL}),
# sheet "CSF 2.0", column "Informative References". Authoritative rather
# than inferred, which is why every rationale below cites NIST instead of
# paraphrasing a judgment no human here made.
#
# {len(entries)} entries covering {len({a for a, _ in pairs})} of {len(texts_11)} CSF 1.1
# subcategories. Coverage is partial because NIST itself maps only
# {len(references)} of the 2.0 subcategories back to 1.1 -- concepts new in
# 2.0 (most of the GOVERN function) have no 1.1 predecessor to cite, which
# is a real property of the standards, not a gap in this transcription.
# {len(dropped)} reference(s) dropped: see the generator for the reasons.
# Regenerate via backend/scripts/generate_nist_csf_version_crosswalk.py.
"""

    body = yaml.safe_dump(entries, sort_keys=False, allow_unicode=True, width=100)
    with EQUIVALENCE_PATH.open("a", encoding="utf-8") as handle:
        handle.write(header)
        handle.write(body)

    print(f"appended {len(entries)} entries to {EQUIVALENCE_PATH.relative_to(REPO_ROOT)}")
    print(f"  CSF 1.1 subcategories covered: {len({a for a, _ in pairs})} of {len(texts_11)}")
    print(f"  CSF 2.0 subcategories mapped back: {len({b for _, b in pairs})} of {len(texts_20)}")
    for id_20, id_11, reason in dropped:
        print(f"  DROPPED {id_20} -> {id_11}: {reason}")


if __name__ == "__main__":
    main()
