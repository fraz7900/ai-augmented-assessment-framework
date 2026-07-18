"""Framework definition loader (Sprint 3).

Loads framework_mapping/*.yaml into validated FrameworkDefinition
objects. Per ADR-0002, application code never hardcodes framework
structure — this module is the one place that reads the YAML files;
every other module (scoring_service, assessment_service, api/) consumes
FrameworkDefinition objects, never the YAML directly.

Sprint 10 (US-5.2/FR-14, ADR-0019): also loads framework_mapping/
cross_framework_equivalence.yaml and merges reviewed cross-framework
equivalents into each Practice.equivalents. That file's two column
names (c2m2_practice_id/nist_subcategory_id) hardcode exactly the two
frameworks this project has today — a real, disclosed limitation, not
an oversight (see ADR-0019's Consequences): adding a third framework
with its own equivalence data would need this loader generalized, not
just another column.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from compliance_platform.models.framework import Equivalent, FrameworkDefinition

_EQUIVALENCE_FILENAME = "cross_framework_equivalence.yaml"


class FrameworkNotFoundError(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"No framework definition loaded for '{name}'.")


# Maps the name an Assessment.framework_name might use to the YAML file
# that defines it. Deliberately explicit rather than a filename-guessing
# convention, so a framework_name is validated against this registry,
# not against whatever happens to exist on disk.
_KNOWN_FRAMEWORKS: dict[str, str] = {
    "C2M2": "c2m2_v2_1.yaml",
    "NIST CSF 2.0": "nist_csf_2_0.yaml",
    "NERC CIP": "nerc_cip.yaml",
}


def load_framework_file(path: Path) -> FrameworkDefinition:
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return FrameworkDefinition.model_validate(raw)


class FrameworkRegistry:
    """Loads and caches framework definitions from framework_mapping/.

    A registry instance, not a bare module-level cache, so tests can
    construct one pointed at a fixture directory instead of the real
    framework_mapping/.
    """

    def __init__(self, framework_mapping_dir: Path) -> None:
        self._dir = framework_mapping_dir
        self._cache: dict[str, FrameworkDefinition] = {}
        self._equivalence_entries: list[dict] | None = None
        # {practice_id: (framework_name, text)} — built directly from the
        # raw YAML files (not through get()/the FrameworkDefinition cache)
        # so populating one framework's equivalents never depends on the
        # other framework having been loaded first.
        self._practice_text_index: dict[str, tuple[str, str]] | None = None

    def get(self, name: str) -> FrameworkDefinition | None:
        """Returns None (not an error) for a framework this registry
        doesn't have a schema for — e.g. an assessment labeled "NIST CSF
        2.0" before Sprint 4 builds that schema. Callers decide whether
        an unknown framework name is acceptable; see
        services/assessment_service.py, which only validates
        practice_reference when a schema is actually available, per
        Decision D-10.
        """
        if name in self._cache:
            return self._cache[name]
        filename = _KNOWN_FRAMEWORKS.get(name)
        if filename is None:
            return None
        path = self._dir / filename
        if not path.exists():
            return None
        framework = load_framework_file(path)
        self._merge_equivalents(framework)
        self._cache[name] = framework
        return framework

    def require(self, name: str) -> FrameworkDefinition:
        framework = self.get(name)
        if framework is None:
            raise FrameworkNotFoundError(name)
        return framework

    def _merge_equivalents(self, framework: FrameworkDefinition) -> None:
        entries = self._load_equivalence_entries()
        if not entries:
            return
        text_index = self._build_practice_text_index()
        for domain in framework.domains:
            for objective in domain.objectives:
                for practice in objective.practices:
                    for entry in entries:
                        other_id = None
                        if entry["c2m2_practice_id"] == practice.id:
                            other_id = entry["nist_subcategory_id"]
                        elif entry["nist_subcategory_id"] == practice.id:
                            other_id = entry["c2m2_practice_id"]
                        if other_id is None:
                            continue
                        other = text_index.get(other_id)
                        if other is None:
                            continue
                        other_framework_name, other_text = other
                        practice.equivalents.append(
                            Equivalent(
                                framework_name=other_framework_name,
                                practice_id=other_id,
                                practice_text=other_text,
                                similarity=entry["similarity"],
                                rationale=entry["rationale"],
                            )
                        )

    def _load_equivalence_entries(self) -> list[dict]:
        if self._equivalence_entries is not None:
            return self._equivalence_entries
        path = self._dir / _EQUIVALENCE_FILENAME
        if not path.exists():
            self._equivalence_entries = []
            return self._equivalence_entries
        with path.open("r", encoding="utf-8") as f:
            self._equivalence_entries = yaml.safe_load(f) or []
        return self._equivalence_entries

    def _build_practice_text_index(self) -> dict[str, tuple[str, str]]:
        if self._practice_text_index is not None:
            return self._practice_text_index
        index: dict[str, tuple[str, str]] = {}
        for name, filename in _KNOWN_FRAMEWORKS.items():
            path = self._dir / filename
            if not path.exists():
                continue
            with path.open("r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
            for domain in raw.get("domains", []):
                for objective in domain.get("objectives", []):
                    for practice in objective.get("practices", []):
                        index[practice["id"]] = (name, practice["text"])
        self._practice_text_index = index
        return index
