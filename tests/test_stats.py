"""Tests for stats endpoint."""
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
def webhook_secret():
    """Webhook secret for testing."""
    return "test-secret-key"


def seed_messages(webhook_secret, monkeypatch):
    """Seed test messages for stats."""
    # Set webhook secret
    monkeypatch.setenv("WEBHOOK_SECRET", webhook_secret)
    from main import settings as app_settings
    app_settings.webhook_secret = webhook_secret
    
    messages = [
        {
            "message_id": "msg_1",
            "from": "+919876543210",
            "to": "+919876543211",
            "ts": "2025-01-15T10:00:00Z",
            "text": "Hello"
        },
        {
            "message_id": "msg_2",
            "from": "+919876543210",
            "to": "+919876543212",
            "ts": "2025-01-15T10:01:00Z",
            "text": "World"
        },
        {
            "message_id": "msg_3",
            "from": "+919876543211",
            "to": "+919876543210",
            "ts": "2025-01-15T10:02:00Z",
            "text": "Hello there"
        },
    ]
    
    for msg in messages:
        body = json.dumps(msg)
        signature = calculate_signature(webhook_secret, body)
        client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature
            }
        )


def test_get_stats_empty():
    """Test GET /stats with no messages."""
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_messages"] == 0
    assert data["senders_count"] == 0
    assert data["messages_per_sender"] == []
    assert data["first_message_ts"] is None
    assert data["last_message_ts"] is None


def test_get_stats_with_messages(webhook_secret, monkeypatch):
    """Test GET /stats with messages."""
    seed_messages(webhook_secret, monkeypatch)
    
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    
    assert "total_messages" in data
    assert "senders_count" in data
    assert "messages_per_sender" in data
    assert "first_message_ts" in data
    assert "last_message_ts" in data
    
    assert data["total_messages"] >= 3
    assert data["senders_count"] >= 2
    assert len(data["messages_per_sender"]) <= 10
    assert data["first_message_ts"] is not None
    assert data["last_message_ts"] is not None
    
    # Check messages_per_sender structure
    for sender in data["messages_per_sender"]:
        assert "from" in sender
        assert "count" in sender
        assert isinstance(sender["count"], int)


def test_get_stats_top_senders(webhook_secret, monkeypatch):
    """Test GET /stats returns top 10 senders sorted by count."""
    seed_messages(webhook_secret, monkeypatch)
    
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    
    if len(data["messages_per_sender"]) > 1:
        # Should be sorted by count descending
        for i in range(len(data["messages_per_sender"]) - 1):
            assert data["messages_per_sender"][i]["count"] >= data["messages_per_sender"][i + 1]["count"]
    
    # Should not exceed 10 senders
    assert len(data["messages_per_sender"]) <= 10

