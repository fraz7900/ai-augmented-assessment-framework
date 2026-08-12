"""Framework definition loader (Sprint 3).

Loads framework_mapping/*.yaml into validated FrameworkDefinition
objects. Per ADR-0002, application code never hardcodes framework
structure — this module is the one place that reads the YAML files;
every other module (scoring_service, assessment_service, api/) consumes
FrameworkDefinition objects, never the YAML directly.

Sprint 10 (US-5.2/FR-14, ADR-0019): also loads framework_mapping/
cross_framework_equivalence.yaml and merges reviewed cross-framework
equivalents into each Practice.equivalents. Sprint 11 (ADR-0023)
generalized that file's schema from two framework-specific columns
(c2m2_practice_id/nist_subcategory_id) to a generic two-sided
framework_a/practice_a_id/framework_b/practice_b_id shape, once a
third framework (NERC CIP) had its own equivalence data to represent —
exactly the evolution ADR-0019's Consequences section predicted would
be needed "when it actually happens."
"""

from __future__ import annotations

from pathlib import Path

import yaml

from compliance_platform.models.framework import Equivalent, FrameworkDefinition

_EQUIVALENCE_FILENAME = "cross_framework_equivalence.yaml"


class FrameworkNotFoundError(Exception):
    def __init__(self, name: str, version: str | None = None) -> None:
        self.name = name
        self.version = version
        if version is None:
            super().__init__(f"No framework definition loaded for '{name}'.")
        else:
            super().__init__(f"No framework definition loaded for '{name}' version '{version}'.")


# Maps the name an Assessment.framework_name might use to the YAML
# file(s) that define it, one entry per known VERSION (Sprint 18,
# ADR-0053) — deliberately explicit rather than a filename-guessing
# convention, so a framework_name/version pair is validated against this
# registry, not against whatever happens to exist on disk. Every
# framework here has exactly one version today; the dict-of-versions
# shape exists so a future second version of a framework's YAML (a
# correction, an updated standard) can be ADDED as a new entry without
# evicting or overwriting the version(s) already there — the actual
# mechanism ADR-0031's version-pinning depends on to mean anything once
# framework content actually changes, not just a label.
#
# Version-key values are each framework's own real, loaded
# FrameworkDefinition.version string (confirmed by loading every
# framework once and reading it back — see ADR-0053) — including NERC
# CIP's genuinely non-numeric "see each domain's own source_version"
# placeholder, which is correct: NERC CIP has no single top-level
# version (each of its 13 standards has its own independent revision),
# and this registry treats version strings as opaque lookup keys, never
# parsed or compared, so that placeholder works as a key exactly like
# every other framework's real version number does.
#
# When adding a second version of a framework: APPEND a new key to that
# name's dict, never insert before or replace the existing entry(ies) —
# _latest_version() below resolves "latest" as the last-inserted key,
# not a semver comparison (these version strings aren't uniformly
# comparable across frameworks, e.g. "2.1" vs "4.0.1" vs SOC 2's prose
# string above).
# Version order within a name is significant: _latest_version takes the
# LAST key, so versions must be listed oldest-first.
_KNOWN_FRAMEWORKS: dict[str, dict[str, str]] = {
    "C2M2": {"2.1": "c2m2_v2_1.yaml"},
    # The project's first framework with two real versions (ADR-0055).
    # Until this, multi-version support (ADR-0053) had only ever run
    # against a synthetic test fixture.
    "NIST CSF": {"1.1": "nist_csf_1_1.yaml", "2.0": "nist_csf_2_0.yaml"},
    # Legacy alias, deliberately retained. Every assessment created
    # before ADR-0055 stored the literal framework_name "NIST CSF 2.0" —
    # a name with the version baked into it, which is exactly why this
    # framework could never hold two versions and why ADR-0053's
    # mechanism had nothing real to operate on. Renaming the entry would
    # orphan those rows: Assessment.framework_name is stored text, and
    # nothing resolves it through an alias table. Kept as a
    # single-version entry pointing at the same file, so old assessments
    # keep resolving exactly as before while new ones use "NIST CSF".
    "NIST CSF 2.0": {"2.0": "nist_csf_2_0.yaml"},
    "NERC CIP": {"see each domain's own source_version": "nerc_cip.yaml"},
    "ISO 27001": {"2022": "iso_27001.yaml"},
    "CIS Controls": {"8": "cis_controls_v8.yaml"},
    "SOC 2": {"2017 (criteria text, as amended March 2020)": "soc2_tsc.yaml"},
    "PCI DSS": {"4.0.1": "pci_dss_v4.yaml"},
}


