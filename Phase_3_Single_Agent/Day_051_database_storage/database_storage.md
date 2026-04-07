# Storing Conversations in SQLite & PostgreSQL

For production agents, you need durable storage. This guide shows you how to store conversation threads in SQLite (for development) and PostgreSQL (for production).

> **Coming from Software Engineering?** Database storage for agents is just application persistence. If you've designed database schemas for user sessions, audit logs, or event sourcing, you already know how to model conversational data. The schema here (conversations, messages, metadata) maps directly to patterns you've built before.

---

## Why Database Storage?

```mermaid
flowchart TB
    subgraph "In-Memory"
        A["Fast"] --> B["Lost on restart"]
        B --> C["Single process only"]
    end

    subgraph "Database Storage"
        D["Persists forever"] --> E["Survives restarts"]
        E --> F["Multi-process safe"]
        F --> G["Queryable history"]
    end

    style C fill:#ff6b6b
    style G fill:#90EE90
```

Benefits:
- **Persistence**: Survives server restarts
- **Scalability**: Multiple servers can access
- **History**: Query past conversations
- **Compliance**: Audit trails and logging

---

## SQLite for Development

SQLite is perfect for local development and small deployments:

```python
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional

class SQLiteConversationStore:
    """Store conversations in SQLite."""

    def __init__(self, db_path: str = "conversations.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_tables()

    def _create_tables(self):
        """Create necessary tables."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conversation
            ON messages(conversation_id, timestamp);

            CREATE INDEX IF NOT EXISTS idx_conversations_user
            ON conversations(user_id);
        """)
        self.conn.commit()

    def create_conversation(self, user_id: str, title: str = None, metadata: dict = None) -> str:
        """Create a new conversation."""
        import uuid
        conv_id = str(uuid.uuid4())

        self.conn.execute(
            "INSERT INTO conversations (id, user_id, title, metadata) VALUES (?, ?, ?, ?)",
            (conv_id, user_id, title or "New Conversation", json.dumps(metadata or {}))
        )
        self.conn.commit()
        return conv_id

    def add_message(self, conversation_id: str, role: str, content: str, metadata: dict = None):
        """Add a message to a conversation."""
        self.conn.execute(
            "INSERT INTO messages (conversation_id, role, content, metadata) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, json.dumps(metadata or {}))
        )
        self.conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (datetime.now(), conversation_id)
        )
        self.conn.commit()

    def get_messages(self, conversation_id: str, limit: int = 50) -> List[Dict]:
        """Get messages for a conversation."""
        cursor = self.conn.execute(
            """SELECT role, content, timestamp, metadata
               FROM messages
               WHERE conversation_id = ?
               ORDER BY timestamp ASC
               LIMIT ?""",
            (conversation_id, limit)
        )

        return [
            {
                "role": row[0],
                "content": row[1],
                "timestamp": row[2],
                "metadata": json.loads(row[3])
            }
            for row in cursor.fetchall()
        ]

    def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """Get conversation details with messages."""
        cursor = self.conn.execute(
            "SELECT id, user_id, title, created_at, metadata FROM conversations WHERE id = ?",
            (conversation_id,)
        )
        row = cursor.fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "user_id": row[1],
            "title": row[2],
            "created_at": row[3],
            "metadata": json.loads(row[4]),
            "messages": self.get_messages(conversation_id)
        }

    def list_conversations(self, user_id: str, limit: int = 20) -> List[Dict]:
        """List conversations for a user."""
        cursor = self.conn.execute(
            """SELECT id, title, created_at, updated_at
               FROM conversations
               WHERE user_id = ?
               ORDER BY updated_at DESC
               LIMIT ?""",
            (user_id, limit)
        )

        return [
            {"id": row[0], "title": row[1], "created_at": row[2], "updated_at": row[3]}
            for row in cursor.fetchall()
        ]

    def delete_conversation(self, conversation_id: str):
        """Delete a conversation and its messages."""
        self.conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        self.conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        self.conn.commit()

# Usage
store = SQLiteConversationStore()

# Create conversation
conv_id = store.create_conversation("user-123", "Help with Python")

# Add messages
store.add_message(conv_id, "user", "How do I read a file?")
store.add_message(conv_id, "assistant", "You can use open() function...")

# Retrieve
conversation = store.get_conversation(conv_id)
print(conversation)
```

---

## PostgreSQL for Production

PostgreSQL provides better concurrency and scaling:

