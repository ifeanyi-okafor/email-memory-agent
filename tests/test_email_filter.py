# tests/test_email_filter.py
#
# ============================================================================
# Tests for the email noise filter (tools/email_filter.py).
#
# The filter classifies emails as "signal" (real person-to-person messages)
# or "noise" (newsletters, receipts, notifications, cold outreach) using
# pure heuristics — no LLM calls involved.
#
# We test three levels:
#   1. Single email classification (classify_email)
#   2. Batch filtering (filter_emails)
#   3. Realistic Gmail-shaped data (integration)
# ============================================================================

import pytest
from tools.email_filter import classify_email, filter_emails


# ── TestClassifyEmail ─────────────────────────────────────────────────
# Tests for classifying individual emails as signal or noise.

class TestClassifyEmail:
    """Tests for the classify_email() function — single email classification."""

    def test_normal_email_is_signal(self):
        """A regular person-to-person email should be classified as signal."""
        email = {
            'from': 'Alice Johnson <alice@company.com>',
            'subject': 'Quick question about the project',
            'body': 'Hey, do you have time to chat about the timeline?',
            'labels': ['INBOX'],
        }
        assert classify_email(email) == 'signal'

    def test_noreply_sender_is_noise(self):
        """Emails from noreply addresses are automated — noise."""
        email = {
            'from': 'GitHub <noreply@github.com>',
            'subject': 'New pull request in your repo',
            'body': 'Someone opened a PR.',
            'labels': ['INBOX'],
        }
        assert classify_email(email) == 'noise'

    def test_notifications_sender_is_noise(self):
        """Emails from notifications@ addresses are automated — noise."""
        email = {
            'from': 'LinkedIn <notifications@linkedin.com>',
            'subject': 'You have 5 new connection requests',
            'body': 'See who wants to connect with you.',
            'labels': ['INBOX'],
        }
        assert classify_email(email) == 'noise'

    def test_unsubscribe_in_body_is_noise(self):
        """Emails with 'unsubscribe' in the body are mass-mailed — noise."""
        email = {
            'from': 'TechDaily <editor@techdaily.com>',
            'subject': 'This week in AI',
            'body': 'Top stories this week... Click here to unsubscribe.',
            'labels': ['INBOX'],
        }
        assert classify_email(email) == 'noise'

    def test_gmail_promotions_label_is_noise(self):
        """Emails in Gmail's Promotions tab are marketing — noise."""
        email = {
            'from': 'Store <deals@shop.com>',
            'subject': '50% off everything!',
            'body': 'Limited time offer.',
            'labels': ['CATEGORY_PROMOTIONS'],
        }
        assert classify_email(email) == 'noise'

    def test_gmail_social_label_is_noise(self):
        """Emails in Gmail's Social tab are social notifications — noise."""
        email = {
            'from': 'Twitter <info@twitter.com>',
            'subject': 'You have new followers',
            'body': '3 people followed you.',
            'labels': ['CATEGORY_SOCIAL'],
        }
        assert classify_email(email) == 'noise'

    def test_gmail_updates_label_is_noise(self):
        """Emails in Gmail's Updates tab are automated updates — noise."""
        email = {
            'from': 'Bank <statements@bank.com>',
            'subject': 'Your monthly statement is ready',
            'body': 'View your statement online.',
            'labels': ['CATEGORY_UPDATES'],
        }
        assert classify_email(email) == 'noise'

    def test_gmail_forums_label_is_noise(self):
        """Emails in Gmail's Forums tab are mailing list messages — noise."""
        email = {
            'from': 'Python Dev List <python-dev@lists.python.org>',
            'subject': 'PEP 999 discussion',
            'body': 'Let us discuss the new PEP.',
            'labels': ['CATEGORY_FORUMS'],
        }
        assert classify_email(email) == 'noise'

    def test_receipt_subject_is_noise(self):
        """Order confirmation subjects are transactional — noise."""
        email = {
            'from': 'Amazon <ship-confirm@amazon.com>',
            'subject': 'Your order confirmation #123-456',
            'body': 'Thank you for your purchase.',
            'labels': ['INBOX'],
        }
        assert classify_email(email) == 'noise'

    def test_personal_with_inbox_label_is_signal(self):
        """A real email sitting in INBOX with no noise markers is signal."""
        email = {
            'from': 'Bob Smith <bob@example.com>',
            'subject': 'Lunch tomorrow?',
            'body': 'Want to grab lunch at noon?',
            'labels': ['INBOX', 'IMPORTANT'],
        }
        assert classify_email(email) == 'signal'

    def test_missing_fields_defaults_to_signal(self):
        """An email dict with only a 'from' key should not crash — defaults to signal."""
        email = {
            'from': 'someone@example.com',
        }
        assert classify_email(email) == 'signal'

    def test_support_sender_is_noise(self):
        """Emails from support@ addresses are automated — noise."""
        email = {
            'from': 'Help Desk <support@helpdesk.com>',
            'subject': 'Your ticket has been updated',
            'body': 'An agent replied to your ticket.',
            'labels': ['INBOX'],
        }
        assert classify_email(email) == 'noise'


# ── TestFilterEmails ──────────────────────────────────────────────────
# Tests for batch filtering of email lists.

