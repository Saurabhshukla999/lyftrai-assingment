"""Pytest configuration and fixtures."""
import os
import pytest
from pathlib import Path

# Set TESTING environment variable before any imports
os.environ["TESTING"] = "1"

# Set a default WEBHOOK_SECRET for tests if not already set
if "WEBHOOK_SECRET" not in os.environ:
    os.environ["WEBHOOK_SECRET"] = "test-secret-key"

# Use test database
os.environ["DATABASE_URL"] = "sqlite:///./test.db"


@pytest.fixture(autouse=True)
def cleanup_test_db():
    """Clean up test database after each test."""
    yield
    # Clean up test database file if it exists
    test_db = Path("test.db")
    if test_db.exists():
        test_db.unlink()

