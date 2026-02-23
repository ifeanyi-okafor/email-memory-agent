# tests/test_integration.py
#
# Integration tests for the full batched pipeline: fetch → batch analyze → write.
# These test the actual wiring between components (with mocked external calls).

import json
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
            "body": f"Body of email {i}.",
            "labels": ["INBOX"]
        }
        for i in range(count)
    ]


class TestFullPipelineFlow:
    """Integration test for the complete build pipeline."""

    @patch('orchestrator.EMAIL_BATCH_SIZE', 5)
    @patch('orchestrator.get_vault_stats', return_value={"total": 3, "people": 2, "decisions": 1})
    @patch('orchestrator.fetch_emails')
    def test_full_pipeline_single_batch(self, mock_fetch, mock_stats):
        """3 emails with batch_size 5 → 1 batch → 1 analyze_batch call → 1 writer run."""
        mock_fetch.return_value = _make_fake_emails(3)

        from orchestrator import Orchestrator
        with patch.object(Orchestrator, '__init__', lambda self: None):
            orch = Orchestrator()
            orch.email_reader = MagicMock()
            orch.email_reader.analyze_batch.return_value = json.dumps({
                "observations": [
                    {"type": "people", "title": "Me — Engineer"}
                ]
            })
            orch.memory_writer = MagicMock()
            orch.memory_writer.reset = MagicMock()
            orch.memory_writer.run.return_value = "Created 1 memory"

            events = []
            result = orch.build_memory(
                "build", progress_callback=lambda e: events.append(e),
                max_emails=3
            )

        assert orch.email_reader.analyze_batch.call_count == 1
        assert orch.memory_writer.run.call_count == 1
        assert "Memory Build Complete" in result

    @patch('orchestrator.EMAIL_BATCH_SIZE', 3)
    @patch('orchestrator.get_vault_stats', return_value={"total": 10, "people": 5, "decisions": 3, "commitments": 2})
    @patch('orchestrator.fetch_emails')
    def test_full_pipeline_multiple_batches(self, mock_fetch, mock_stats):
        """10 emails with batch_size 3 → 4 batches."""
        mock_fetch.return_value = _make_fake_emails(10)

        batch_observations = [
            json.dumps({"observations": [{"type": "people", "title": f"Person {i}"}]})
            for i in range(4)
        ]

        from orchestrator import Orchestrator
        with patch.object(Orchestrator, '__init__', lambda self: None):
            orch = Orchestrator()
            orch.email_reader = MagicMock()
            orch.email_reader.analyze_batch.side_effect = batch_observations
            orch.memory_writer = MagicMock()
            orch.memory_writer.reset = MagicMock()
            orch.memory_writer.run.return_value = "Created 4 memories"

            events = []
            result = orch.build_memory(
                "build", progress_callback=lambda e: events.append(e),
                max_emails=10
            )

        # Verify batch counts
        assert orch.email_reader.analyze_batch.call_count == 4

        # Verify each batch got the right number of emails
        for i, c in enumerate(orch.email_reader.analyze_batch.call_args_list):
            batch_json = c.args[0]
            batch_data = json.loads(batch_json)
            expected_size = 1 if i == 3 else 3  # Last batch has 1 email
            assert len(batch_data) == expected_size

        # Verify writer got all observations
        writer_prompt = orch.memory_writer.run.call_args.args[0]
        for i in range(4):
            assert f"Person {i}" in writer_prompt

    @patch('orchestrator.EMAIL_BATCH_SIZE', 10)
    @patch('orchestrator.get_vault_stats', return_value={"total": 0})
    @patch('orchestrator.fetch_emails')
    def test_progress_events_order_and_content(self, mock_fetch, mock_stats):
        """Verify the exact sequence of progress events."""
        mock_fetch.return_value = _make_fake_emails(15)

        from orchestrator import Orchestrator
        with patch.object(Orchestrator, '__init__', lambda self: None):
            orch = Orchestrator()
            orch.email_reader = MagicMock()
            orch.email_reader.analyze_batch.return_value = '{}'
            orch.memory_writer = MagicMock()
            orch.memory_writer.reset = MagicMock()
            orch.memory_writer.run.return_value = "Done"

            events = []
            orch.build_memory("build", progress_callback=lambda e: events.append(e), max_emails=15)

        # Expected event sequence for 15 emails / 10 batch_size = 2 batches:
        expected_stages = [
            ("fetching", "started"),
            ("fetching", "complete"),
            ("email_reader", "started"),
            ("email_reader", "in_progress"),   # Batch 1
            ("email_reader", "in_progress"),   # Batch 2
            ("email_reader", "complete"),
            ("memory_writer", "started"),
            ("memory_writer", "complete"),
            ("complete", "complete"),
        ]

        actual = [(e["stage"], e["status"]) for e in events]
        assert actual == expected_stages

    @patch('orchestrator.EMAIL_BATCH_SIZE', 10)
    @patch('orchestrator.get_vault_stats', return_value={"total": 0})
    @patch('orchestrator.fetch_emails')
    def test_no_progress_callback(self, mock_fetch, mock_stats):
        """Pipeline should work fine without a progress callback."""
        mock_fetch.return_value = _make_fake_emails(5)

        from orchestrator import Orchestrator
        with patch.object(Orchestrator, '__init__', lambda self: None):
            orch = Orchestrator()
            orch.email_reader = MagicMock()
            orch.email_reader.analyze_batch.return_value = '{}'
            orch.memory_writer = MagicMock()
            orch.memory_writer.reset = MagicMock()
            orch.memory_writer.run.return_value = "Done"

            # No progress_callback — should not raise
            result = orch.build_memory("build", max_emails=5)

        assert "Memory Build Complete" in result


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch('orchestrator.EMAIL_BATCH_SIZE', 10)
    @patch('orchestrator.get_vault_stats', return_value={"total": 1, "people": 1})
    @patch('orchestrator.fetch_emails')
    def test_single_email(self, mock_fetch, mock_stats):
        """1 email should create exactly 1 batch."""
        mock_fetch.return_value = _make_fake_emails(1)

        from orchestrator import Orchestrator
        with patch.object(Orchestrator, '__init__', lambda self: None):
            orch = Orchestrator()
            orch.email_reader = MagicMock()
            orch.email_reader.analyze_batch.return_value = '{}'
            orch.memory_writer = MagicMock()
            orch.memory_writer.reset = MagicMock()
            orch.memory_writer.run.return_value = "Done"

            orch.build_memory("build", max_emails=1)

        assert orch.email_reader.analyze_batch.call_count == 1
        batch_json = orch.email_reader.analyze_batch.call_args.args[0]
        assert len(json.loads(batch_json)) == 1

    @patch('orchestrator.EMAIL_BATCH_SIZE', 10)
    @patch('orchestrator.get_vault_stats', return_value={"total": 10, "people": 10})
    @patch('orchestrator.fetch_emails')
    def test_exact_batch_size(self, mock_fetch, mock_stats):
        """10 emails with batch_size 10 → exactly 1 batch."""
        mock_fetch.return_value = _make_fake_emails(10)

        from orchestrator import Orchestrator
        with patch.object(Orchestrator, '__init__', lambda self: None):
            orch = Orchestrator()
            orch.email_reader = MagicMock()
            orch.email_reader.analyze_batch.return_value = '{}'
            orch.memory_writer = MagicMock()
            orch.memory_writer.reset = MagicMock()
            orch.memory_writer.run.return_value = "Done"

            orch.build_memory("build", max_emails=10)

        assert orch.email_reader.analyze_batch.call_count == 1

    @patch('orchestrator.EMAIL_BATCH_SIZE', 10)
    @patch('orchestrator.get_vault_stats', return_value={"total": 11, "people": 11})
    @patch('orchestrator.fetch_emails')
    def test_one_over_batch_size(self, mock_fetch, mock_stats):
        """11 emails with batch_size 10 → 2 batches (10 + 1)."""
        mock_fetch.return_value = _make_fake_emails(11)

        from orchestrator import Orchestrator
        with patch.object(Orchestrator, '__init__', lambda self: None):
            orch = Orchestrator()
            orch.email_reader = MagicMock()
            orch.email_reader.analyze_batch.return_value = '{}'
            orch.memory_writer = MagicMock()
            orch.memory_writer.reset = MagicMock()
            orch.memory_writer.run.return_value = "Done"

            orch.build_memory("build", max_emails=11)

        assert orch.email_reader.analyze_batch.call_count == 2

        # First batch: 10 emails, second batch: 1 email
        calls = orch.email_reader.analyze_batch.call_args_list
        assert len(json.loads(calls[0].args[0])) == 10
        assert len(json.loads(calls[1].args[0])) == 1

    @patch('orchestrator.EMAIL_BATCH_SIZE', 3)
    @patch('orchestrator.get_vault_stats', return_value={"total": 0})
    @patch('orchestrator.fetch_emails')
    def test_large_email_count(self, mock_fetch, mock_stats):
        """100 emails with batch_size 3 → 34 batches."""
        mock_fetch.return_value = _make_fake_emails(100)

        from orchestrator import Orchestrator
        with patch.object(Orchestrator, '__init__', lambda self: None):
            orch = Orchestrator()
            orch.email_reader = MagicMock()
            orch.email_reader.analyze_batch.return_value = '{}'
            orch.memory_writer = MagicMock()
            orch.memory_writer.reset = MagicMock()
            orch.memory_writer.run.return_value = "Done"

            orch.build_memory("build", max_emails=100)

        import math
        expected_batches = math.ceil(100 / 3)
        assert orch.email_reader.analyze_batch.call_count == expected_batches

    @patch('orchestrator.get_vault_stats', return_value={"total": 0})
    @patch('orchestrator.fetch_emails')
    def test_fetch_emails_raises_error(self, mock_fetch, mock_stats):
        """If fetch_emails raises, the error should propagate."""
        mock_fetch.side_effect = Exception("Gmail connection failed")

        from orchestrator import Orchestrator
        with patch.object(Orchestrator, '__init__', lambda self: None):
            orch = Orchestrator()
            orch.email_reader = MagicMock()
            orch.memory_writer = MagicMock()

            with pytest.raises(Exception, match="Gmail connection failed"):
                orch.build_memory("build")

    @patch('orchestrator.EMAIL_BATCH_SIZE', 10)
    @patch('orchestrator.get_vault_stats', return_value={"total": 0})
    @patch('orchestrator.fetch_emails')
    def test_analyze_batch_error_skips_batch(self, mock_fetch, mock_stats):
        """If all batches fail, the pipeline returns an error message (not an exception)."""
        mock_fetch.return_value = _make_fake_emails(5)

        from orchestrator import Orchestrator
        with patch.object(Orchestrator, '__init__', lambda self: None):
            orch = Orchestrator()
            orch.email_reader = MagicMock()
            orch.email_reader.analyze_batch.side_effect = Exception("Token limit exceeded")
            orch.memory_writer = MagicMock()

            result = orch.build_memory("build", max_emails=5)

            # Pipeline should NOT crash — it returns an error message instead
            assert "failed" in result.lower() or "error" in result.lower()
            # Memory writer should NOT be called when all batches fail
            orch.memory_writer.run.assert_not_called()

    @patch('orchestrator.EMAIL_BATCH_SIZE', 5)
    @patch('orchestrator.get_vault_stats', return_value={"total": 2})
    @patch('orchestrator.fetch_emails')
    def test_partial_batch_failure_continues(self, mock_fetch, mock_stats):
        """If one batch fails but others succeed, the pipeline continues with partial results."""
        mock_fetch.return_value = _make_fake_emails(10)

        from orchestrator import Orchestrator
        with patch.object(Orchestrator, '__init__', lambda self: None):
            orch = Orchestrator()
            orch.email_reader = MagicMock()
            # First batch fails, second succeeds
            orch.email_reader.analyze_batch.side_effect = [
                Exception("API overloaded"),
                "batch 2 observations"
            ]
            orch.memory_writer = MagicMock()
            orch.memory_writer.run.return_value = "Wrote 2 memories"

            result = orch.build_memory("build", max_emails=10)

            # Memory writer SHOULD be called with partial observations
            orch.memory_writer.run.assert_called_once()
            prompt_arg = orch.memory_writer.run.call_args[0][0]
            assert "batch 2 observations" in prompt_arg
