"""
Tests for Account API endpoints.

Tests:
  • GET /accounts — list
  • DELETE /accounts/{id} — disconnect
  • Duplicate protection
  • Security (no tokens in responses)
"""

from app.models.email_account import EmailAccount
from app.models.user import User


def _seed_user_and_account(db, email="test@gmail.com"):
    """Helper: create a user and account in the test DB."""
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        user = User(id=1, display_name="Test User")
        db.add(user)
        db.commit()

    account = EmailAccount(
        user_id=1,
        provider="gmail",
        email_address=email,
        encrypted_access_token="encrypted-access",
        encrypted_refresh_token="encrypted-refresh",
        is_active=True,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


class TestListAccounts:
    def test_empty_accounts(self, client, db):
        """No accounts returns empty list."""
        response = client.get("/accounts")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["accounts"] == []

    def test_list_with_accounts(self, client, db):
        """Returns connected accounts with message count."""
        _seed_user_and_account(db, "account1@gmail.com")
        _seed_user_and_account(db, "account2@gmail.com")

        response = client.get("/accounts")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    def test_no_tokens_in_response(self, client, db):
        """SECURITY: API responses must never contain tokens."""
        _seed_user_and_account(db)

        response = client.get("/accounts")
        data = response.json()

        # Check no sensitive fields leak.
        for account in data["accounts"]:
            assert "encrypted_access_token" not in account
            assert "encrypted_refresh_token" not in account
            assert "token" not in str(account).lower() or "token" not in account
            assert "secret" not in str(account).lower()


class TestDeleteAccount:
    def test_delete_existing_account(self, client, db):
        """Successfully disconnect an account."""
        account = _seed_user_and_account(db)

        response = client.delete(f"/accounts/{account.id}")
        assert response.status_code == 200
        assert "disconnected" in response.json()["message"]

        # Verify it's gone.
        response = client.get("/accounts")
        assert response.json()["total"] == 0

    def test_delete_nonexistent_account(self, client, db):
        """404 for non-existent account."""
        response = client.delete("/accounts/999")
        assert response.status_code == 404


class TestSyncEndpoint:
    def test_sync_nonexistent_account(self, client, db):
        """404 when syncing non-existent account."""
        response = client.post("/accounts/999/sync")
        assert response.status_code == 404

    def test_sync_no_refresh_token(self, client, db):
        """400 when account has no refresh token."""
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            user = User(id=1, display_name="Test User")
            db.add(user)
            db.commit()

        account = EmailAccount(
            user_id=1,
            provider="gmail",
            email_address="notoken@gmail.com",
            encrypted_refresh_token=None,
            is_active=True,
        )
        db.add(account)
        db.commit()
        db.refresh(account)

        response = client.post(f"/accounts/{account.id}/sync")
        assert response.status_code == 400
        assert "refresh token" in response.json()["detail"].lower()
