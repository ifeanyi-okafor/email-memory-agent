# tests/test_batching.py
#
# Tests for email batch splitting and the orchestrator's batched build_memory flow.
# Mocks Gmail fetching and agent runs to test orchestration logic in isolation.

import json
import math
import pytest
from unittest.mock import patch, MagicMock, call

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def _make_fake_emails(count: int) -> list[dict]:
    """Generate a list of fake email dicts for testing."""
    return [
        {
            "id": f"msg_{i}",
            "thread_id": f"thread_{i}",
            "subject": f"Test Email {i}",
            "from": f"person{i}@example.com",
            "from_email": f"person{i}@example.com",
            "from_name": f"Person {i}",
            "to": "me@example.com",
            "date": f"2026-02-{(i % 28) + 1:02d}",
            "snippet": f"Snippet for email {i}",
            "body": f"Body of email {i} with some content about project {i}.",
            "labels": ["INBOX"]
        }
        for i in range(count)
    ]


class TestBatchSplitting:
    """Test that emails are correctly split into batches."""

    def test_batch_count_exact_division(self):
        """20 emails / batch_size 10 = exactly 2 batches."""
        emails = _make_fake_emails(20)
        batch_size = 10
        total = math.ceil(len(emails) / batch_size)
        assert total == 2

    def test_batch_count_remainder(self):
        """25 emails / batch_size 10 = 3 batches (last batch has 5)."""
        emails = _make_fake_emails(25)
        batch_size = 10
        total = math.ceil(len(emails) / batch_size)
        assert total == 3

    def test_batch_count_single_email(self):
        """1 email = 1 batch."""
        emails = _make_fake_emails(1)
        batch_size = 10
        total = math.ceil(len(emails) / batch_size)
        assert total == 1

    def test_batch_count_exact_batch_size(self):
        """10 emails / batch_size 10 = exactly 1 batch."""
        emails = _make_fake_emails(10)
        batch_size = 10
        total = math.ceil(len(emails) / batch_size)
        assert total == 1

    def test_batch_slicing_preserves_all_emails(self):
        """Every email appears in exactly one batch, none lost."""
        emails = _make_fake_emails(23)
        batch_size = 10
        total_batches = math.ceil(len(emails) / batch_size)

        all_batched = []
        for idx in range(total_batches):
            start = idx * batch_size
            end = start + batch_size
            batch = emails[start:end]
            all_batched.extend(batch)

        assert len(all_batched) == 23
        assert all_batched == emails

    def test_batch_sizes(self):
        """23 emails / batch_size 10 → batches of [10, 10, 3]."""
        emails = _make_fake_emails(23)
        batch_size = 10
        total_batches = math.ceil(len(emails) / batch_size)

        sizes = []
        for idx in range(total_batches):
            start = idx * batch_size
            end = start + batch_size
            batch = emails[start:end]
            sizes.append(len(batch))

        assert sizes == [10, 10, 3]


