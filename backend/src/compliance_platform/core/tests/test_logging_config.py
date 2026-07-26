"""Unit tests for configure_logging (security hardening, controlled-pilot
readiness audit §A.12).
"""

from __future__ import annotations

import logging

from compliance_platform.core.config import Settings
from compliance_platform.core.logging_config import configure_logging


def test_configure_logging_sets_root_level_from_settings() -> None:
    configure_logging(Settings(log_level="WARNING"))
    try:
        assert logging.getLogger().level == logging.WARNING
    finally:
        configure_logging(Settings(log_level="INFO"))  # restore for other tests in the process


def test_configure_logging_defaults_to_info() -> None:
    configure_logging(Settings())
    assert logging.getLogger().level == logging.INFO
