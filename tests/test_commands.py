"""Tests for commands module."""
import pytest
from unittest.mock import Mock, AsyncMock

from nova_os.commands import CommandHandler


@pytest.fixture
def mock_bot():
    """Mock bot instance."""
    bot = Mock()
    bot.bot = Mock()
    bot.ai = Mock()
    bot.config = {'bot': {'owner_id': 123}}
    return bot


@pytest.fixture
def command_handler(mock_bot):
    """Create command handler."""
    return CommandHandler(mock_bot)


@pytest.mark.asyncio
async def test_help_command(command_handler):
    """Test help command."""
    message = AsyncMock()
    await command_handler.help(message)
    
    message.answer.assert_called_once()
    call_args = message.answer.call_args[0][0]
    assert "/status" in call_args
    assert "/exec" in call_args


@pytest.mark.asyncio
async def test_status_command(command_handler):
    """Test status command."""
    message = AsyncMock()
    await command_handler.status(message)
    
    message.answer.assert_called_once()
    call_args = message.answer.call_args[0][0]
    assert "System Status" in call_args


@pytest.mark.asyncio
async def test_execute_empty_command(command_handler):
    """Test exec with no command."""
    message = AsyncMock()
    message.text = "/exec"
    
    await command_handler.execute(message)
    
    message.answer.assert_called_once()
    call_args = message.answer.call_args[0][0]
    assert "Usage" in call_args


@pytest.mark.asyncio
async def test_execute_forbidden_command(command_handler):
    """Test exec with forbidden command."""
    message = AsyncMock()
    message.text = "/exec rm -rf /"
    
    await command_handler.execute(message)
    
    message.answer.assert_called_once()
    call_args = message.answer.call_args[0][0]
    assert "Security Alert" in call_args