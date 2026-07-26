"""Unit tests for Settings (Sprint 18, ADR-0045: cors_allowed_origins
became configurable rather than hardcoded in main.py).
"""

from __future__ import annotations

import pytest

from compliance_platform.core.config import Settings


def test_cors_allowed_origins_defaults_to_the_local_vite_dev_server() -> None:
    settings = Settings()
    assert settings.cors_allowed_origins == (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )


def test_cors_allowed_origins_is_overridable_via_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "COMPLIANCE_PLATFORM_CORS_ALLOWED_ORIGINS",
        '["https://compliance.example.org"]',
    )
    settings = Settings()
    assert settings.cors_allowed_origins == ("https://compliance.example.org",)
