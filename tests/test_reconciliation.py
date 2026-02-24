"""Tests for the ReconciliationAgent's heuristic matching and expiry logic."""

import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.reconciliation_agent import heuristic_match, check_expiry


class TestHeuristicMatching:
    """Test the heuristic matching function that compares action items to sent emails."""

    def test_subject_overlap_match(self):
        """Should match when sent email subject overlaps with source_emails."""
        action = {
            'source_emails': ['Re: Q2 Project Timeline'],
            'related_to': ['Jake'],
        }
        sent_emails = [
            {'subject': 'Re: Q2 Project Timeline', 'to': 'jake@example.com', 'date': '2026-02-22'},
        ]
        match = heuristic_match(action, sent_emails)
        assert match is not None
        assert 'Q2 Project Timeline' in match['reason']

    def test_recipient_match(self):
        """Should match when sent email recipient matches related_to entity."""
        action = {
            'source_emails': [],
            'related_to': ['Sarah Chen'],
        }
        sent_emails = [
            {'subject': 'Monthly report attached', 'to': 'sarah.chen@company.com', 'date': '2026-02-22'},
        ]
        match = heuristic_match(action, sent_emails)
        assert match is not None
        assert 'sarah' in match['reason'].lower()

    def test_no_match(self):
        """Should return None when no sent email matches."""
        action = {
            'source_emails': ['Budget review needed'],
            'related_to': ['Finance Team'],
        }
        sent_emails = [
            {'subject': 'Lunch plans', 'to': 'friend@example.com', 'date': '2026-02-22'},
        ]
        match = heuristic_match(action, sent_emails)
        assert match is None

    def test_empty_sent_emails(self):
        """Should return None with no sent emails."""
        action = {'source_emails': ['Something'], 'related_to': ['Someone']}
        assert heuristic_match(action, []) is None


class TestExpiryCheck:
    """Test deadline-based expiry logic."""

    def test_past_deadline_is_expired(self):
        """Action with past deadline should be marked expired."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        assert check_expiry(yesterday) is True

    def test_future_deadline_not_expired(self):
        """Action with future deadline should not be expired."""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        assert check_expiry(tomorrow) is False

    def test_no_deadline_not_expired(self):
        """Action with no deadline should not be expired."""
        assert check_expiry('') is False
        assert check_expiry(None) is False

    def test_today_deadline_not_expired(self):
        """Action due today should not be expired yet."""
        today = datetime.now().strftime('%Y-%m-%d')
        assert check_expiry(today) is False
