# Nova-OS Commands Reference

## Telegram Commands

### /start
**Description:** Welcome message and bot introduction

**Usage:** `/start`

**Output:**
- Bot status
- Feature list
- Available commands

---

### /help
**Description:** Show all available commands

**Usage:** `/help`

**Output:**
- Complete command list
- Usage examples

---

### /status
**Description:** System health information

**Usage:** `/status`

**Output:**
- Current time
- CPU load
- Memory usage
- Disk usage

---

### /exec
**Description:** Execute shell command

**Usage:** `/exec <command>`

**Examples:**
```
/exec ls -la
/exec python --version
/exec cat /etc/os-release
/exec df -h
```

**Security:**
- Forbidden commands: `rm -rf /`, `mkfs`, `dd if=/dev/zero`, fork bombs
- Timeout: 30 seconds
- Output limit: 3500 characters

---

### /memory
**Description:** Show memory statistics

**Usage:** `/memory`

**Output:**
- Total exchanges
- Unique users
- Last 24h activity
- Database size

---

### /clear
**Description:** Clear conversation history

**Usage:** `/clear`

**Effect:**
- Removes all messages for current user
- Memory persists until cleared

---

## Natural Chat

No command needed — just message normally.

**Features:**
- Context awareness (remembers previous messages)
- Multi-language support
- Code generation (just ask)

**Examples:**
```
User: What's 2+2?
Bot: 4

User: And multiplied by 5?
Bot: 20

User: Write a Python function to reverse a string
Bot: [code]

User: What's my name? (if told before)
Bot: Your name is Mamun
```

---

## CLI Commands

### nova-os start
Start the bot.

```bash
nova-os start
```

### nova-os status
Check if bot is running.

```bash
nova-os status
```

### nova-os config
Open configuration in editor.

```bash
nova-os config
```

### nova-os logs
View recent logs.

```bash
nova-os logs
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | Telegram bot token |
| `OWNER_ID` | Your Telegram user ID |
| `OLLAMA_BASE_URL` | Ollama server URL |
| `LOG_LEVEL` | DEBUG/INFO/WARNING/ERROR |

---

## Configuration File

Location: `~/.config/nova-os/config.yaml`

```yaml
bot:
  token: "your_token"
  owner_id: 123456789

model:
  provider: ollama
  model: llama3.2:3b

memory:
  enabled: true
  storage: sqlite

features:
  system_commands: true
  web_search: true
  file_operations: true
```