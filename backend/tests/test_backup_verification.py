"""Backups you can prove, not just checksum (ADR-0079).

`scripts/backup.sh` writes a SHA-256 beside every archive and says why:
"a backup you cannot prove is intact is a backup you are trusting rather
than verifying." That is right and it is not enough. A checksum proves
the BYTES have not changed since the tarball was written. It says
nothing about whether the tarball contains a database that opens.

Unlike backup.sh and restore.sh -- which need Docker and a live stack,
and are therefore only read by `test_deployment_config.py` -- these two
scripts need nothing but tar, sqlite and a temp directory. So these
tests actually RUN them, including against archives corrupted in the
specific way a checksum cannot detect.
"""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
import tarfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY = REPO_ROOT / "scripts" / "verify-backup.sh"
PRUNE = REPO_ROOT / "scripts" / "prune-backups.sh"


def _run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script), *args], capture_output=True, text=True, cwd=REPO_ROOT
    )


@pytest.fixture
def volume(tmp_path: Path) -> Path:
    """A directory shaped like the real Docker volume: a SQLite database
    with the tables the product depends on, and a vector store."""
    from compliance_platform.repositories.assessment_repository import AssessmentRepository

    root = tmp_path / "volume"
    (root / "lancedb").mkdir(parents=True)
    (root / "lancedb" / "chunks.lance").write_bytes(b"not really lance, but present")
    repository = AssessmentRepository(root / "assessments.db")
    repository.create_assessment("Backed up assessment", "C2M2")
    return root


