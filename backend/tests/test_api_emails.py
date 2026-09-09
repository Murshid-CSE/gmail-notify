"""
Tests for Email API endpoints.

Tests:
  • GET /emails — pagination
  • GET /emails — filtering
  • GET /emails/{id} — detail
  • 404 handling
  • Duplicate gmail_message_id protection
"""

import json
from datetime import datetime, timezone

from app.models.email_account import EmailAccount
from app.models.email_message import EmailMessage
from app.models.user import User


def _seed_data(db, num_emails: int = 5, account_email: str = "test@gmail.com"):
    """Seed a user, account, and N email messages."""
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        user = User(id=1, display_name="Test User")
        db.add(user)
        db.commit()

    account = EmailAccount(
        user_id=1,
        provider="gmail",
        email_address=account_email,
        is_active=True,
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    messages = []
    for i in range(num_emails):
        msg = EmailMessage(
            account_id=account.id,
            gmail_message_id=f"gmail_{i}",
            gmail_thread_id=f"thread_{i}",
            sender=f"sender{i}@example.com",
            recipients=json.dumps([f"me@example.com"]),
            subject=f"Test Email {i}",
            received_at=datetime(2026, 9, 1, 12, 0, i, tzinfo=timezone.utc),
            body_text=f"Body of email {i}",
            labels=json.dumps(["INBOX"]),
            processing_status="pending",
        )
        messages.append(msg)
        db.add(msg)

    db.commit()
    return account, messages


class TestListEmails:
    def test_empty_list(self, client, db):
        """No emails returns empty paginated response."""
        response = client.get("/emails")
        assert response.status_code == 200
        data = response.json()
        assert data["total_items"] == 0
        assert data["items"] == []
        assert data["has_next"] is False
        assert data["has_previous"] is False

    def test_paginated_response(self, client, db):
        """Pagination works correctly."""
        _seed_data(db, num_emails=15)

        # Page 1: 10 items.
        response = client.get("/emails?page=1&page_size=10")
        data = response.json()
        assert data["total_items"] == 15
        assert len(data["items"]) == 10
        assert data["has_next"] is True
        assert data["has_previous"] is False
        assert data["total_pages"] == 2

        # Page 2: 5 items.
        response = client.get("/emails?page=2&page_size=10")
        data = response.json()
        assert len(data["items"]) == 5
        assert data["has_next"] is False
        assert data["has_previous"] is True

    def test_default_page_size(self, client, db):
        """Default page size is 20."""
        _seed_data(db, num_emails=25)

        response = client.get("/emails")
        data = response.json()
        assert len(data["items"]) == 20
        assert data["page_size"] == 20

    def test_filter_by_account(self, client, db):
        """Filter emails by account_id."""
        account, _ = _seed_data(db, num_emails=3, account_email="acc1@gmail.com")

        response = client.get(f"/emails?account_id={account.id}")
        data = response.json()
        assert data["total_items"] == 3

        response = client.get("/emails?account_id=999")
        data = response.json()
        assert data["total_items"] == 0

    def test_filter_by_processing_status(self, client, db):
        """Filter emails by processing status."""
        _seed_data(db, num_emails=3)

        response = client.get("/emails?processing_status=pending")
        data = response.json()
        assert data["total_items"] == 3

        response = client.get("/emails?processing_status=extracted")
        data = response.json()
        assert data["total_items"] == 0

    def test_newest_first_ordering(self, client, db):
        """Emails are returned newest first."""
        _seed_data(db, num_emails=5)

        response = client.get("/emails?page_size=5")
        data = response.json()
        items = data["items"]
        # Received_at with higher seconds should come first.
        assert items[0]["subject"] == "Test Email 4"
        assert items[-1]["subject"] == "Test Email 0"

    def test_invalid_page_number(self, client, db):
        """Page number < 1 returns 422."""
        response = client.get("/emails?page=0")
        assert response.status_code == 422

    def test_page_size_limit(self, client, db):
        """Page size > 100 returns 422."""
        response = client.get("/emails?page_size=200")
        assert response.status_code == 422

    def test_labels_parsed_as_list(self, client, db):
        """Labels JSON string is returned as a list."""
        _seed_data(db, num_emails=1)

        response = client.get("/emails")
        data = response.json()
        item = data["items"][0]
        assert isinstance(item["labels"], list)
        assert "INBOX" in item["labels"]


class TestEmailDetail:
    def test_get_email_detail(self, client, db):
        """GET /emails/{id} returns full detail including body."""
        account, messages = _seed_data(db, num_emails=1)

        # Get the ID (need to query).
        response = client.get("/emails")
        email_id = response.json()["items"][0]["id"]

        response = client.get(f"/emails/{email_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["body_text"] == "Body of email 0"
        assert data["gmail_message_id"] == "gmail_0"
        assert isinstance(data["recipients"], list)

    def test_404_nonexistent_email(self, client, db):
        """404 for non-existent email."""
        response = client.get("/emails/999")
        assert response.status_code == 404


class TestDuplicateProtection:
    def test_unique_constraint(self, db):
        """Cannot insert two emails with the same gmail_message_id + account_id."""
        import pytest
        from sqlalchemy.exc import IntegrityError

        user = User(id=1, display_name="Test User")
        db.add(user)
        db.commit()

        account = EmailAccount(
            user_id=1, provider="gmail", email_address="dupe@gmail.com", is_active=True
        )
        db.add(account)
        db.commit()
        db.refresh(account)

        msg1 = EmailMessage(
            account_id=account.id,
            gmail_message_id="same_id",
            gmail_thread_id="thread1",
            sender="test@example.com",
            subject="First",
            received_at=datetime.now(timezone.utc),
        )
        db.add(msg1)
        db.commit()

        msg2 = EmailMessage(
            account_id=account.id,
            gmail_message_id="same_id",
            gmail_thread_id="thread1",
            sender="test@example.com",
            subject="Duplicate",
            received_at=datetime.now(timezone.utc),
        )
        db.add(msg2)
        with pytest.raises(IntegrityError):
            db.commit()
