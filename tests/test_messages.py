"""Tests for messages endpoint."""
import pytest
import hmac
import hashlib
import json
from fastapi.testclient import TestClient
from main import app
from storage import Storage
from config import settings

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
    """Seed test messages."""
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


def test_get_messages_default(webhook_secret, monkeypatch):
    """Test GET /messages with default parameters."""
    seed_messages(webhook_secret, monkeypatch)
    
    response = client.get("/messages")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert data["limit"] == 50
    assert data["offset"] == 0
    assert len(data["data"]) <= 50


def test_get_messages_limit_offset(webhook_secret, monkeypatch):
    """Test GET /messages with limit and offset."""
    seed_messages(webhook_secret, monkeypatch)
    
    response = client.get("/messages?limit=2&offset=1")
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 2
    assert data["offset"] == 1
    assert len(data["data"]) <= 2


def test_get_messages_filter_from(webhook_secret, monkeypatch):
    """Test GET /messages with from filter."""
    seed_messages(webhook_secret, monkeypatch)
    
    response = client.get("/messages?from=%2B919876543210")
    assert response.status_code == 200
    data = response.json()
    assert all(msg["from"] == "+919876543210" for msg in data["data"])


def test_get_messages_filter_since(webhook_secret, monkeypatch):
    """Test GET /messages with since filter."""
    seed_messages(webhook_secret, monkeypatch)
    
    response = client.get("/messages?since=2025-01-15T10:01:00Z")
    assert response.status_code == 200
    data = response.json()
    # All messages should have ts >= since
    for msg in data["data"]:
        assert msg["ts"] >= "2025-01-15T10:01:00Z"


def test_get_messages_filter_q(webhook_secret, monkeypatch):
    """Test GET /messages with text search."""
    seed_messages(webhook_secret, monkeypatch)
    
    response = client.get("/messages?q=Hello")
    assert response.status_code == 200
    data = response.json()
    # All messages should contain "Hello" in text (case-insensitive)
    for msg in data["data"]:
        if msg["text"]:
            assert "hello" in msg["text"].lower()


def test_get_messages_ordering(webhook_secret, monkeypatch):
    """Test GET /messages ordering (ts ASC, message_id ASC)."""
    seed_messages(webhook_secret, monkeypatch)
    
    response = client.get("/messages")
    assert response.status_code == 200
    data = response.json()
    
    if len(data["data"]) > 1:
        for i in range(len(data["data"]) - 1):
            msg1 = data["data"][i]
            msg2 = data["data"][i + 1]
            # ts should be ascending, or if equal, message_id should be ascending
            assert msg1["ts"] < msg2["ts"] or (
                msg1["ts"] == msg2["ts"] and msg1["message_id"] <= msg2["message_id"]
            )


def test_get_messages_limit_validation():
    """Test GET /messages limit validation."""
    response = client.get("/messages?limit=0")
    assert response.status_code == 422
    
    response = client.get("/messages?limit=101")
    assert response.status_code == 422


def test_get_messages_offset_validation():
    """Test GET /messages offset validation."""
    response = client.get("/messages?offset=-1")
    assert response.status_code == 422