```python
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from datetime import datetime
from typing import List, Dict, Optional
import uuid

class PostgresConversationStore:
    """Production-ready PostgreSQL conversation store."""

    def __init__(self, connection_string: str):
        """
        Initialize with connection string like:
        "postgresql://user:password@localhost:5432/dbname"
        """
        self.conn = psycopg2.connect(connection_string)
        self._create_tables()

    def _create_tables(self):
        """Create tables if they don't exist."""
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id TEXT NOT NULL,
                    title TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    metadata JSONB DEFAULT '{}'::jsonb
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tokens INTEGER,
                    latency_ms INTEGER,
                    timestamp TIMESTAMPTZ DEFAULT NOW(),
                    metadata JSONB DEFAULT '{}'::jsonb
                );

                CREATE INDEX IF NOT EXISTS idx_messages_conv_time
                ON messages(conversation_id, timestamp);

                CREATE INDEX IF NOT EXISTS idx_conv_user_updated
                ON conversations(user_id, updated_at DESC);

                CREATE INDEX IF NOT EXISTS idx_messages_metadata
                ON messages USING GIN(metadata);
            """)
        self.conn.commit()

    def create_conversation(self, user_id: str, title: str = None, metadata: dict = None) -> str:
        """Create a new conversation."""
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO conversations (user_id, title, metadata)
                   VALUES (%s, %s, %s)
                   RETURNING id""",
                (user_id, title, Json(metadata or {}))
            )
            conv_id = cur.fetchone()[0]
        self.conn.commit()
        return str(conv_id)

    def add_message(self, conversation_id: str, role: str, content: str,
                    tokens: int = None, latency_ms: int = None, metadata: dict = None):
        """Add a message with optional metrics."""
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO messages (conversation_id, role, content, tokens, latency_ms, metadata)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (conversation_id, role, content, tokens, latency_ms, Json(metadata or {}))
            )
            cur.execute(
                "UPDATE conversations SET updated_at = NOW() WHERE id = %s",
                (conversation_id,)
            )
        self.conn.commit()

    def get_messages(self, conversation_id: str, limit: int = 50) -> List[Dict]:
        """Get messages for a conversation."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT role, content, timestamp, tokens, latency_ms, metadata
                   FROM messages
                   WHERE conversation_id = %s
                   ORDER BY timestamp ASC
                   LIMIT %s""",
                (conversation_id, limit)
            )
            return cur.fetchall()

    def get_recent_context(self, conversation_id: str, max_tokens: int = 4000) -> List[Dict]:
        """Get recent messages within a token budget."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get messages in reverse order, accumulate until budget exceeded
            cur.execute(
                """WITH token_sum AS (
                       SELECT *,
                              SUM(COALESCE(tokens, 100)) OVER (ORDER BY timestamp DESC) as running_total
                       FROM messages
                       WHERE conversation_id = %s
                   )
                   SELECT role, content, timestamp
                   FROM token_sum
                   WHERE running_total <= %s
                   ORDER BY timestamp ASC""",
                (conversation_id, max_tokens)
            )
            return cur.fetchall()

    def search_conversations(self, user_id: str, query: str) -> List[Dict]:
        """Full-text search across conversations."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT DISTINCT c.id, c.title, c.updated_at
                   FROM conversations c
                   JOIN messages m ON c.id = m.conversation_id
                   WHERE c.user_id = %s
                   AND m.content ILIKE %s
                   ORDER BY c.updated_at DESC
                   LIMIT 20""",
                (user_id, f"%{query}%")
            )
            return cur.fetchall()

    def get_conversation_stats(self, conversation_id: str) -> Dict:
        """Get statistics for a conversation."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT
                       COUNT(*) as message_count,
                       SUM(tokens) as total_tokens,
                       AVG(latency_ms) as avg_latency_ms,
                       MIN(timestamp) as started_at,
                       MAX(timestamp) as last_message_at
                   FROM messages
                   WHERE conversation_id = %s""",
                (conversation_id,)
            )
            return cur.fetchone()

# Usage
store = PostgresConversationStore("postgresql://localhost/myapp")

conv_id = store.create_conversation("user-123", "Code Help")
store.add_message(conv_id, "user", "Hello!", tokens=5, latency_ms=0)
store.add_message(conv_id, "assistant", "Hi! How can I help?", tokens=10, latency_ms=234)

# Get with token budget
context = store.get_recent_context(conv_id, max_tokens=2000)
```

---

## Integration with LangGraph

Use database storage with LangGraph checkpointing:

```python
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import StateGraph, END

# Create PostgreSQL checkpointer
checkpointer = PostgresSaver.from_conn_string(
    "postgresql://user:pass@localhost:5432/agents"
)

# Build your graph
workflow = StateGraph(AgentState)
# ... add nodes and edges ...

# Compile with PostgreSQL checkpointing
app = workflow.compile(checkpointer=checkpointer)

# Run with thread ID (stored in PostgreSQL)
config = {"configurable": {"thread_id": f"user-{user_id}-conv-{conv_id}"}}
result = app.invoke(initial_state, config=config)
```

---

## Combining Conversation Store with Agent

