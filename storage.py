"""Database storage operations."""
import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class Storage:
    """Database storage operations for messages."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.db_path = self._get_db_path()
    
    def _get_db_path(self) -> Path:
        """Extract database path from SQLite URL."""
        path_str = self.database_url.replace("sqlite:///", "")
        return Path(path_str)
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn
    
    def insert_message(
        self,
        message_id: str,
        from_msisdn: str,
        to_msisdn: str,
        ts: str,
        text: Optional[str],
    ) -> bool:
        """
        Insert a message. Returns True if inserted, False if duplicate.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            created_at = datetime.utcnow().isoformat() + "Z"
            cursor.execute("""
                INSERT INTO messages (message_id, from_msisdn, to_msisdn, ts, text, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (message_id, from_msisdn, to_msisdn, ts, text, created_at))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Duplicate message_id
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def get_messages(
        self,
        limit: int = 50,
        offset: int = 0,
        from_msisdn: Optional[str] = None,
        since: Optional[str] = None,
        q: Optional[str] = None,
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        Get messages with filtering and pagination.
        Returns (messages, total_count).
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Build WHERE clause
        conditions = []
        params = []
        
        if from_msisdn:
            conditions.append("from_msisdn = ?")
            params.append(from_msisdn)
        
        if since:
            conditions.append("ts >= ?")
            params.append(since)
        
        if q:
            # Case-insensitive search
            conditions.append("LOWER(text) LIKE LOWER(?)")
            params.append(f"%{q}%")
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM messages WHERE {where_clause}"
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Get messages
        query = f"""
            SELECT message_id, from_msisdn, to_msisdn, ts, text
            FROM messages
            WHERE {where_clause}
            ORDER BY ts ASC, message_id ASC
            LIMIT ? OFFSET ?
        """
        cursor.execute(query, params + [limit, offset])
        
        rows = cursor.fetchall()
        messages = [
            {
                "message_id": row["message_id"],
                "from": row["from_msisdn"],
                "to": row["to_msisdn"],
                "ts": row["ts"],
                "text": row["text"],
            }
            for row in rows
        ]
        
        conn.close()
        return messages, total
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about messages."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Total messages
        cursor.execute("SELECT COUNT(*) FROM messages")
        total_messages = cursor.fetchone()[0]
        
        if total_messages == 0:
            conn.close()
            return {
                "total_messages": 0,
                "senders_count": 0,
                "messages_per_sender": [],
                "first_message_ts": None,
                "last_message_ts": None,
            }
        
        # Unique senders count
        cursor.execute("SELECT COUNT(DISTINCT from_msisdn) FROM messages")
        senders_count = cursor.fetchone()[0]
        
        # Top 10 senders
        cursor.execute("""
            SELECT from_msisdn as from_msisdn, COUNT(*) as count
            FROM messages
            GROUP BY from_msisdn
            ORDER BY count DESC
            LIMIT 10
        """)
        top_senders = [
            {"from": row["from_msisdn"], "count": row["count"]}
            for row in cursor.fetchall()
        ]
        
        # First and last message timestamps
        cursor.execute("SELECT MIN(ts) FROM messages")
        first_ts = cursor.fetchone()[0]
        
        cursor.execute("SELECT MAX(ts) FROM messages")
        last_ts = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_messages": total_messages,
            "senders_count": senders_count,
            "messages_per_sender": top_senders,
            "first_message_ts": first_ts,
            "last_message_ts": last_ts,
        }
    
    def check_health(self) -> bool:
        """Check if database is accessible."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

