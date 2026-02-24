# tests/test_retry.py
#
# Tests for the exponential backoff retry logic in BaseAgent.
# We mock the LLM clients to simulate API errors without making real calls.

import time
import pytest
from unittest.mock import patch, MagicMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from anthropic import APIStatusError
from agents.base_agent import BaseAgent


def _make_api_error(status_code: int) -> APIStatusError:
    """Create a mock APIStatusError with the given status code."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.headers = {}
    mock_response.json.return_value = {"error": {"type": "overloaded_error", "message": "Overloaded"}}
    return APIStatusError(
        message=f"Error code: {status_code}",
        response=mock_response,
        body={"error": {"type": "overloaded_error", "message": "Overloaded"}},
    )


class TestAnthropicRetryLogic:
    """Tests for _call_anthropic retry with exponential backoff."""

    def setup_method(self):
        """Create a fresh BaseAgent for each test."""
        self.agent = BaseAgent()
        self.agent.system_prompt = "test"
        self.agent.tools = []
        self.agent.conversation_history = [{"role": "user", "content": "test"}]

    @patch('agents.base_agent.anthropic_client')
    def test_success_on_first_try(self, mock_client):
        """API call succeeds immediately — no retries needed."""
        mock_response = MagicMock()
        mock_client.messages.create.return_value = mock_response

        result = self.agent._call_anthropic()

        assert result == mock_response
        assert mock_client.messages.create.call_count == 1

    @patch('agents.base_agent.time.sleep')
    @patch('agents.base_agent.anthropic_client')
    def test_retry_on_529_then_succeed(self, mock_client, mock_sleep):
        """529 error on first attempt, success on second."""
        error_529 = _make_api_error(529)
        mock_response = MagicMock()
        mock_client.messages.create.side_effect = [error_529, mock_response]

        result = self.agent._call_anthropic()

        assert result == mock_response
        assert mock_client.messages.create.call_count == 2
        mock_sleep.assert_called_once()  # Should have slept once

    @patch('agents.base_agent.time.sleep')
    @patch('agents.base_agent.anthropic_client')
    def test_retry_on_429_then_succeed(self, mock_client, mock_sleep):
        """429 rate limit error on first attempt, success on second."""
        error_429 = _make_api_error(429)
        mock_response = MagicMock()
        mock_client.messages.create.side_effect = [error_429, mock_response]

        result = self.agent._call_anthropic()

        assert result == mock_response
        assert mock_client.messages.create.call_count == 2

    @patch('agents.base_agent.random.random', return_value=0.5)
    @patch('agents.base_agent.time.sleep')
    @patch('agents.base_agent.anthropic_client')
    def test_exponential_backoff_delays(self, mock_client, mock_sleep, mock_random):
        """Verify backoff doubles with jitter: base * 2^attempt ± 25%."""
        error_529 = _make_api_error(529)
        mock_response = MagicMock()
        mock_client.messages.create.side_effect = [
            error_529, error_529, error_529, mock_response
        ]

        result = self.agent._call_anthropic()

        assert result == mock_response
        assert mock_client.messages.create.call_count == 4

        # With random()=0.5, jitter = base*0.25*(2*0.5-1) = 0, so delays are exact
        sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
        from config.settings import API_RETRY_BASE_DELAY
        expected = [API_RETRY_BASE_DELAY * (2 ** i) for i in range(3)]
        assert sleep_calls == expected

    @patch('config.settings.API_MAX_RETRIES', 3)
    @patch('agents.base_agent.time.sleep')
    @patch('agents.base_agent.anthropic_client')
    def test_exhausted_retries_raises(self, mock_client, mock_sleep):
        """All retries exhausted — the error propagates to the caller."""
        error_529 = _make_api_error(529)
        mock_client.messages.create.side_effect = error_529

        with pytest.raises(APIStatusError):
            self.agent._call_anthropic()

        # With API_MAX_RETRIES=3, should attempt 3 times
        assert mock_client.messages.create.call_count == 3

    @patch('agents.base_agent.time.sleep')
    @patch('agents.base_agent.anthropic_client')
    def test_non_retryable_error_raises_immediately(self, mock_client, mock_sleep):
        """A 400 Bad Request should NOT be retried — raise immediately."""
        error_400 = _make_api_error(400)
        mock_client.messages.create.side_effect = error_400

        with pytest.raises(APIStatusError):
            self.agent._call_anthropic()

        # Should only try once (no retry for 400)
        assert mock_client.messages.create.call_count == 1
        mock_sleep.assert_not_called()

    @patch('agents.base_agent.time.sleep')
    @patch('agents.base_agent.anthropic_client')
    def test_500_error_not_retried(self, mock_client, mock_sleep):
        """500 Internal Server Error should NOT be retried (not in our retryable set)."""
        error_500 = _make_api_error(500)
        mock_client.messages.create.side_effect = error_500

        with pytest.raises(APIStatusError):
            self.agent._call_anthropic()

        assert mock_client.messages.create.call_count == 1
        mock_sleep.assert_not_called()

    @patch('agents.base_agent.time.sleep')
    @patch('agents.base_agent.anthropic_client')
    def test_mixed_retryable_errors(self, mock_client, mock_sleep):
        """Mix of 429 and 529 errors before success."""
        mock_response = MagicMock()
        mock_client.messages.create.side_effect = [
            _make_api_error(429),
            _make_api_error(529),
            mock_response
        ]

        result = self.agent._call_anthropic()

        assert result == mock_response
        assert mock_client.messages.create.call_count == 3
        assert mock_sleep.call_count == 2


class TestProviderFallback:
    """Tests for OpenRouter → Anthropic fallback logic."""

    def setup_method(self):
        self.agent = BaseAgent()
        self.agent.system_prompt = "test"
        self.agent.tools = []
        self.agent.conversation_history = [{"role": "user", "content": "test"}]

    @patch('agents.base_agent.USE_OPENROUTER', True)
    @patch('agents.base_agent.USE_ANTHROPIC', True)
    @patch('agents.base_agent.openrouter_client')
    @patch('agents.base_agent.anthropic_client')
    def test_fallback_on_openrouter_failure(self, mock_anthropic, mock_openrouter, ):
        """When OpenRouter fails, should fall back to Anthropic."""
        mock_openrouter.chat.completions.create.side_effect = Exception("OpenRouter down")
        mock_anthropic_response = MagicMock()
        mock_anthropic.messages.create.return_value = mock_anthropic_response

        result = self.agent._call_llm()

        assert result == mock_anthropic_response
        mock_openrouter.chat.completions.create.assert_called_once()
        mock_anthropic.messages.create.assert_called_once()

    @patch('agents.base_agent.USE_OPENROUTER', False)
    @patch('agents.base_agent.USE_ANTHROPIC', True)
    @patch('agents.base_agent.anthropic_client')
    def test_anthropic_only(self, mock_anthropic):
        """When only Anthropic is configured, use it directly."""
        mock_response = MagicMock()
        mock_anthropic.messages.create.return_value = mock_response

        result = self.agent._call_llm()

        assert result == mock_response

    @patch('agents.base_agent.USE_OPENROUTER', False)
    @patch('agents.base_agent.USE_ANTHROPIC', False)
    def test_no_provider_raises(self):
        """When no provider is configured, raise RuntimeError."""
        with pytest.raises(RuntimeError, match="No LLM provider available"):
            self.agent._call_llm()