class TestOrchestratorBuildMemory:
    """Test the orchestrator's build_memory method with mocked dependencies."""

    @patch('orchestrator.get_vault_stats', return_value={"total": 5, "people": 3, "decisions": 1, "commitments": 1})
    @patch('orchestrator.fetch_emails')
    def test_build_memory_calls_fetch_emails(self, mock_fetch, mock_stats):
        """build_memory should call fetch_emails with correct parameters."""
        mock_fetch.return_value = _make_fake_emails(5)

        from orchestrator import Orchestrator
        with patch.object(Orchestrator, '__init__', lambda self: None):
            orch = Orchestrator()
            orch.email_reader = MagicMock()
            orch.email_reader.analyze_batch.return_value = '{"observations": []}'
            orch.memory_writer = MagicMock()
            orch.memory_writer.run.return_value = "Done"

            orch.build_memory("test", max_emails=25, days_back=14, gmail_query="is:important")

        mock_fetch.assert_called_once_with(max_results=25, query="is:important", days_back=14)

    @patch('orchestrator.get_vault_stats', return_value={"total": 0})
    @patch('orchestrator.fetch_emails')
    def test_build_memory_no_emails_returns_early(self, mock_fetch, mock_stats):
        """When no emails are found, return early without calling agents."""
        mock_fetch.return_value = []

        from orchestrator import Orchestrator
        with patch.object(Orchestrator, '__init__', lambda self: None):
            orch = Orchestrator()
            orch.email_reader = MagicMock()
            orch.memory_writer = MagicMock()

            result = orch.build_memory("test")

        assert "No emails found" in result
        orch.email_reader.analyze_batch.assert_not_called()
        orch.memory_writer.run.assert_not_called()

    @patch('orchestrator.EMAIL_BATCH_SIZE', 10)
    @patch('orchestrator.get_vault_stats', return_value={"total": 5, "people": 3, "decisions": 2})
    @patch('orchestrator.fetch_emails')
    def test_build_memory_correct_batch_count(self, mock_fetch, mock_stats):
        """25 emails / batch 10 → analyze_batch called 3 times."""
        mock_fetch.return_value = _make_fake_emails(25)

        from orchestrator import Orchestrator
        with patch.object(Orchestrator, '__init__', lambda self: None):
            orch = Orchestrator()
            orch.email_reader = MagicMock()
            orch.email_reader.analyze_batch.return_value = '{"observations": []}'
            orch.memory_writer = MagicMock()
            orch.memory_writer.reset = MagicMock()
            orch.memory_writer.run.return_value = "Wrote 5 memories"

            orch.build_memory("test", max_emails=25)

        assert orch.email_reader.analyze_batch.call_count == 3

    @patch('orchestrator.EMAIL_BATCH_SIZE', 10)
    @patch('orchestrator.get_vault_stats', return_value={"total": 3, "people": 2, "decisions": 1})
    @patch('orchestrator.fetch_emails')
    def test_build_memory_batch_numbers_correct(self, mock_fetch, mock_stats):
        """Verify batch_num and total_batches passed correctly to analyze_batch."""
        mock_fetch.return_value = _make_fake_emails(25)

        from orchestrator import Orchestrator
        with patch.object(Orchestrator, '__init__', lambda self: None):
            orch = Orchestrator()
            orch.email_reader = MagicMock()
            orch.email_reader.analyze_batch.return_value = '{"observations": []}'
            orch.memory_writer = MagicMock()
            orch.memory_writer.reset = MagicMock()
            orch.memory_writer.run.return_value = "Done"

            orch.build_memory("test", max_emails=25)

        # Verify batch numbers: (batch_json, 1, 3), (batch_json, 2, 3), (batch_json, 3, 3)
        calls = orch.email_reader.analyze_batch.call_args_list
        for i, c in enumerate(calls):
            _, batch_num, total_batches = c.args
            assert batch_num == i + 1
            assert total_batches == 3

    @patch('orchestrator.EMAIL_BATCH_SIZE', 5)
    @patch('orchestrator.get_vault_stats', return_value={"total": 2, "people": 2})
    @patch('orchestrator.fetch_emails')
    def test_build_memory_batch_sizes_in_json(self, mock_fetch, mock_stats):
        """Verify each batch has the right number of emails in the JSON."""
        mock_fetch.return_value = _make_fake_emails(12)

        from orchestrator import Orchestrator
        with patch.object(Orchestrator, '__init__', lambda self: None):
            orch = Orchestrator()
            orch.email_reader = MagicMock()
            orch.email_reader.analyze_batch.return_value = '{"observations": []}'
            orch.memory_writer = MagicMock()
            orch.memory_writer.reset = MagicMock()
            orch.memory_writer.run.return_value = "Done"

            orch.build_memory("test", max_emails=12)

        calls = orch.email_reader.analyze_batch.call_args_list
        batch_sizes = []
        for c in calls:
            batch_json = c.args[0]
            batch_data = json.loads(batch_json)
            batch_sizes.append(len(batch_data))

        assert batch_sizes == [5, 5, 2]

    @patch('orchestrator.EMAIL_BATCH_SIZE', 10)
    @patch('orchestrator.get_vault_stats', return_value={"total": 0})
    @patch('orchestrator.fetch_emails')
    def test_progress_callback_events(self, mock_fetch, mock_stats):
        """Verify progress_callback receives events in the right order."""
        mock_fetch.return_value = _make_fake_emails(15)

        from orchestrator import Orchestrator
        with patch.object(Orchestrator, '__init__', lambda self: None):
            orch = Orchestrator()
            orch.email_reader = MagicMock()
            orch.email_reader.analyze_batch.return_value = '{"observations": []}'
            orch.memory_writer = MagicMock()
            orch.memory_writer.reset = MagicMock()
            orch.memory_writer.run.return_value = "Done"

            events = []
            orch.build_memory("test", progress_callback=lambda e: events.append(e), max_emails=15)

        # Expected stages in order
        stages = [e["stage"] for e in events]
        statuses = [e["status"] for e in events]

        # Must start with fetching
        assert stages[0] == "fetching"
        assert statuses[0] == "started"

        # Must have email_reader events
        assert "email_reader" in stages

        # Must have memory_writer events
        assert "memory_writer" in stages

        # Must end with complete
        assert stages[-1] == "complete"
        assert statuses[-1] == "complete"

    @patch('orchestrator.EMAIL_BATCH_SIZE', 10)
    @patch('orchestrator.get_vault_stats', return_value={"total": 0})
    @patch('orchestrator.fetch_emails')
    def test_progress_callback_in_progress_per_batch(self, mock_fetch, mock_stats):
        """Each batch should emit an 'in_progress' event."""
        mock_fetch.return_value = _make_fake_emails(25)

        from orchestrator import Orchestrator
        with patch.object(Orchestrator, '__init__', lambda self: None):
            orch = Orchestrator()
            orch.email_reader = MagicMock()
            orch.email_reader.analyze_batch.return_value = '{"observations": []}'
            orch.memory_writer = MagicMock()
            orch.memory_writer.reset = MagicMock()
            orch.memory_writer.run.return_value = "Done"

            events = []
            orch.build_memory("test", progress_callback=lambda e: events.append(e), max_emails=25)

        # Should have 3 in_progress events (one per batch)
        in_progress = [e for e in events if e.get("status") == "in_progress"]
        assert len(in_progress) == 3

    @patch('orchestrator.get_vault_stats', return_value={"total": 5, "people": 5})
    @patch('orchestrator.fetch_emails')
    def test_memory_writer_receives_combined_observations(self, mock_fetch, mock_stats):
        """Memory writer should receive all batch observations combined."""
        mock_fetch.return_value = _make_fake_emails(5)

        from orchestrator import Orchestrator
        with patch.object(Orchestrator, '__init__', lambda self: None):
            orch = Orchestrator()
            orch.email_reader = MagicMock()
            orch.email_reader.analyze_batch.return_value = '{"observations": [{"type":"people"}]}'
            orch.memory_writer = MagicMock()
            orch.memory_writer.reset = MagicMock()
            orch.memory_writer.run.return_value = "Done"

            orch.build_memory("test", max_emails=5)

        writer_prompt = orch.memory_writer.run.call_args.args[0]
        assert "observations" in writer_prompt.lower()
        assert "duplicate" in writer_prompt.lower()  # Mentions dedup

    @patch('orchestrator.get_vault_stats', return_value={"total": 0})
    @patch('orchestrator.fetch_emails')
    def test_memory_writer_reset_called(self, mock_fetch, mock_stats):
        """Memory writer should be reset before processing."""
        mock_fetch.return_value = _make_fake_emails(5)

        from orchestrator import Orchestrator
        with patch.object(Orchestrator, '__init__', lambda self: None):
            orch = Orchestrator()
            orch.email_reader = MagicMock()
            orch.email_reader.analyze_batch.return_value = '{}'
            orch.memory_writer = MagicMock()
            orch.memory_writer.reset = MagicMock()
            orch.memory_writer.run.return_value = "Done"

            orch.build_memory("test")

        orch.memory_writer.reset.assert_called_once()

    @patch('orchestrator.get_vault_stats', return_value={"total": 0})
    @patch('orchestrator.fetch_emails')
    def test_defaults_from_config(self, mock_fetch, mock_stats):
        """When no params given, use config defaults."""
        mock_fetch.return_value = []

        from orchestrator import Orchestrator
        from config.settings import DEFAULT_MAX_EMAILS, DEFAULT_DAYS_BACK
        with patch.object(Orchestrator, '__init__', lambda self: None):
            orch = Orchestrator()
            orch.email_reader = MagicMock()
            orch.memory_writer = MagicMock()

            orch.build_memory("test")

        mock_fetch.assert_called_once_with(
            max_results=DEFAULT_MAX_EMAILS,
            query='',
            days_back=DEFAULT_DAYS_BACK
        )