```python
from openai import OpenAI

class PersistentAgent:
    """Agent with database-backed conversations."""

    def __init__(self, store: SQLiteConversationStore):
        self.store = store
        self.client = OpenAI()

    def chat(self, conversation_id: str, user_message: str) -> str:
        """Process a message and store in database."""

        # Store user message
        self.store.add_message(conversation_id, "user", user_message)

        # Get conversation history
        messages = self.store.get_messages(conversation_id)

        # Format for API
        api_messages = [
            {"role": "system", "content": "You are a helpful assistant."}
        ] + [
            {"role": m["role"], "content": m["content"]}
            for m in messages
        ]

        # Get response
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=api_messages
        )

        assistant_message = response.choices[0].message.content

        # Store assistant response
        self.store.add_message(
            conversation_id,
            "assistant",
            assistant_message,
            metadata={"model": "gpt-4o-mini", "tokens": response.usage.total_tokens}
        )

        return assistant_message

    def start_conversation(self, user_id: str, title: str = None) -> str:
        """Start a new conversation."""
        return self.store.create_conversation(user_id, title)

    def get_history(self, conversation_id: str) -> List[Dict]:
        """Get conversation history."""
        return self.store.get_messages(conversation_id)

# Usage
store = SQLiteConversationStore("my_agent.db")
agent = PersistentAgent(store)

# Start conversation
conv_id = agent.start_conversation("user-456", "Python Help")

# Chat
response1 = agent.chat(conv_id, "How do I sort a list?")
print(response1)

response2 = agent.chat(conv_id, "What about reverse sorting?")
print(response2)

# Later - conversation is saved!
history = agent.get_history(conv_id)
```

---

## Database Schema Best Practices

```mermaid
erDiagram
    users ||--o{ conversations : has
    conversations ||--o{ messages : contains
    conversations ||--o{ checkpoints : stores

    users {
        uuid id PK
        text email
        timestamp created_at
    }

    conversations {
        uuid id PK
        uuid user_id FK
        text title
        jsonb metadata
        timestamp created_at
        timestamp updated_at
    }

    messages {
        serial id PK
        uuid conversation_id FK
        text role
        text content
        int tokens
        int latency_ms
        jsonb metadata
        timestamp timestamp
    }

    checkpoints {
        uuid id PK
        uuid conversation_id FK
        jsonb state
        timestamp created_at
    }
```

---

## Migration Example

Migrate from SQLite to PostgreSQL:

```python
def migrate_sqlite_to_postgres(sqlite_path: str, postgres_conn: str):
    """Migrate data from SQLite to PostgreSQL."""

    import sqlite3
    import psycopg2
    from psycopg2.extras import Json

    # Connect to both
    sqlite_conn = sqlite3.connect(sqlite_path)
    pg_conn = psycopg2.connect(postgres_conn)

    # Migrate conversations
    sqlite_cursor = sqlite_conn.execute("SELECT * FROM conversations")
    with pg_conn.cursor() as pg_cursor:
        for row in sqlite_cursor:
            pg_cursor.execute(
                """INSERT INTO conversations (id, user_id, title, created_at, metadata)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (id) DO NOTHING""",
                (row[0], row[1], row[2], row[3], Json(json.loads(row[5] or '{}')))
            )

    # Migrate messages
    sqlite_cursor = sqlite_conn.execute("SELECT * FROM messages")
    with pg_conn.cursor() as pg_cursor:
        for row in sqlite_cursor:
            pg_cursor.execute(
                """INSERT INTO messages (conversation_id, role, content, timestamp, metadata)
                   VALUES (%s, %s, %s, %s, %s)""",
                (row[1], row[2], row[3], row[4], Json(json.loads(row[5] or '{}')))
            )

    pg_conn.commit()
    print("Migration complete!")

# Usage
migrate_sqlite_to_postgres("local.db", "postgresql://localhost/production")
```

---

## Summary

```mermaid
mindmap
  root((Database Storage))
    SQLite
      Local development
      Single file
      Easy setup
    PostgreSQL
      Production
      Scalable
      Full-text search
      JSONB metadata
    Features
      Message history
      Token tracking
      Search
      Analytics
```

---

## Quick Reference

```python
# SQLite setup
store = SQLiteConversationStore("app.db")

# PostgreSQL setup
store = PostgresConversationStore("postgresql://localhost/db")

# Create conversation
conv_id = store.create_conversation(user_id, "Title")

# Add message
store.add_message(conv_id, "user", "Hello")
store.add_message(conv_id, "assistant", "Hi!", tokens=5)

# Get messages
messages = store.get_messages(conv_id, limit=50)

# LangGraph integration
checkpointer = PostgresSaver.from_conn_string(conn_str)
app = workflow.compile(checkpointer=checkpointer)
```

---

## What's Next?

You've mastered single-agent architectures! Next month, we'll explore **Multi-Agent Systems** where multiple agents work together!
