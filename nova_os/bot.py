"""
Nova-OS Main Bot Module
Handles Telegram messages, AI responses, and memory.
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

import yaml
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from rich.console import Console
from rich.logging import RichHandler

from .social_auth import SocialAuthManager
from .social_actions import SocialMediaManager
from .subagent import SubAgentManager
from .ai_engine import AIEngine
from .memory import MemoryManager
from .commands import CommandHandler

console = Console()

class NovaOS:
    """Main Nova-OS Agent."""

    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self._setup_logging()

        # Initialize components
        self.bot = Bot(token=self.config['bot']['token'])
        self.dp = Dispatcher()

        self.memory = MemoryManager(self.config.get('memory', {}))
        self.ai = AIEngine(self.config.get('model', {}), self.memory)
        self.subagent = SubAgentManager(self.config.get('subagent', {}))
        self.social_auth = SocialAuthManager(self.config.get('social', {}))
        self.social = SocialMediaManager(self.social_auth)
        self.commands = CommandHandler(self)

        self._setup_handlers()

    def _load_config(self, config_path: Optional[str]) -> dict:
        """Load configuration from YAML file with env var overrides."""
        if config_path is None:
            env_dir = os.environ.get("NOVA_CONFIG_DIR")
            if env_dir:
                config_path = os.path.join(env_dir, "config.yaml")
            else:
                config_path = os.path.expanduser("~/.config/nova-os/config.yaml")

        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"Config not found at {config_path}. "
                "Run: curl -sSL ... | bash"
            )

        with open(config_path) as f:
            config = yaml.safe_load(f)

        # Env var overrides (take precedence over config.yaml)
        env_token = os.environ.get("NOVA_BOT_TOKEN")
        env_owner = os.environ.get("NOVA_OWNER_ID")
        env_model = os.environ.get("NOVA_MODEL")

        if env_token:
            config.setdefault('bot', {})['token'] = env_token
        if env_owner:
            config.setdefault('bot', {})['owner_id'] = int(env_owner)
        if env_model:
            config.setdefault('model', {})['model'] = env_model

        return config

    def _setup_logging(self):
        """Setup rich logging."""
        logging.basicConfig(
            level=getattr(logging, self.config.get('logging', {}).get('level', 'INFO')),
            format="%(message)s",
            handlers=[RichHandler(console=console)]
        )
        self.logger = logging.getLogger("Nova-OS")

    def _setup_handlers(self):
        """Register Telegram handlers."""
        @self.dp.message(Command("start"))
        async def cmd_start(message: Message):
            if not self._is_owner(message):
                return
            await message.answer(
                "🚀 **Nova-OS Online!**\n\n"
                "I'm your personal AI assistant. I can:\n"
                "• Chat with you using local AI (llama3.2:3b)\n"
                "• Remember our conversations\n"
                "• Execute system commands\n"
                "• Help with coding, writing, and more\n\n"
                "Commands:\n"
                "/help - Show all commands\n"
                "/status - System status\n"
                "/exec <cmd> - Run command\n"
                "/memory - Show memory stats\n"
                "/clear - Clear conversation\n\n"
                "Just message me to start!",
                parse_mode="Markdown"
            )

        @self.dp.message(Command("help"))
        async def cmd_help(message: Message):
            if not self._is_owner(message):
                return
            await self.commands.help(message)

        @self.dp.message(Command("status"))
        async def cmd_status(message: Message):
            if not self._is_owner(message):
                return
            await self.commands.status(message)

        @self.dp.message(Command("exec"))
        async def cmd_exec(message: Message):
            if not self._is_owner(message):
                return
            await self.commands.execute(message)

        @self.dp.message(Command("memory"))
        async def cmd_memory(message: Message):
            if not self._is_owner(message):
                return
            stats = self.memory.get_stats()
            await message.answer(f"🧠 **Memory Stats**\n\n{stats}")

        @self.dp.message(Command("tasks"))
        async def cmd_tasks(message: Message):
            if not self._is_owner(message):
                return
            stats = self.subagent.get_stats()
            await message.answer(
                f"📋 **Sub-Agent Tasks**\n\n"
                f"Total: {stats['total']}\n"
                f"Running: {stats['running']}\n"
                f"Pending: {stats['pending']}\n"
                f"Completed: {stats['completed']}\n"
                f"Failed: {stats['failed']}",
                parse_mode="Markdown"
            )

        @self.dp.message(Command("agents"))
        async def cmd_agents(message: Message):
            if not self._is_owner(message):
                return
            await self.commands.agents(message)

        @self.dp.message(Command("social"))
        async def cmd_social(message: Message):
            if not self._is_owner(message):
                return
            await self.commands.social(message)

        @self.dp.message(Command("clear"))
        async def cmd_clear(message: Message):
            if not self._is_owner(message):
                return
            self.memory.clear_thread(message.chat.id)
            await message.answer("🗑️ Conversation cleared!")

        @self.dp.message()
        async def handle_message(message: Message):
            if not self._is_owner(message):
                return
            await self._process_chat(message)

    def _is_owner(self, message: Message) -> bool:
        """Check if message is from owner."""
        owner_id = self.config['bot'].get('owner_id')
        if owner_id is None:
            return True  # No owner set, allow all (dev mode)
        return message.from_user.id == int(owner_id)

    async def _process_chat(self, message: Message):
        """Process regular chat message."""
        # Show typing indicator
        await self.bot.send_chat_action(message.chat.id, "typing")

        # Get AI response
        response = await self.ai.chat(
            user_id=message.from_user.id,
            message=message.text
        )

        # Send response
        await message.answer(response, parse_mode="Markdown")

    async def start(self):
        """Start the bot."""
        self.logger.info(f"🚀 Nova-OS v{__version__} starting...")
        self.logger.info("Press Ctrl+C to stop")

        try:
            await self.dp.start_polling(self.bot)
        finally:
            await self.bot.session.close()


# Entry point
async def main():
    agent = NovaOS()
    await agent.start()

if __name__ == "__main__":
    asyncio.run(main())