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
        if line.strip()
        and not line.strip().startswith("#")
        and not line.strip().startswith("--hash=")
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
    # The flags around it changed when hashes arrived (ADR-0081), so this
    # asserts the requirement rather than one exact spelling of it.
    assert re.search(r"pip install .*--requirement requirements\.lock", commands)
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


# ---- The interpreters are declared once (ADR-0080) ----
#
# Four places name a Python and a Node version: the two Dockerfiles, the
# CI workflow, and now .python-version / .nvmrc. Before this, the only
# thing holding them together was a comment saying "matches
# deployment/backend.Dockerfile" -- which becomes false at exactly the
# moment it matters, silently.

NVMRC = REPO_ROOT / ".nvmrc"
PYTHON_VERSION_FILE = REPO_ROOT / ".python-version"
BACKEND_DOCKERFILE = REPO_ROOT / "deployment" / "backend.Dockerfile"
FRONTEND_DOCKERFILE = REPO_ROOT / "deployment" / "frontend.Dockerfile"


def _declared(path: Path) -> str:
    return path.read_text("utf-8").strip()


def test_the_version_files_exist_and_name_one_version_each() -> None:
    for path in (NVMRC, PYTHON_VERSION_FILE):
        assert path.is_file(), f"{path.name} is what nvm/pyenv read to pick a version"
        assert re.fullmatch(r"\d+(\.\d+)?", _declared(path)), (
            f"{path.name} should hold a bare version, got {_declared(path)!r}"
        )


def test_the_backend_dockerfile_agrees_with_python_version() -> None:
    """A version file the production image ignores would be worse than
    no version file: it would look authoritative and be wrong."""
    declared = _declared(PYTHON_VERSION_FILE)
    dockerfile = BACKEND_DOCKERFILE.read_text("utf-8")

    match = re.search(r"^FROM python:(\d+\.\d+)", dockerfile, re.MULTILINE)
    assert match, "could not find the python base image in backend.Dockerfile"
    assert match.group(1) == declared, (
        f"backend.Dockerfile builds on python {match.group(1)}, "
        f".python-version declares {declared}"
    )


def test_the_frontend_dockerfile_agrees_with_nvmrc() -> None:
    declared = _declared(NVMRC)
    dockerfile = FRONTEND_DOCKERFILE.read_text("utf-8")

    match = re.search(r"^FROM node:(\d+)", dockerfile, re.MULTILINE)
    assert match, "could not find the node base image in frontend.Dockerfile"
    assert match.group(1) == declared, (
        f"frontend.Dockerfile builds on node {match.group(1)}, .nvmrc declares {declared}"
    )


def test_ci_reads_the_version_files_rather_than_repeating_them() -> None:
    """The declaration cannot drift from itself. A literal in the
    workflow can, and did nothing to announce it."""
    commands = _ci_commands()

    assert "python-version-file: .python-version" in commands
    assert "node-version-file: .nvmrc" in commands
    assert not re.search(r'python-version:\s*"', commands), "CI still hardcodes a python version"
    assert not re.search(r'node-version:\s*"', commands), "CI still hardcodes a node version"


def test_bootstrap_checks_the_declared_version_not_the_floor() -> None:
    """3.11 satisfies pyproject's requires-python and is not what this
    project ships on. Accepting it produces the half-right environment
    ADR-0075 exists to prevent."""
    bootstrap = BOOTSTRAP.read_text("utf-8")

    assert ".python-version" in bootstrap
    assert ".nvmrc" in bootstrap
    assert "3, 11" not in bootstrap, "bootstrap still checks the pyproject floor"


def test_the_doctor_reports_an_interpreter_mismatch() -> None:
    doctor = DOCTOR.read_text("utf-8")

    assert ".python-version" in doctor
    assert ".nvmrc" in doctor


# ---- Every artifact is hash-verified (ADR-0081) ----
#
# Version pinning makes the build reproducible. Hash pinning makes it
# verifiable: pip refuses any artifact whose bytes differ from the one
# recorded. That defends the charter's central claim rather than just the
# build -- evidence never leaves local infrastructure "by construction",
# and a substituted dependency would break that silently on a machine
# holding real evidence.


def test_every_pin_carries_a_hash() -> None:
    """--require-hashes refuses the whole file if even one requirement
    lacks a hash, so a single missing line turns the guarantee off
    entirely rather than weakening it."""
    pins, hashes = 0, 0
    for line in LOCK.read_text("utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if stripped.startswith("--hash="):
            hashes += 1
        elif "==" in stripped:
            pins += 1

    assert pins > 0
    assert hashes == pins, f"{pins} pinned packages but {hashes} hashes"


def test_the_hashes_are_well_formed_sha256() -> None:
    digests = re.findall(r"--hash=sha256:([0-9a-f]*)", LOCK.read_text("utf-8"))

    assert digests
    for digest in digests:
        assert len(digest) == 64, f"not a sha256 digest: {digest!r}"


def test_bootstrap_and_ci_both_require_hashes() -> None:
    """A hash nobody verifies is a comment. Both install paths have to
    ask pip to enforce it, or the lock records an intention."""
    assert "--require-hashes" in BOOTSTRAP.read_text("utf-8")
    assert "--require-hashes" in _ci_commands()


def test_the_lock_explains_what_the_hashes_are_for() -> None:
    """A generated file that does not say why it looks like this gets
    simplified back by someone trying to help."""
    header = LOCK.read_text("utf-8")[:2000]

    assert "--require-hashes" in header
    assert "lock-backend.sh" in header


def test_lock_regeneration_produces_hashes() -> None:
    """If the regeneration script emitted bare versions, the next routine
    dependency bump would silently drop hash verification for everything."""
    script = LOCK_SCRIPT.read_text("utf-8")

    assert "pip download" in script, "hashes must come from the artifacts actually resolved"
    assert "sha256" in script


def test_the_doctor_can_still_read_a_hashed_lock() -> None:
    """It parses the lock to detect drift, and a pin is now written
    across two lines with a trailing backslash. The first version of this
    change reported all 75 packages as drifted."""
    doctor = DOCTOR.read_text("utf-8")

    assert '--hash=' in doctor, "the doctor must skip hash lines when parsing pins"
