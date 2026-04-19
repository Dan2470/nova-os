"""Tests for memory module."""
import tempfile
from pathlib import Path

import pytest

from nova_os.memory import MemoryManager


@pytest.fixture
def temp_memory():
    """Create temporary memory instance."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            'enabled': True,
            'db_path': Path(tmpdir) / 'test.db'
        }
        yield MemoryManager(config)


def test_add_exchange(temp_memory):
    """Test adding conversation exchange."""
    temp_memory.add_exchange(123, "Hello", "Hi there!")
    history = temp_memory.get_thread(123)
    
    assert len(history) == 1
    assert history[0]['user'] == "Hello"
    assert history[0]['assistant'] == "Hi there!"


def test_get_thread_limit(temp_memory):
    """Test thread limit."""
    for i in range(15):
        temp_memory.add_exchange(123, f"msg{i}", f"reply{i}")
    
    # Should return only last 10
    history = temp_memory.get_thread(123, limit=10)
    assert len(history) == 10


def test_clear_thread(temp_memory):
    """Test clearing conversation."""
    temp_memory.add_exchange(123, "Hello", "Hi!")
    temp_memory.clear_thread(123)
    history = temp_memory.get_thread(123)
    
    assert len(history) == 0


def test_store_and_get_facts(temp_memory):
    """Test user facts."""
    temp_memory.store_fact(123, "name", "Mamun")
    temp_memory.store_fact(123, "city", "Dhaka")
    
    facts = temp_memory.get_facts(123)
    assert facts["name"] == "Mamun"
    assert facts["city"] == "Dhaka"


def test_disabled_memory():
    """Test disabled memory."""
    config = {'enabled': False}
    mem = MemoryManager(config)
    
    mem.add_exchange(123, "Hello", "Hi!")
    history = mem.get_thread(123)
    
    assert history == []