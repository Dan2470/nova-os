# Nova-OS Architecture

## Overview

Nova-OS is a personal AI agent that runs locally and communicates via Telegram.

## System Architecture

```
┌─────────────────────────────────────────┐
│              Telegram                   │
│              (User)                     │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│           Telegram API                  │
│         (aiogram library)               │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│            Nova-OS Core                 │
│  ┌──────────┐  ┌──────────┐            │
│  │  Bot     │  │ Commands │            │
│  │ Handler  │  │ Handler  │            │
│  └──────────┘  └──────────┘            │
│  ┌──────────┐  ┌──────────┐            │
│  │   AI     │  │ Memory   │            │
│  │ Engine   │  │ Manager  │            │
│  └──────────┘  └──────────┘            │
└──────────────────┬──────────────────────┘
                   │
       ┌───────────┴───────────┐
       ▼                       ▼
┌──────────────┐        ┌──────────────┐
│   Ollama     │        │   SQLite     │
│  (Primary)   │        │  (Memory)    │
└──────────────┘        └──────────────┘
       │
       ▼ (Fallback)
┌──────────────┐
│ Cloud APIs   │
│ (OpenAI/etc) │
└──────────────┘
```

## Components

### 1. Bot Handler (`bot.py`)
- Manages Telegram connection
- Routes messages to handlers
- Security: Owner verification
- Session management

### 2. AI Engine (`ai_engine.py`)
- Primary: Ollama (local)
- Fallback: Cloud APIs
- Message formatting
- Context building

### 3. Memory Manager (`memory.py`)
- SQLite storage
- Conversation threads
- User facts
- Statistics

### 4. Command Handler (`commands.py`)
- `/status` - System health
- `/exec` - Shell execution
- `/help` - Documentation
- Security: Forbidden commands

## Data Flow

```
1. User sends message via Telegram
2. Bot receives update via webhook/polling
3. Security check: Is owner?
4. If command → Command Handler
5. If chat → AI Engine
6. AI Engine:
   a. Fetch context from Memory
   b. Call Ollama (or fallback)
   c. Save response to Memory
7. Send response to user
```

## Security

### Owner Verification
```python
def _is_owner(self, message) -> bool:
    return message.from_user.id == self.config['bot']['owner_id']
```

### Command Filtering
```python
forbidden = ["rm -rf /", "mkfs", "dd if=/dev/zero"]
```

### Execution Limits
- Timeout: 30 seconds
- Output limit: 3500 characters
- No subprocess chains

## Memory Schema

### conversations table
```sql
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    timestamp REAL NOT NULL,
    user_message TEXT NOT NULL,
    assistant_response TEXT,
    metadata TEXT
);
```

### user_facts table
```sql
CREATE TABLE user_facts (
    user_id INTEGER PRIMARY KEY,
    facts TEXT,  -- JSON
    updated_at REAL
);
```

## Configuration

```yaml
bot:
  token: "telegram_bot_token"
  owner_id: 123456789

model:
  provider: ollama
  model: llama3.2:3b
  ollama_base_url: http://localhost:11434
  # Optional fallback:
  # cloud_provider: openai
  # api_key: "..."

memory:
  enabled: true
  db_path: ~/.config/nova-os/memory.db
```

## Deployment Options

1. **Bare Metal** - Direct install
2. **Docker** - Containerized
3. **Docker Compose** - With Ollama
4. **VPS Cloud** - Remote server

## Extending

### Add New Command

1. Add handler in `commands.py`
2. Register in `bot.py` handlers
3. Document in README

### Add New AI Provider

1. Add method in `ai_engine.py`
2. Update config schema
3. Add provider detection

### Custom Memory Backend

1. Implement interface in `memory.py`
2. Add config option
3. Update initialization