class TestFilterEmails:
    """Tests for the filter_emails() function — batch filtering."""

    def test_filters_noise_from_batch(self):
        """A mixed batch should be split into 2 signal and 2 noise emails."""
        emails = [
            # Signal: person-to-person
            {
                'from': 'Alice <alice@company.com>',
                'subject': 'Meeting notes',
                'body': 'Here are the notes from today.',
                'labels': ['INBOX'],
            },
            # Noise: noreply sender
            {
                'from': 'noreply@service.com',
                'subject': 'Your weekly digest',
                'body': 'Here is your digest.',
                'labels': ['INBOX'],
            },
            # Signal: personal question
            {
                'from': 'Bob <bob@example.com>',
                'subject': 'Quick favor',
                'body': 'Can you review my doc?',
                'labels': ['INBOX'],
            },
            # Noise: promotions label
            {
                'from': 'deals@store.com',
                'subject': 'Big sale!',
                'body': 'Everything must go.',
                'labels': ['CATEGORY_PROMOTIONS'],
            },
        ]

        signal, noise = filter_emails(emails)
        assert len(signal) == 2
        assert len(noise) == 2

    def test_empty_batch_returns_empty(self):
        """An empty list should return two empty lists."""
        signal, noise = filter_emails([])
        assert signal == []
        assert noise == []

    def test_all_signal(self):
        """When all emails are signal, noise list should be empty."""
        emails = [
            {
                'from': 'Alice <alice@company.com>',
                'subject': 'Project update',
                'body': 'Everything is on track.',
                'labels': ['INBOX'],
            },
            {
                'from': 'Bob <bob@example.com>',
                'subject': 'Re: Dinner plans',
                'body': 'Sounds good, see you at 7.',
                'labels': ['INBOX'],
            },
        ]

        signal, noise = filter_emails(emails)
        assert len(signal) == 2
        assert len(noise) == 0

    def test_all_noise(self):
        """When all emails are noise, signal list should be empty."""
        emails = [
            {
                'from': 'noreply@github.com',
                'subject': 'PR merged',
                'body': 'Your pull request was merged.',
                'labels': ['INBOX'],
            },
            {
                'from': 'deals@store.com',
                'subject': 'Flash sale!',
                'body': 'Shop now. Unsubscribe here.',
                'labels': ['CATEGORY_PROMOTIONS'],
            },
        ]

        signal, noise = filter_emails(emails)
        assert len(signal) == 0
        assert len(noise) == 2


# ── TestFilterIntegration ─────────────────────────────────────────────
# Tests with realistic Gmail-shaped data (matching gmail_tools.py output).

class TestFilterIntegration:
    """Tests with realistic Gmail-shaped email dictionaries."""

    def test_gmail_shaped_email_classification(self):
        """
        Emails shaped like real Gmail fetch output (with id, thread_id, date,
        snippet, from_email, from_name, etc.) should classify correctly.
        """
        # A real person-to-person email — signal
        personal_email = {
            'id': 'msg_001',
            'thread_id': 'thread_001',
            'from': 'Jane Doe <jane@company.com>',
            'from_email': 'jane@company.com',
            'from_name': 'Jane Doe',
            'to': 'me@gmail.com',
            'subject': 'Q3 Planning Discussion',
            'date': 'Mon, 10 Mar 2026 09:15:00 -0500',
            'snippet': 'Hey, wanted to discuss our Q3 roadmap...',
            'body': 'Hey, wanted to discuss our Q3 roadmap. Can we block an hour this week?',
            'labels': ['INBOX', 'IMPORTANT'],
        }

        # An automated notification — noise
        notification_email = {
            'id': 'msg_002',
            'thread_id': 'thread_002',
            'from': 'GitHub <notifications@github.com>',
            'from_email': 'notifications@github.com',
            'from_name': 'GitHub',
            'to': 'me@gmail.com',
            'subject': '[repo] Issue #42: Bug in parser',
            'date': 'Mon, 10 Mar 2026 10:30:00 -0500',
            'snippet': 'New comment on issue #42...',
            'body': 'User xyz commented on issue #42. View it on GitHub.',
            'labels': ['INBOX'],
        }

        # A promotional email — noise
        promo_email = {
            'id': 'msg_003',
            'thread_id': 'thread_003',
            'from': 'CloudHost <marketing@cloudhost.io>',
            'from_email': 'marketing@cloudhost.io',
            'from_name': 'CloudHost',
            'to': 'me@gmail.com',
            'subject': 'Upgrade your plan today!',
            'date': 'Mon, 10 Mar 2026 11:00:00 -0500',
            'snippet': 'Get 50% off premium...',
            'body': 'Upgrade now and save. Click to unsubscribe.',
            'labels': ['CATEGORY_PROMOTIONS'],
        }

        assert classify_email(personal_email) == 'signal'
        assert classify_email(notification_email) == 'noise'
        assert classify_email(promo_email) == 'noise'

        # Also verify batch filtering works with these shapes
        signal, noise = filter_emails([personal_email, notification_email, promo_email])
        assert len(signal) == 1
        assert len(noise) == 2
        assert signal[0]['id'] == 'msg_001'
