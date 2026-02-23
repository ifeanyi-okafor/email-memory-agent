# tests/test_config.py
#
# Tests for configuration constants — validates all new settings exist
# and have sensible values.

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import (
    EMAIL_BATCH_SIZE,
    API_MAX_RETRIES,
    API_RETRY_BASE_DELAY,
    DEFAULT_MAX_EMAILS,
    DEFAULT_DAYS_BACK,
    MEMORY_TYPES,
)


class TestConfigConstants:
    """Validate configuration values."""

    def test_batch_size_is_positive(self):
        assert EMAIL_BATCH_SIZE > 0

    def test_batch_size_is_reasonable(self):
        """Batch size should be between 1 and 50 (practical range)."""
        assert 1 <= EMAIL_BATCH_SIZE <= 50

    def test_max_retries_is_positive(self):
        assert API_MAX_RETRIES > 0

    def test_max_retries_is_reasonable(self):
        """More than 10 retries would wait too long with exponential backoff."""
        assert API_MAX_RETRIES <= 10

    def test_retry_base_delay_is_positive(self):
        assert API_RETRY_BASE_DELAY > 0

    def test_retry_base_delay_is_reasonable(self):
        """Base delay should be between 0.1s and 10s."""
        assert 0.1 <= API_RETRY_BASE_DELAY <= 10.0

    def test_max_backoff_time(self):
        """Total worst-case wait should be under 10 minutes (generous for resilience)."""
        total_wait = sum(
            API_RETRY_BASE_DELAY * (2 ** i) for i in range(API_MAX_RETRIES - 1)
        )
        assert total_wait < 600  # seconds — allows for long overload periods

    def test_default_max_emails_reasonable(self):
        """Default max emails should be between 1 and 500."""
        assert 1 <= DEFAULT_MAX_EMAILS <= 500

    def test_default_days_back_reasonable(self):
        """Default days back should be between 1 and 365."""
        assert 1 <= DEFAULT_DAYS_BACK <= 365

    def test_memory_types_not_empty(self):
        assert len(MEMORY_TYPES) > 0

    def test_memory_types_includes_people(self):
        assert 'people' in MEMORY_TYPES

    def test_batch_size_less_than_max_emails(self):
        """Batch size should be smaller than max emails (otherwise batching is pointless)."""
        assert EMAIL_BATCH_SIZE <= DEFAULT_MAX_EMAILS
