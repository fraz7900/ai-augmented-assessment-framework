"""The environment is reproducible, and the lock is not decorative
(ADR-0075).

R-9 has been open since Sprint 1 and is the only High-likelihood risk in
the register that has already occurred. The scripts are shell, so this
cannot meaningfully run them in CI. What it CAN check is the thing that
actually rots: that the lock still describes the environment, that CI
still installs from it, and that the doctor still knows what it is
looking for.

That last one matters more than it sounds. This repository has been
bitten by a documented capability with nothing behind it before (the
sanitization pipeline, ADR-0032), and a bootstrap script that has
quietly stopped matching CI is the same failure wearing overalls.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCK = REPO_ROOT / "backend" / "requirements.lock"
BOOTSTRAP = REPO_ROOT / "scripts" / "bootstrap.sh"
DOCTOR = REPO_ROOT / "scripts" / "doctor.sh"
LOCK_SCRIPT = REPO_ROOT / "scripts" / "lock-backend.sh"
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PYPROJECT = REPO_ROOT / "backend" / "pyproject.toml"


def _pinned() -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in LOCK.read_text("utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "==" in line:
            name, _, version = line.partition("==")
            pins[name.lower().replace("_", "-")] = version
    return pins


def test_every_shell_script_is_executable_in_git() -> None:
    """Checked against git's index, not the filesystem.

    This working copy lives on NTFS via WSL, where every file reports
    mode 777 and `chmod +x` is a no-op -- so the local filesystem cannot
    answer this question, and CI caught the first version of these
    scripts committed as 100644. A cloner would have received scripts
    they could not run, including the one bootstrap.sh itself calls.

    Covers the whole directory rather than a list, because the same
    mistake was already sitting in install-git-hooks.sh, which AGENTS.md
    tells people to run directly.
    """
    listing = subprocess.run(
        ["git", "ls-files", "-s", "scripts/"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    non_executable = [
        line.split("\t", 1)[1]
        for line in listing.splitlines()
        if line.endswith(".sh") and not line.startswith("100755")
    ]
    assert not non_executable, f"committed without the executable bit: {non_executable}"


def test_the_scripts_this_adr_adds_exist() -> None:
    for script in (BOOTSTRAP, DOCTOR, LOCK_SCRIPT):
        assert script.is_file(), f"{script.name} is referenced by AGENTS.md and ADR-0075"


def test_the_lock_pins_every_version_exactly() -> None:
    """A single ">=" in here would defeat the whole point: the file
    exists because pyproject.toml's floors resolve differently over
    time."""
    body = [
        line.strip()
        for line in LOCK.read_text("utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert body, "the lock has no pins at all"
    for line in body:
        assert "==" in line, f"unpinned requirement in the lock: {line}"
        assert not re.search(r">=|<=|~=|>|<", line), f"range specifier in the lock: {line}"


def test_every_declared_dependency_is_pinned_in_the_lock() -> None:
    """The lock has to cover what pyproject actually declares, or a
    direct dependency resolves fresh while everything around it is
    pinned -- which looks reproducible and is not."""
    declared = set(
        re.findall(r'^\s*"([A-Za-z0-9_.-]+)\s*[><=]', PYPROJECT.read_text("utf-8"), re.MULTILINE)
    )
    assert declared, "could not read dependencies out of pyproject.toml"
    pins = _pinned()
    missing = sorted(
        name for name in declared if name.lower().replace("_", "-") not in pins
    )
    assert not missing, f"declared but not pinned: {missing}"


def _ci_commands() -> str:
    """CI with its YAML comments stripped.

    The first version of the test below matched the raw file and failed
    on the explanatory comment that quotes the old command -- a test
    that can be defeated, or tripped, by a comment is checking the wrong
    thing. What matters is what CI RUNS.
    """
    return "\n".join(
        line.split("#", 1)[0] for line in CI.read_text("utf-8").splitlines()
    )


def test_ci_installs_from_the_lock_rather_than_resolving() -> None:
    """A lock nothing installs from records history rather than
    controlling it."""
    commands = _ci_commands()
    assert "requirements.lock" in commands, "CI does not reference the lock"
    assert "pip install --requirement requirements.lock" in commands
    # The project itself must go in without deps, or pip re-resolves and
    # can upgrade straight past the pins it just installed.
    assert "--no-deps --editable ." in commands
    assert 'pip install -e ".[dev]"' not in commands, "CI still resolves dependencies fresh"


def test_ci_caches_on_the_lock_not_on_pyproject() -> None:
    """Keying the cache on pyproject.toml would restore a stale wheel set
    whenever the lock changed but the declarations did not -- which is
    every routine dependency bump."""
    assert "cache-dependency-path: backend/requirements.lock" in _ci_commands()


def test_bootstrap_consumes_the_lock_and_does_not_regenerate_it() -> None:
    """Bootstrap and lock-regeneration are deliberately separate. If
    setup regenerated the lock, every developer would silently adopt
    whatever PyPI served that morning -- which is R-9, not a fix for
    it."""
    bootstrap = BOOTSTRAP.read_text("utf-8")
    assert "requirements.lock" in bootstrap
    assert "pip freeze" not in bootstrap, "bootstrap must not regenerate the lock"
    assert "npm ci" in bootstrap, "npm install would not honour package-lock.json"
    assert "--legacy-peer-deps" in bootstrap, "a real peer conflict, see ADR-0016"


def test_the_doctor_checks_the_failure_agents_md_documents() -> None:
    """The one AGENTS.md spends the most words on: a node_modules that
    looks installed, is incomplete, and presents as vitest worker-startup
    errors rather than as an install problem. Checking the directory
    exists would not catch it; `npm ls` inspects the tree."""
    doctor = DOCTOR.read_text("utf-8")
    assert "npm ls" in doctor
    assert "requirements.lock" in doctor, "the doctor must detect backend drift too"


def test_the_doctor_reports_environment_faults_through_its_exit_code() -> None:
    """It has to be usable in a script and in CI, not just readable by a
    human."""
    doctor = DOCTOR.read_text("utf-8")
    assert "exit 1" in doctor and "exit 0" in doctor


def test_the_lock_says_how_to_regenerate_it() -> None:
    """A generated file that does not say how it was generated becomes
    hand-edited eventually."""
    header = LOCK.read_text("utf-8")[:1600]
    assert "GENERATED" in header
    assert "lock-backend.sh" in header
