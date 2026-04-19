# Nova-OS

> 🚀 **Personal AI Agent for Telegram** — Run locally, powered by Ollama

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Nova-OS is a **self-hosted AI agent** that runs on your machine and communicates via Telegram. No cloud API costs, no vendor lock-in — just your personal AI assistant.

## ✨ Features

- 🤖 **Local AI** — Powered by llama3.2:3b via Ollama (free, private)
- ☁️ **Cloud Fallback** — Optional OpenAI/Google Gemini for complex tasks
- 💬 **Memory** — Remembers conversations across sessions
- 🛠️ **System Commands** — Run shell commands from Telegram
- 📝 **Code Generation** — Ask for code, get working examples
- 🔒 **Secure** — Only you can access it (owner-verified)
- 🔧 **One-Command Install** — Fully automatic, zero prompts

## 🚀 Quick Start

### One-Line Install (Non-Interactive)

```bash
# With bot token — fully automatic, no prompts:
NOVA_BOT_TOKEN='123456:ABCdef...' NOVA_OWNER_ID='123456789' \
  curl -sSL https://raw.githubusercontent.com/Dan2470/nova-os/main/install/install.sh | bash
```

That's it. The bot installs, configures, and starts as a systemd service automatically.

### Install First, Configure Later

```bash
# Install everything, configure later:
curl -sSL https://raw.githubusercontent.com/Dan2470/nova-os/main/install/install.sh | bash

# Then set your token:
export NOVA_BOT_TOKEN='123456:ABCdef...'
export NOVA_OWNER_ID='123456789'
nova-os start
```

### All Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NOVA_BOT_TOKEN` | Yes* | Telegram bot token from [@BotFather](https://t.me/BotFather) |
| `NOVA_OWNER_ID` | Yes* | Your Telegram user ID from [@userinfobot](https://t.me/userinfobot) |
| `NOVA_AUTO_START` | No | Auto-start service after install (`1` = yes, default) |
| `NOVA_MODEL` | No | Ollama model to pull (default: `llama3.2:3b`) |
| `NOVA_CLOUD_PROVIDER` | No | Cloud fallback: `openai`, `google`, `anthropic` |
| `NOVA_CLOUD_API_KEY` | No | API key for cloud fallback |
| `NOVA_INSTALL_DIR` | No | Custom install directory (default: `~/.nova-os`) |
| `NOVA_CONFIG_DIR` | No | Custom config directory (default: `~/.config/nova-os`) |
| `NOVA_SKIP_OLLAMA` | No | Skip Ollama install (`1` = skip) |

*\*Can be omitted during install — bot will prompt on first run or you can edit config manually.*

### Manual Install

```bash
# 1. Clone
git clone https://github.com/Dan2470/nova-os.git
cd nova-os

# 2. Install dependencies
pip3 install -r nova_os/requirements.txt

# 3. Set env vars and start
export NOVA_BOT_TOKEN='your-token'
export NOVA_OWNER_ID='your-id'
python3 -m nova_os.main start
```

### Interactive Setup (Optional)

```bash
python3 -m nova_os.main setup
```

The wizard will ask for your bot token, owner ID, and optional features interactively.

## 📋 What the Installer Does

1. ✅ Detects OS and installs dependencies (Python 3.11+, pip, git)
2. ✅ Installs Ollama (if not present) and pulls the AI model
3. ✅ Clones Nova-OS into `~/.nova-os`
4. ✅ Creates a Python virtual environment with all dependencies
5. ✅ Generates config from environment variables (or creates placeholder)
6. ✅ Creates `nova-os` CLI command in `~/.local/bin/`
7. ✅ Sets up systemd service for auto-start (Linux)
8. ✅ Starts the bot — terminal returns immediately

## 🎮 Usage

### CLI Commands

```bash
nova-os start     # Start the bot (foreground)
nova-os daemon    # Start as background daemon
nova-os stop      # Stop the bot
nova-os status    # Check if running
nova-os config    # Edit configuration
nova-os logs      # View recent logs
nova-os setup     # Interactive setup wizard
```

### Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Show all commands |
| `/status` | System health (CPU, RAM, disk) |
| `/exec <cmd>` | Run shell command |
| `/memory` | Conversation stats |
| `/clear` | Clear conversation |

### Natural Chat

Just message normally — Nova-OS remembers context:

> **You:** "What's my name?"  
> **Bot:** "I don't know yet. What's your name?"  
> **You:** "I'm Mamun"  
> **Bot:** "Nice to meet you, Mamun!"  
> **You:** "What's my name again?"  
> **Bot:** "Your name is Mamun!"  

### Systemd (Linux)

```bash
systemctl status nova-os    # Check status
systemctl restart nova-os   # Restart
systemctl stop nova-os      # Stop
journalctl -u nova-os -f    # Follow logs
```

## 🐳 Docker

```bash
# Build
docker build -t nova-os .

# Run
docker run -d \
  -e BOT_TOKEN=your_token \
  -e OWNER_ID=your_id \
  -v ~/.config/nova-os:/data \
  --network host \
  nova-os
```

## 🛠️ Development

```bash
# Setup dev environment
python3 -m venv venv
source venv/bin/activate
pip3 install -e ".[dev]"

# Run tests
pytest

# Lint
flake8 nova_os/
black nova_os/
```

## 📚 Documentation

- [Architecture](docs/architecture.md) — How it works
- [Commands](docs/commands.md) — Available features
- [Development](docs/development.md) — Contributing guide
- [API Reference](docs/api.md) — Internal APIs

## 🤝 Contributing

1. Fork it
2. Create branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -am 'Add amazing feature'`)
4. Push (`git push origin feature/amazing`)
5. Open a Pull Request

## 📜 License

MIT © Mamun

---

**Built with ❤️ using Python, Ollama, and aiogram**