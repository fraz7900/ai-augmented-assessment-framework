from __future__ import annotations

from pathlib import Path

from compliance_platform.core.config import Settings
from compliance_platform.services import original_store


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    defaults: dict[str, object] = {"data_raw_dir": tmp_path / "raw"}
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


def test_original_is_retained_and_found_again_by_document_id(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    path = original_store.store(settings, "doc-1", "access_policy.pdf", b"real bytes")
    assert path is not None
    assert path.read_bytes() == b"real bytes"
    assert original_store.path_for(settings, "doc-1") == path


def test_retention_can_be_disabled(tmp_path: Path) -> None:
    settings = _settings(tmp_path, retain_original_uploads=False)
    assert original_store.store(settings, "doc-1", "policy.pdf", b"bytes") is None
    assert original_store.path_for(settings, "doc-1") is None


def test_path_for_returns_none_when_nothing_was_retained(tmp_path: Path) -> None:
    # The common real case: every document ingested before retention
    # existed. Must be a quiet None, not an error.
    assert original_store.path_for(_settings(tmp_path), "never-ingested") is None


def test_a_traversing_filename_cannot_escape_the_store(tmp_path: Path) -> None:
    """`filename` comes from an upload. This is a security boundary, not
    tidiness -- the written file must stay inside data_raw_dir whatever
    the upload calls itself.
    """
    settings = _settings(tmp_path)
    path = original_store.store(settings, "doc-1", "../../etc/passwd", b"bytes")
    assert path is not None
    assert path.parent == settings.data_raw_dir
    assert path.read_bytes() == b"bytes"


def test_two_documents_with_the_same_filename_do_not_collide(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    first = original_store.store(settings, "doc-1", "policy.pdf", b"first")
    second = original_store.store(settings, "doc-2", "policy.pdf", b"second")
    assert first != second
    assert first is not None and first.read_bytes() == b"first"
    assert second is not None and second.read_bytes() == b"second"


def test_content_hash_matches_the_parsers_own_hash(tmp_path: Path) -> None:
    """Re-ingestion checks a retained file against Document.content_hash
    before rebuilding anything from it, so the two hashes must be the
    same function.
    """
    from compliance_platform.services import document_parsers

    content = b"some evidence content"
    assert original_store.content_hash(content) == document_parsers._content_hash(content)


def test_delete_removes_a_retained_original(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    original_store.store(settings, "doc-1", "policy.pdf", b"bytes")
    assert original_store.delete(settings, "doc-1") is True
    assert original_store.path_for(settings, "doc-1") is None
    assert original_store.delete(settings, "doc-1") is False  # already gone