def _latest_version(name: str) -> str | None:
    versions = _KNOWN_FRAMEWORKS.get(name)
    if not versions:
        return None
    return next(reversed(versions))


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
        # Keyed by (name, resolved_version), not bare name (Sprint 18,
        # ADR-0053) -- so a second version of a framework loaded later
        # doesn't evict the first, and an assessment pinned to an older
        # version keeps resolving to that exact FrameworkDefinition for
        # the life of this (process-lifetime singleton, api/dependencies.py)
        # registry instance.
        self._cache: dict[tuple[str, str], FrameworkDefinition] = {}
        self._equivalence_entries: list[dict] | None = None
        # {(framework_name, practice_id): text} — built directly from the
        # raw YAML files (not through get()/the FrameworkDefinition cache)
        # so populating one framework's equivalents never depends on the
        # other framework having been loaded first. Keyed by the pair, not
        # bare practice_id alone: several frameworks independently reuse
        # short numeric-style IDs (e.g. CIS Controls Safeguard "5.1" and
        # PCI DSS Section "5.1"), and a bare-ID index would silently let
        # one framework's entry overwrite another's, corrupting equivalence
        # data with the wrong framework name/text for the same ID string.
        self._practice_text_index: dict[tuple[str, str], str] | None = None

    def get(self, name: str, version: str | None = None) -> FrameworkDefinition | None:
        """Returns None (not an error) for a framework/version this
        registry doesn't have a schema for — e.g. an assessment labeled
        "NIST CSF 2.0" before Sprint 4 builds that schema. Callers
        decide whether an unknown framework name is acceptable; see
        services/assessment_service.py, which only validates
        practice_reference when a schema is actually available, per
        Decision D-10.

        version=None (Sprint 18, ADR-0053) resolves to whatever this
        name's registered LATEST version is — the same behavior get()
        always had before this parameter existed, so every pre-existing
        caller (framework browsing, new-assessment creation) needs no
        change. Pass an explicit version to resolve a SPECIFIC one — the
        mechanism services/assessment_service.py uses to serve an
        existing assessment its pinned Assessment.framework_version
        rather than always whatever's currently latest.
        """
        resolved_version = version if version is not None else _latest_version(name)
        if resolved_version is None:
            return None
        cache_key = (name, resolved_version)
        if cache_key in self._cache:
            return self._cache[cache_key]
        filename = _KNOWN_FRAMEWORKS.get(name, {}).get(resolved_version)
        if filename is None:
            return None
        path = self._dir / filename
        if not path.exists():
            return None
        framework = load_framework_file(path)
        self._merge_equivalents(framework)
        self._cache[cache_key] = framework
        return framework

    def require(self, name: str, version: str | None = None) -> FrameworkDefinition:
        framework = self.get(name, version)
        if framework is None:
            raise FrameworkNotFoundError(name, version)
        return framework

    def available_versions(self, name: str) -> list[str]:
        """Every version this registry knows a filename for, in the
        order they were added (last = latest, per _latest_version's own
        convention) — [] for an unrecognized name, never an error. Lets
        a caller (services/assessment_service.py.create_assessment,
        ADR-0053) distinguish "this framework_name isn't recognized at
        all" (silently tolerated, pre-existing behavior) from "it's
        recognized, but not at the specific version you asked for" (a
        real, disclosable mistake) without reaching into this registry's
        own private _KNOWN_FRAMEWORKS.
        """
        return list(_KNOWN_FRAMEWORKS.get(name, {}).keys())

    def _merge_equivalents(self, framework: FrameworkDefinition) -> None:
        entries = self._load_equivalence_entries()
        if not entries:
            return
        text_index = self._build_practice_text_index()
        for domain in framework.domains:
            for objective in domain.objectives:
                for practice in objective.practices:
                    for entry in entries:
                        other_framework_name = None
                        other_id = None
                        a_matches = (
                            entry["framework_a"] == framework.name
                            and entry["practice_a_id"] == practice.id
                        )
                        b_matches = (
                            entry["framework_b"] == framework.name
                            and entry["practice_b_id"] == practice.id
                        )
                        if a_matches:
                            other_framework_name = entry["framework_b"]
                            other_id = entry["practice_b_id"]
                        elif b_matches:
                            other_framework_name = entry["framework_a"]
                            other_id = entry["practice_a_id"]
                        if other_id is None:
                            continue
                        other_text = text_index.get((other_framework_name, other_id))
                        if other_text is None:
                            continue
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

    def _build_practice_text_index(self) -> dict[tuple[str, str], str]:
        """Every known version of every framework, keyed by the framework
        name each YAML file declares for ITSELF -- not by this registry's
        key for it (ADR-0055).

        That distinction is the whole fix. Before, this indexed each
        framework's LATEST version only, keyed by registry key, and
        ADR-0053 disclosed the consequence: a pinned older version whose
        practice ids differ from latest would not resolve its equivalents.
        NIST CSF 1.1 alongside 2.0 made that real -- the two versions
        share no practice ids at all ("ID.AM-1" vs "ID.AM-01"), so a
        1.1-pinned assessment looked up ids that the latest-only index
        had never heard of.

        Keying by the file's own `name` is what makes indexing every
        version safe rather than ambiguous: each version declares a
        distinct name ("NIST CSF 1.1" vs "NIST CSF 2.0"), so two versions
        can never collide on the same key, and equivalence entries -- which
        already reference frameworks by exactly that declared name -- keep
        resolving unchanged for every framework that has only one version.
        """
        if self._practice_text_index is not None:
            return self._practice_text_index
        index: dict[tuple[str, str], str] = {}
        # Several registry keys can point at one file (the "NIST CSF 2.0"
        # legacy alias resolves to the same YAML as "NIST CSF" 2.0), so
        # files are de-duplicated rather than parsed once per alias.
        for filename in dict.fromkeys(
            f for versions in _KNOWN_FRAMEWORKS.values() for f in versions.values()
        ):
            path = self._dir / filename
            if not path.exists():
                continue
            with path.open("r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
            declared_name = raw.get("name")
            if not declared_name:
                continue
            for domain in raw.get("domains", []):
                for objective in domain.get("objectives", []):
                    for practice in objective.get("practices", []):
                        index[(declared_name, practice["id"])] = practice["text"]
        self._practice_text_index = index
        return index