def _archive(volume: Path, destination: Path, *, checksum: bool = True) -> Path:
    archive = destination / "compliance-data-20260101T000000Z.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for entry in sorted(volume.iterdir()):
            tar.add(entry, arcname=entry.name)
    if checksum:
        digest = subprocess.run(
            ["sha256sum", archive.name],
            cwd=destination,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        (destination / f"{archive.name}.sha256").write_text(digest)
    return archive


class TestVerify:
    def test_a_good_archive_verifies(self, volume: Path, tmp_path: Path) -> None:
        result = _run(VERIFY, str(_archive(volume, tmp_path)))

        assert result.returncode == 0, result.stdout
        assert "This archive would restore." in result.stdout

    def test_it_reports_what_is_actually_in_there(self, volume: Path, tmp_path: Path) -> None:
        """Counts, not just a pass. Someone verifying a backup of real
        work wants to see the work."""
        result = _run(VERIFY, str(_archive(volume, tmp_path)))

        assert "assessment 1" in result.stdout

    def test_a_truncated_database_fails_despite_a_valid_checksum(
        self, volume: Path, tmp_path: Path
    ) -> None:
        """The case this script exists for. The bytes are intact and hash
        correctly; the database is unusable. A checksum cannot tell the
        difference and reports the archive as fine."""
        database = volume / "assessments.db"
        database.write_bytes(database.read_bytes()[:40_000])
        archive = _archive(volume, tmp_path)

        result = _run(VERIFY, str(archive))

        assert result.returncode == 1
        assert "checksum matches" in result.stdout
        assert "unusable" in result.stdout
        assert "malformed" in result.stdout
        assert "Do not rely on this archive." in result.stdout

    def test_a_missing_vector_store_fails(self, volume: Path, tmp_path: Path) -> None:
        """A database with no vector store restores into an assessment
        whose citations point at chunks that are not there -- the exact
        failure backup.sh stops the stack to avoid."""
        shutil.rmtree(volume / "lancedb")

        result = _run(VERIFY, str(_archive(volume, tmp_path)))

        assert result.returncode == 1
        assert "citations would restore pointing at nothing" in result.stdout

    def test_a_tampered_archive_stops_before_reading_it(
        self, volume: Path, tmp_path: Path
    ) -> None:
        """If the bytes moved, nothing else this script could report
        would be trustworthy, so it does not pretend to check."""
        archive = _archive(volume, tmp_path)
        archive.write_bytes(archive.read_bytes() + b"appended")

        result = _run(VERIFY, str(archive))

        assert result.returncode == 1
        assert "checksum does NOT match" in result.stdout
        assert "extracts" not in result.stdout

    def test_a_missing_sidecar_is_not_a_failure(self, volume: Path, tmp_path: Path) -> None:
        """"No checksum" and "checksum failed" are different findings.
        An archive copied without its sidecar is still worth opening."""
        result = _run(VERIFY, str(_archive(volume, tmp_path, checksum=False)))

        assert result.returncode == 0
        assert "no .sha256 sidecar" in result.stdout

    def test_an_empty_but_valid_backup_says_so(self, tmp_path: Path) -> None:
        """Restorable and empty is a real outcome, and not the one
        someone checking a backup of real work wants told quietly."""
        from compliance_platform.repositories.assessment_repository import AssessmentRepository

        root = tmp_path / "empty"
        (root / "lancedb").mkdir(parents=True)
        AssessmentRepository(root / "assessments.db")

        result = _run(VERIFY, str(_archive(root, tmp_path)))

        assert result.returncode == 0
        assert "contains no assessments" in result.stdout

    def test_something_that_is_not_a_backup_is_rejected(self, tmp_path: Path) -> None:
        stray = tmp_path / "compliance-data-20260101T000000Z.tar.gz"
        with tarfile.open(stray, "w:gz") as tar:
            note = tmp_path / "readme.txt"
            note.write_text("wrong tarball")
            tar.add(note, arcname="readme.txt")

        result = _run(VERIFY, str(stray))

        assert result.returncode == 1
        assert "not a compliance-platform backup" in result.stdout

    def test_a_missing_archive_is_a_usage_error_not_a_verdict(self, tmp_path: Path) -> None:
        """Exit 2, not 1: "you pointed me at nothing" must not read the
        same as "your backup is bad"."""
        result = _run(VERIFY, str(tmp_path / "nope.tar.gz"))
        assert result.returncode == 2


class TestPrune:
    def _archives(self, directory: Path, count: int) -> list[Path]:
        directory.mkdir(parents=True, exist_ok=True)
        made = []
        for day in range(1, count + 1):
            archive = directory / f"compliance-data-202601{day:02d}T000000Z.tar.gz"
            archive.write_bytes(b"archive")
            (directory / f"{archive.name}.sha256").write_text("x")
            made.append(archive)
        return made

    def test_it_deletes_nothing_without_apply(self, tmp_path: Path) -> None:
        """Deleting a backup is the second most destructive thing in this
        repository. A dry run is the default for the same reason
        restore.sh has no --force."""
        self._archives(tmp_path / "backups", 5)

        result = _run(PRUNE, "--keep", "2", str(tmp_path / "backups"))

        assert result.returncode == 0
        assert "Nothing was deleted" in result.stdout
        assert len(list((tmp_path / "backups").glob("*.tar.gz"))) == 5

    def test_apply_keeps_the_newest_and_removes_the_rest(self, tmp_path: Path) -> None:
        directory = tmp_path / "backups"
        self._archives(directory, 5)

        result = _run(PRUNE, "--keep", "2", "--apply", str(directory))

        assert result.returncode == 0
        remaining = sorted(p.name for p in directory.glob("*.tar.gz"))
        assert remaining == [
            "compliance-data-20260104T000000Z.tar.gz",
            "compliance-data-20260105T000000Z.tar.gz",
        ]

    def test_it_removes_the_checksum_sidecar_too(self, tmp_path: Path) -> None:
        """An orphaned .sha256 would make the next verification of a
        deleted archive fail confusingly."""
        directory = tmp_path / "backups"
        self._archives(directory, 3)

        _run(PRUNE, "--keep", "1", "--apply", str(directory))

        assert len(list(directory.glob("*.sha256"))) == 1

    def test_keep_is_required(self, tmp_path: Path) -> None:
        """How many copies of an audit record you are willing to lose is
        not a decision a default should make."""
        self._archives(tmp_path / "backups", 3)

        result = _run(PRUNE, str(tmp_path / "backups"))

        assert result.returncode == 2
        assert "--keep N is required" in result.stderr

    def test_keeping_zero_is_refused(self, tmp_path: Path) -> None:
        self._archives(tmp_path / "backups", 3)

        result = _run(PRUNE, "--keep", "0", "--apply", str(tmp_path / "backups"))

        assert result.returncode == 2
        assert len(list((tmp_path / "backups").glob("*.tar.gz"))) == 3

    def test_fewer_archives_than_the_limit_removes_nothing(self, tmp_path: Path) -> None:
        directory = tmp_path / "backups"
        self._archives(directory, 2)

        result = _run(PRUNE, "--keep", "7", "--apply", str(directory))

        assert result.returncode == 0
        assert "Nothing to remove." in result.stdout
        assert len(list(directory.glob("*.tar.gz"))) == 2

    def test_it_ignores_files_that_are_not_backups(self, tmp_path: Path) -> None:
        directory = tmp_path / "backups"
        self._archives(directory, 3)
        (directory / "notes.txt").write_text("keep me")

        _run(PRUNE, "--keep", "1", "--apply", str(directory))

        assert (directory / "notes.txt").exists()


def test_the_verified_database_is_never_written_to(tmp_path: Path) -> None:
    """It opens the extracted copy read-only, and the extraction is
    deleted. Verifying a backup must not be able to change one."""
    from compliance_platform.repositories.assessment_repository import AssessmentRepository

    root = tmp_path / "volume"
    (root / "lancedb").mkdir(parents=True)
    AssessmentRepository(root / "assessments.db")
    archive = _archive(root, tmp_path)
    before = archive.read_bytes()

    _run(VERIFY, str(archive))

    assert archive.read_bytes() == before
    assert sqlite3.connect(root / "assessments.db").execute("PRAGMA integrity_check").fetchone()[
        0
    ] == "ok"


# ---- One command worth scheduling (ADR-0083) ----
#
# ADR-0079 ended by saying "what this offers is a command worth
# scheduling" and did not provide one, so operating this well meant
# knowing to run three scripts in the right order. The order carries the
# whole safety property, so it is worth a test rather than a paragraph.

SCHEDULED = REPO_ROOT / "scripts" / "scheduled-backup.sh"


class TestScheduledBackup:
    def test_it_verifies_before_it_prunes(self) -> None:
        """The ordering IS the safety property. Backing up and then
        deleting older copies without checking the new one is how a
        directory of good backups becomes a directory of one bad one."""
        script = SCHEDULED.read_text("utf-8")

        # Anchored on the invocations, not on any mention: both scripts
        # are named in the header comment too, and the first draft of
        # this test compared a comment against a command.
        verify_at = script.index('"$SCRIPTS/verify-backup.sh"')
        prune_at = script.index('"$SCRIPTS/prune-backups.sh"')

        assert verify_at < prune_at, "pruning must not precede verification"

    def test_a_failed_verification_stops_before_pruning(self) -> None:
        """And says why, because the operator reading a cron log at 2am
        needs to know the old archives are still there."""
        script = SCHEDULED.read_text("utf-8")

        assert "NOTHING has been pruned" in script
        assert "exit 1" in script

    def test_keep_is_still_required(self) -> None:
        """Passed through to prune-backups.sh, which refuses to guess a
        retention count. A wrapper must not quietly supply one."""
        result = _run(SCHEDULED)

        assert result.returncode == 2
        assert "--keep N is required" in result.stderr

    def test_it_documents_the_host_cron_line(self) -> None:
        """A command worth scheduling is worth showing how to schedule."""
        script = SCHEDULED.read_text("utf-8")

        assert "cron" in script.lower()
        assert "scheduled-backup.sh --keep" in script

    def test_it_explains_why_this_is_not_a_container(self) -> None:
        """The obvious implementation -- a scheduler service in the
        compose stack -- needs the docker socket mounted, which is
        root-equivalent access in a long-running service on a product
        whose posture is that the deployment must not be exposed. That
        reasoning has to survive in the file, or someone will helpfully
        containerise it."""
        script = SCHEDULED.read_text("utf-8")

        assert "docker socket" in script
        assert "root-equivalent" in script
