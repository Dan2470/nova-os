"""Tests for AI engine."""
import pytest
from unittest.mock import Mock, patch

from nova_os.ai_engine import AIEngine


@pytest.fixture
def mock_memory():
    """Mock memory manager."""
    mem = Mock()
    mem.get_thread.return_value = []
    mem.add_exchange = Mock()
    return mem


@pytest.fixture
def ai_engine(mock_memory):
    """Create AI engine with mock memory."""
    config = {
        'provider': 'ollama',
        'model': 'llama3.2:3b',
        'ollama_base_url': 'http://localhost:11434'
    }
    return AIEngine(config, mock_memory)


def test_load_system_prompt(ai_engine):
    """Test system prompt loading."""
    assert "Nova-OS" in ai_engine.system_prompt
    assert "Ollama" in ai_engine.system_prompt


@pytest.mark.asyncio
@patch('nova_os.ai_engine.OllamaClient')
async def test_chat_success(mock_ollama_class, ai_engine, mock_memory):
    """Test successful chat."""
    # Mock Ollama response
    mock_ollama = Mock()
    mock_ollama_class.return_value = mock_ollama
    mock_ollama.chat.return_value = {
        'message': {'content': 'Hello! How can I help?'}
    }
    
    response = await ai_engine.chat(123, "Hi!")
    
    assert response == 'Hello! How can I help?'
    mock_memory.add_exchange.assert_called_once()


def test_generate_code_prompt(ai_engine):
    """Test code generation prompt."""
    prompt = "Write a function"
    language = "python"
    
    # Check prompt contains required elements
    code_prompt = ai_engine._load_system_prompt()
    assert "Nova-OS" in code_prompt


def test_cloud_fallback_config():
    """Test cloud fallback configuration."""
    config = {
        'provider': 'openai',
        'model': 'llama3.2:3b',
        'cloud_model': 'gpt-3.5-turbo',
        'api_key': 'test-key'
    }
    engine = AIEngine(config, Mock())
    
    assert engine.cloud_provider == 'openai'
    assert engine.cloud_model == 'gpt-3.5-turbo'
    assert engine.api_key == 'test-key'
