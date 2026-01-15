"""Database models and initialization."""
import sqlite3
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def get_db_path(database_url: str) -> Path:
    """Extract database path from SQLite URL."""
    # Remove sqlite:/// prefix
    path_str = database_url.replace("sqlite:///", "")
    return Path(path_str)


def init_db(database_url: str) -> None:
    """Initialize the database with the required schema."""
    db_path = get_db_path(database_url)
    
    # Create parent directory if it doesn't exist
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id TEXT PRIMARY KEY,
            from_msisdn TEXT NOT NULL,
            to_msisdn TEXT NOT NULL,
            ts TEXT NOT NULL,
            text TEXT,
            created_at TEXT NOT NULL
        )
    """)
    
    # Create index for common queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ts ON messages(ts)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_from_msisdn ON messages(from_msisdn)
    """)
    
    conn.commit()
    conn.close()
    
    logger.info(f"Database initialized at {db_path}")

