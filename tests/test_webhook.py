"""Tests for webhook endpoint."""
import pytest
import hmac
import hashlib
import json
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def calculate_signature(secret: str, body: str) -> str:
    """Calculate HMAC-SHA256 signature."""
    return hmac.new(
        secret.encode(),
        body.encode(),
        hashlib.sha256
    ).hexdigest()


@pytest.fixture
def valid_message():
    """Valid message payload."""
    return {
        "message_id": "msg_123",
        "from": "+919876543210",
        "to": "+919876543211",
        "ts": "2025-01-15T10:00:00Z",
        "text": "Hello, world!"
    }


@pytest.fixture
def webhook_secret():
    """Webhook secret for testing."""
    return "test-secret-key"


def test_webhook_missing_signature(valid_message):
    """Test webhook without signature returns 401."""
    response = client.post("/webhook", json=valid_message)
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid signature"}


def test_webhook_invalid_signature(valid_message):
    """Test webhook with invalid signature returns 401."""
    response = client.post(
        "/webhook",
        json=valid_message,
        headers={"X-Signature": "invalid-signature"}
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid signature"}


def test_webhook_valid_signature(valid_message, webhook_secret, monkeypatch):
    """Test webhook with valid signature returns 200."""
    # Set webhook secret
    monkeypatch.setenv("WEBHOOK_SECRET", webhook_secret)
    from config import Settings
    from main import settings as app_settings
    app_settings.webhook_secret = webhook_secret
    
    body = json.dumps(valid_message)
    signature = calculate_signature(webhook_secret, body)
    
    response = client.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature": signature
        }
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_webhook_duplicate_message(valid_message, webhook_secret, monkeypatch):
    """Test duplicate message returns 200 (idempotent)."""
    # Set webhook secret
    monkeypatch.setenv("WEBHOOK_SECRET", webhook_secret)
    from config import Settings
    from main import settings as app_settings
    app_settings.webhook_secret = webhook_secret
    
    body = json.dumps(valid_message)
    signature = calculate_signature(webhook_secret, body)
    
    # First request
    response1 = client.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature": signature
        }
    )
    assert response1.status_code == 200
    
    # Duplicate request
    response2 = client.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature": signature
        }
    )
    assert response2.status_code == 200
    assert response2.json() == {"status": "ok"}


def test_webhook_validation_error(webhook_secret, monkeypatch):
    """Test webhook with invalid data returns 422."""
    # Set webhook secret
    monkeypatch.setenv("WEBHOOK_SECRET", webhook_secret)
    from main import settings as app_settings
    app_settings.webhook_secret = webhook_secret
    
    invalid_message = {
        "message_id": "",  # Empty message_id
        "from": "+919876543210",
        "to": "+919876543211",
        "ts": "2025-01-15T10:00:00Z",
    }
    
    body = json.dumps(invalid_message)
    signature = calculate_signature(webhook_secret, body)
    
    response = client.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature": signature
        }
    )
    assert response.status_code == 422


def test_webhook_invalid_msisdn(webhook_secret, monkeypatch):
    """Test webhook with invalid MSISDN format returns 422."""
    # Set webhook secret
    monkeypatch.setenv("WEBHOOK_SECRET", webhook_secret)
    from main import settings as app_settings
    app_settings.webhook_secret = webhook_secret
    
    invalid_message = {
        "message_id": "msg_123",
        "from": "919876543210",  # Missing +
        "to": "+919876543211",
        "ts": "2025-01-15T10:00:00Z",
    }
    
    body = json.dumps(invalid_message)
    signature = calculate_signature(webhook_secret, body)
    
    response = client.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature": signature
        }
    )
    assert response.status_code == 422


def test_webhook_invalid_timestamp(webhook_secret, monkeypatch):
    """Test webhook with invalid timestamp returns 422."""
    # Set webhook secret
    monkeypatch.setenv("WEBHOOK_SECRET", webhook_secret)
    from main import settings as app_settings
    app_settings.webhook_secret = webhook_secret
    
    invalid_message = {
        "message_id": "msg_123",
        "from": "+919876543210",
        "to": "+919876543211",
        "ts": "2025-01-15T10:00:00",  # Missing Z
    }
    
    body = json.dumps(invalid_message)
    signature = calculate_signature(webhook_secret, body)
    
    response = client.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature": signature
        }
    )
    assert response.status_code == 422


def test_webhook_text_too_long(webhook_secret, monkeypatch):
    """Test webhook with text exceeding max length returns 422."""
    # Set webhook secret
    monkeypatch.setenv("WEBHOOK_SECRET", webhook_secret)
    from main import settings as app_settings
    app_settings.webhook_secret = webhook_secret
    
    invalid_message = {
        "message_id": "msg_123",
        "from": "+919876543210",
        "to": "+919876543211",
        "ts": "2025-01-15T10:00:00Z",
        "text": "x" * 4097  # Exceeds 4096 char limit
    }
    
    body = json.dumps(invalid_message)
    signature = calculate_signature(webhook_secret, body)
    
    response = client.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature": signature
        }
    )
    assert response.status_code == 422

