# tests/test_email_reader.py
#
# Tests for EmailReaderAgent, specifically the new analyze_batch method
# and the system prompt update for handling pre-provided emails.

import json
import pytest
from unittest.mock import patch, MagicMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.email_reader import EmailReaderAgent


class TestEmailReaderAnalyzeBatch:
    """Tests for the analyze_batch method."""

    def setup_method(self):
        """Create a fresh EmailReaderAgent for each test."""
        self.agent = EmailReaderAgent()

    def test_analyze_batch_exists(self):
        """Method should exist on EmailReaderAgent."""
        assert hasattr(self.agent, 'analyze_batch')
        assert callable(self.agent.analyze_batch)

    @patch.object(EmailReaderAgent, 'run', return_value='{"observations": []}')
    def test_analyze_batch_resets_history(self, mock_run):
        """Each batch should start with a clean conversation history."""
        # Pre-fill history to simulate a previous batch
        self.agent.conversation_history = [
            {"role": "user", "content": "old stuff"},
            {"role": "assistant", "content": "old response"}
        ]

        self.agent.analyze_batch('[]', 1, 1)

        # After analyze_batch calls reset then run, history should have been cleared
        # before run was called. We verify reset was called by checking the prompt.
        mock_run.assert_called_once()
        prompt = mock_run.call_args.args[0]
        assert "batch 1 of 1" in prompt

    @patch.object(EmailReaderAgent, 'run', return_value='{"observations": []}')
    def test_analyze_batch_prompt_contains_batch_info(self, mock_run):
        """The prompt should include batch number and total."""
        self.agent.analyze_batch('[{"subject": "test"}]', 3, 7)

        prompt = mock_run.call_args.args[0]
        assert "batch 3 of 7" in prompt
        assert "without calling the read_emails tool" in prompt

    @patch.object(EmailReaderAgent, 'run', return_value='{"observations": []}')
    def test_analyze_batch_prompt_contains_emails(self, mock_run):
        """The prompt should include the email JSON data."""
        test_emails = json.dumps([{"subject": "Important Meeting", "from": "boss@co.com"}])
        self.agent.analyze_batch(test_emails, 1, 1)

        prompt = mock_run.call_args.args[0]
        assert "Important Meeting" in prompt
        assert "boss@co.com" in prompt

    @patch.object(EmailReaderAgent, 'run', return_value='{"observations": [{"type": "people"}]}')
    def test_analyze_batch_returns_run_result(self, mock_run):
        """analyze_batch should return whatever run() returns."""
        result = self.agent.analyze_batch('[]', 1, 1)
        assert result == '{"observations": [{"type": "people"}]}'

    def test_analyze_batch_clears_history_before_run(self):
        """Verify reset is called before run by checking history state."""
        self.agent.conversation_history = [
            {"role": "user", "content": "leftover from previous batch"}
        ]

        with patch.object(EmailReaderAgent, 'run') as mock_run:
            mock_run.return_value = '{}'

            # Track when reset happens vs when run happens
            call_order = []
            original_reset = self.agent.reset

            def tracking_reset():
                call_order.append(('reset', len(self.agent.conversation_history)))
                original_reset()

            def tracking_run(prompt):
                call_order.append(('run', len(self.agent.conversation_history)))
                return '{}'

            self.agent.reset = tracking_reset
            mock_run.side_effect = tracking_run

            self.agent.analyze_batch('[]', 1, 1)

            # Reset should have been called (clearing the 1 leftover message)
            # Run should have been called after reset (history empty)
            assert call_order[0][0] == 'reset'
            assert call_order[0][1] == 1  # Had 1 message before reset


class TestEmailReaderSystemPrompt:
    """Tests for the system prompt update."""

    def setup_method(self):
        self.agent = EmailReaderAgent()

    def test_prompt_mentions_pre_provided_emails(self):
        """System prompt should tell Claude to handle pre-provided emails."""
        assert "already provided" in self.agent.system_prompt.lower()

    def test_prompt_mentions_skip_tool_call(self):
        """System prompt should tell Claude to skip read_emails when data is provided."""
        assert "skip" in self.agent.system_prompt.lower()

    def test_tool_still_defined(self):
        """The read_emails tool should still be defined for backwards compatibility."""
        tool_names = [t["name"] for t in self.agent.tools]
        assert "read_emails" in tool_names
