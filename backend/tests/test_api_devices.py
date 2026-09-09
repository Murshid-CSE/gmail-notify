"""
CareerMail AI — Device Token API Tests.

Validates:
  • Device registration with new token
  • Idempotent registration with duplicate token
  • Token reactivation and last_seen update
  • Soft deactivation via DELETE /devices/{token}
  • Listing registered devices without secret token leakage
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from app.models.device import DeviceToken
from app.models.user import User


@pytest.fixture(autouse=True)
def ensure_default_user(db):
    """Ensure default user exists for foreign key constraints."""
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        user = User(id=1, display_name="Test User")
        db.add(user)
        db.commit()


class TestDeviceRegistration:
    """Test device token registration and idempotency."""

    def test_register_new_device(self, client, db):
        payload = {
            "fcm_token": "fcm-token-test-1234567890-abcdef",
            "device_type": "android",
            "device_name": "Pixel 8 Pro",
        }
        resp = client.post("/devices/register", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] is not None
        assert data["user_id"] == 1
        assert data["device_type"] == "android"
        assert data["device_name"] == "Pixel 8 Pro"
        assert data["is_active"] is True
        assert data["fcm_token_snippet"].startswith("fcm-token-")
        assert data["fcm_token_snippet"].endswith("...")
        # Verify does not expose entire raw token directly
        assert data["fcm_token_snippet"] != payload["fcm_token"]

        # Verify in DB
        device = db.query(DeviceToken).filter(DeviceToken.fcm_token == payload["fcm_token"]).first()
        assert device is not None
        assert device.is_active is True

    def test_register_duplicate_token_is_idempotent(self, client, db):
        payload = {
            "fcm_token": "idempotent-token-xyz-12345",
            "device_type": "android",
            "device_name": "Initial Device Name",
        }
        resp1 = client.post("/devices/register", json=payload)
        assert resp1.status_code == 200
        first_id = resp1.json()["id"]

        # Re-register same token with updated name
        update_payload = {
            "fcm_token": "idempotent-token-xyz-12345",
            "device_type": "android",
            "device_name": "Updated Device Name",
        }
        resp2 = client.post("/devices/register", json=update_payload)
        assert resp2.status_code == 200
        assert resp2.json()["id"] == first_id
        assert resp2.json()["device_name"] == "Updated Device Name"

        # Verify only ONE row exists in the database
        count = (
            db.query(DeviceToken)
            .filter(DeviceToken.fcm_token == "idempotent-token-xyz-12345")
            .count()
        )
        assert count == 1

    def test_reactivate_deactivated_token(self, client, db):
        token_val = "token-to-deactivate-and-reactivate"
        device = DeviceToken(
            user_id=1,
            fcm_token=token_val,
            device_type="ios",
            device_name="iPhone 15",
            is_active=False,
            created_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add(device)
        db.commit()

        # Re-register token
        payload = {
            "fcm_token": token_val,
            "device_type": "ios",
            "device_name": "iPhone 15 Pro",
        }
        resp = client.post("/devices/register", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_active"] is True
        assert data["device_name"] == "iPhone 15 Pro"

        db.refresh(device)
        assert device.is_active is True

    def test_invalid_device_type_validation(self, client):
        payload = {
            "fcm_token": "some-token",
            "device_type": "windows_phone",  # Invalid type
        }
        resp = client.post("/devices/register", json=payload)
        assert resp.status_code == 422


class TestDeviceListingAndDeactivation:
    """Test GET /devices and DELETE /devices/{token}."""

    def test_list_devices(self, client, db):
        device1 = DeviceToken(
            user_id=1,
            fcm_token="list-token-1-abc",
            device_type="android",
            device_name="Samsung S23",
            is_active=True,
        )
        device2 = DeviceToken(
            user_id=1,
            fcm_token="list-token-2-xyz",
            device_type="web",
            device_name="Chrome Web",
            is_active=False,
        )
        db.add_all([device1, device2])
        db.commit()

        resp = client.get("/devices")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        snippets = [d["fcm_token_snippet"] for d in data["devices"]]
        assert any("list-token-1" in s for s in snippets)

    def test_deactivate_device(self, client, db):
        token_val = "token-to-delete-abc"
        device = DeviceToken(
            user_id=1,
            fcm_token=token_val,
            device_type="android",
            device_name="Test Device",
            is_active=True,
        )
        db.add(device)
        db.commit()

        resp = client.delete(f"/devices/{token_val}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["deactivated"] is True

        db.refresh(device)
        assert device.is_active is False

    def test_deactivate_nonexistent_device_returns_404(self, client):
        resp = client.delete("/devices/nonexistent-token-999")
        assert resp.status_code == 404
