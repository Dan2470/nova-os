"""
Memory Manager: Persistent conversation and knowledge storage.
Uses SQLite for simplicity and zero-config setup.
"""
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Nova-OS")

class MemoryManager:
    """Manages conversation history and user context."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('enabled', True)
        self.db_path = Path(config.get('db_path', '~/.config/nova-os/memory.db')).expanduser()
        
        if self.enabled:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()
    
    def _init_db(self):
        """Initialize SQLite schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    timestamp REAL NOT NULL,
                    user_message TEXT NOT NULL,
                    assistant_response TEXT,
                    metadata TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_facts (
                    user_id INTEGER PRIMARY KEY,
                    facts TEXT,
                    updated_at REAL
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_user_time 
                ON conversations(user_id, timestamp DESC)
            """)
            
            conn.commit()
    
    def add_exchange(self, user_id: int, user_msg: str, assistant_msg: str, 
                     metadata: Optional[Dict] = None):
        """Add a conversation exchange."""
        if not self.enabled:
            return
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO conversations 
                   (user_id, timestamp, user_message, assistant_response, metadata)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, time.time(), user_msg, assistant_msg, 
                 json.dumps(metadata) if metadata else None)
            )
            conn.commit()
    
    def get_thread(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get conversation history for a user."""
        if not self.enabled:
            return []
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """SELECT user_message, assistant_response, timestamp, metadata
                   FROM conversations
                   WHERE user_id = ?
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (user_id, limit)
            )
            rows = cursor.fetchall()
            
            # Return in chronological order
            return [
                {
                    'user': row['user_message'],
                    'assistant': row['assistant_response'],
                    'timestamp': row['timestamp'],
                    'metadata': json.loads(row['metadata']) if row['metadata'] else None
                }
                for row in reversed(rows)
            ]
    
    def clear_thread(self, user_id: int):
        """Clear conversation history for a user."""
        if not self.enabled:
            return
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM conversations WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()
    
    def get_stats(self) -> str:
        """Get memory statistics."""
        if not self.enabled:
            return "Memory is disabled"
        
        with sqlite3.connect(self.db_path) as conn:
            # Total exchanges
            total = conn.execute(
                "SELECT COUNT(*) FROM conversations"
            ).fetchone()[0]
            
            # Unique users
            users = conn.execute(
                "SELECT COUNT(DISTINCT user_id) FROM conversations"
            ).fetchone()[0]
            
            # Recent (last 24h)
            recent = conn.execute(
                "SELECT COUNT(*) FROM conversations WHERE timestamp > ?",
                (time.time() - 86400,)
            ).fetchone()[0]
            
            # DB size
            db_size = self.db_path.stat().st_size
            
        return (
            f"📊 **Statistics**\n\n"
            f"• Total exchanges: {total}\n"
            f"• Unique users: {users}\n"
            f"• Last 24h: {recent}\n"
            f"• Database size: {db_size / 1024:.1f} KB"
        )
    
    def store_fact(self, user_id: int, key: str, value: str):
        """Store a user-specific fact."""
        if not self.enabled:
            return
        
        with sqlite3.connect(self.db_path) as conn:
            # Get existing facts
            row = conn.execute(
                "SELECT facts FROM user_facts WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            
            facts = json.loads(row[0]) if row else {}
            facts[key] = value
            
            conn.execute(
                """INSERT OR REPLACE INTO user_facts (user_id, facts, updated_at)
                   VALUES (?, ?, ?)""",
                (user_id, json.dumps(facts), time.time())
            )
            conn.commit()
    
    def get_facts(self, user_id: int) -> Dict[str, str]:
        """Get stored facts for a user."""
        if not self.enabled:
            return {}
        
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT facts FROM user_facts WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            
            return json.loads(row[0]) if row else {}
