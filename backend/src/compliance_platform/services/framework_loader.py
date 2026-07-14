"""Framework definition loader (Sprint 3).

Loads framework_mapping/*.yaml into validated FrameworkDefinition
objects. Per ADR-0002, application code never hardcodes framework
structure — this module is the one place that reads the YAML files;
every other module (scoring_service, assessment_service, api/) consumes
FrameworkDefinition objects, never the YAML directly.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from compliance_platform.models.framework import FrameworkDefinition


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
        self._cache[name] = framework
        return framework

    def require(self, name: str) -> FrameworkDefinition:
        framework = self.get(name)
        if framework is None:
            raise FrameworkNotFoundError(name)
        return framework
