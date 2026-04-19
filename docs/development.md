# Nova-OS Development Guide

## Setup Development Environment

### Prerequisites
- Python 3.11+
- Git
- Telegram Bot Token

### Clone and Setup

```bash
# Clone
git clone https://github.com/mamun/nova-os.git
cd nova-os

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate  # Windows

# Install dependencies
pip install -r nova_os/requirements.txt
pip install -r requirements-dev.txt

# Setup pre-commit hooks (optional)
pre-commit install
```

### Configuration

```bash
# Create config directory
mkdir -p ~/.config/nova-os

# Create config file
cat > ~/.config/nova-os/config.yaml << 'EOF'
bot:
  token: "your_bot_token"
  owner_id: your_user_id

model:
  provider: ollama
  model: llama3.2:3b
EOF
```

### Start Ollama

```bash
# Install Ollama if not already
curl -fsSL https://ollama.com/install.sh | sh

# Start server
ollama serve

# Pull model
ollama pull llama3.2:3b
```

### Run Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=nova_os

# Specific test
pytest tests/test_memory.py

# Verbose
pytest -v
```

### Run Bot Locally

```bash
# From repo root
python3 -m nova_os.main start

# Or with module path
PYTHONPATH=. python3 nova_os/main.py start
```

---

## Code Style

We use:
- **Black** for formatting
- **flake8** for linting
- **mypy** for type checking (optional)

### Check Style

```bash
# Format
black nova_os/

# Lint
flake8 nova_os/

# Type check (optional)
mypy nova_os/
```

---

## Project Structure

```
nova-os/
├── nova_os/           # Main package
│   ├── __init__.py    # Version info
│   ├── main.py        # CLI entry
│   ├── bot.py         # Telegram bot
│   ├── ai_engine.py   # AI communication
│   ├── memory.py      # Conversation storage
│   └── commands.py    # Command handlers
├── tests/             # Test suite
├── install/           # Installation scripts
├── docs/              # Documentation
└── README.md          # Main docs
```

---

## Adding Features

### New Command

1. Add method in `commands.py`:

```python
async def my_command(self, message: Message):
    """My new command."""
    await message.answer("Hello!")
```

2. Register in `bot.py`:

```python
@dp.message(Command("mycommand"))
async def cmd_mycommand(message: Message):
    if not is_owner(message): return
    await commands.my_command(message)
```

3. Document in `docs/commands.md`

### New AI Provider

1. Add method in `ai_engine.py`:

```python
async def _my_provider_chat(self, messages: List[Dict]) -> str:
    # Implementation
    pass
```

2. Update `_cloud_chat()` to route to new provider

3. Add config option

### Custom Memory Backend

1. Create new class implementing MemoryManager interface
2. Update config to select backend
3. Update initialization logic

---

## Testing

### Unit Tests

```python
def test_my_feature():
    """Test description."""
    # Arrange
    obj = MyClass()
    
    # Act
    result = obj.method()
    
    # Assert
    assert result == expected
```

### Async Tests

```python
@pytest.mark.asyncio
async def test_async_feature():
    result = await my_async_function()
    assert result == expected
```

### Fixtures

```python
@pytest.fixture
def mock_db():
    """Provide mock database."""
    return Mock()
```

---

## Docker Development

```bash
# Build image
docker build -t nova-os:dev .

# Run with dev config
docker run -it --rm \
  -e BOT_TOKEN=your_token \
  -e OWNER_ID=your_id \
  -v $(pwd)/nova_os:/app/nova_os \
  nova-os:dev bash

# Hot reload (mount code)
docker run -it --rm \
  -e BOT_TOKEN=your_token \
  -v $(pwd):/app \
  nova-os:dev python3 -m nova_os.main start
```

---

## Debugging

### Enable Debug Logging

```yaml
# config.yaml
logging:
  level: DEBUG
```

### View Logs

```bash
tail -f ~/.config/nova-os/nova-os.log
```

### Telegram Debug

In `bot.py`, add:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## Release Process

1. Update version in `__init__.py`
2. Update CHANGELOG.md
3. Run tests: `pytest`
4. Create git tag: `git tag v0.1.0`
5. Push tag: `git push origin v0.1.0`
6. GitHub Actions builds and releases

---

## Contributing

1. Fork repository
2. Create feature branch: `git checkout -b feature/name`
3. Make changes
4. Run tests: `pytest`
5. Format code: `black nova_os/`
6. Commit: `git commit -m "Add feature"`
7. Push: `git push origin feature/name`
8. Open Pull Request

---

## Resources

- [aiogram docs](https://docs.aiogram.dev/)
- [Ollama docs](https://github.com/ollama/ollama)
- [Python Telegram Bot examples](https://github.com/python-telegram-bot/python-telegram-bot/wiki)