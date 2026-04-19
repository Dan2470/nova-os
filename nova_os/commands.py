"""
Command Handler: System commands, status, utilities.
"""
import asyncio
import logging
import os
import subprocess
from datetime import datetime

from aiogram.types import Message

logger = logging.getLogger("Nova-OS")

class CommandHandler:
    """Handles bot commands."""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        
    async def help(self, message: Message):
        """Show help message."""
        help_text = """🤖 **Nova-OS Commands**

**Chat**
Just message me normally - I remember context!

**System**
`/status` - System health (CPU, RAM, disk)
`/exec <command>` - Run shell command
`/exec python script.py` - Run Python scripts
`/exec cat file.txt` - View file contents

**Memory**
`/memory` - Conversation stats
`/tasks` - Sub-agent task status
`/agents` - Sub-agent commands
`/skill <name>` - Install ClawHub skill
`/clear` - Clear conversation

**Social Media**
`/social auth <platform>` - Connect social account
`/social post <platform> <text>` - Post content
`/social schedule <platform> <time>` - Schedule post
`/social analytics <platform>` - View stats
`/social list` - Connected accounts

**AI**
`/code <description>` - Generate code
`/image <prompt>` - Generate image (coming soon)

**Config**
Your config is at: `~/.config/nova-os/config.yaml`

Need help? Just ask!"""
        await message.answer(help_text, parse_mode="Markdown")
    
    async def status(self, message: Message):
        """Show system status."""
        try:
            # CPU and load
            cpu_info = subprocess.run(
                ["top", "-bn1"], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            cpu_line = next((l for l in cpu_info.stdout.split('\n') if 'load average' in l), "N/A")
            
            # Memory
            mem = subprocess.run(
                ["free", "-h"], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            mem_lines = mem.stdout.strip().split('\n')
            
            # Disk
            disk = subprocess.run(
                ["df", "-h", "/"], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            disk_line = disk.stdout.strip().split('\n')[1] if disk.stdout else "N/A"
            
            status_text = f"""📊 **System Status**

**⏰ Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**🖥️ CPU:**
`{cpu_line}`

**💾 Memory:**
```
{chr(10).join(mem_lines[:3])}
```

**💿 Disk:**
```
{disk_line}
```
"""
            await message.answer(status_text, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Status command failed: {e}")
            await message.answer(f"❌ Error getting status: {e}")
    
    async def execute(self, message: Message):
        """Execute shell command."""
        command = message.text.replace("/exec", "").strip()
        
        if not command:
            await message.answer(
                "Usage: `/exec <command>`\n"
                "Examples:\n"
                "• `/exec ls -la`\n"
                "• `/exec python --version`\n"
                "• `/exec cat ~/.bashrc | head -20`",
                parse_mode="Markdown"
            )
            return
        
        # Security checks
        forbidden = ["rm -rf /", "mkfs", "dd if=/dev/zero", ":(){ :|:& }:", ">/dev/sda"]
        if any(f in command.lower() for f in forbidden):
            await message.answer("❌ **Security Alert:** Forbidden command detected!")
            return
        
        # Show typing
        await self.bot.bot.send_chat_action(message.chat.id, "typing")
        
        try:
            # Execute with timeout
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=os.getcwd()
            )
            
            output = result.stdout if result.returncode == 0 else result.stderr
            if not output:
                output = "✅ Command executed successfully (no output)"
            
            # Truncate if too long (Telegram limit ~4096)
            if len(output) > 3500:
                output = output[:3500] + "\n\n... (truncated)"
            
            # Escape markdown special characters in output
            output = output.replace("`", "\`").replace("*", "\*").replace("_", "\_")
            
            await message.answer(
                f"💻 **Command:** `{' '.join(command.split()[:5])}`\n"
                f"**Exit code:** {result.returncode}\n\n"
                f"```\n{output}\n```",
                parse_mode="Markdown"
            )
            
        except subprocess.TimeoutExpired:
            await message.answer("⏱️ Command timed out (30s limit)")
        except Exception as e:
            logger.error(f"Exec failed: {e}")
            await message.answer(f"❌ Error: {e}")
    
    async def generate_code(self, message: Message):
        """Generate code via AI."""
        prompt = message.text.replace("/code", "").strip()
        if not prompt:
            await message.answer("Usage: `/code <what to build>`")
            return
        
        await self.bot.bot.send_chat_action(message.chat.id, "typing")
        
        code = await self.bot.ai.generate_code(prompt)
        
        await message.answer(
            f"📝 **Generated Code**\n\n"
            f"```python\n{code}\n```",
            parse_mode="Markdown"
        )

    async def agents(self, message: Message):
        """Manage sub-agents."""
        help_text = """🤖 **Sub-Agent Commands**

**Spawn Agents:**
`/agents code <description>` - Generate code
`/agents research <query>` - Web research
`/agents file <operation>` - File operations
`/agents shell <command>` - Execute command
`/agents skill <skill_name>` - Install ClawHub skill

**Examples:**
`/agents code "Create a Python function to reverse string"`
`/agents research "Latest AI news"`
`/agents file copy /home/file.txt /backup/`
`/agents shell "ls -la /var/log"`
`/agents skill web-development`

**Check Tasks:**
`/tasks` - View all task status

For custom agents, just describe what you need!"""
        await message.answer(help_text, parse_mode="Markdown")

    async def install_skill(self, message: Message):
        """Install a ClawHub skill."""
        skill_name = message.text.replace("/skill", "").strip()
        if not skill_name:
            await message.answer(
                "Usage: `/skill <skill_name>`\n"
                "Example: `/skill web-development`",
                parse_mode="Markdown"
            )
            return
        await message.answer(f"📦 Installing skill: {skill_name}...")
        task_id = await self.bot.subagent.spawn(
            f"Install skill: {skill_name}",
            "skill",
            {"skill_name": skill_name}
        )
        await message.answer(f"✅ Skill installation started! Task ID: `{task_id}`", parse_mode="Markdown")

    async def social(self, message: Message):
        """Handle social media commands."""
        args = message.text.split(maxsplit=2)
        
        if len(args) == 1:
            # Show social help
            help_text = """📱 **Social Media Commands**

**Connect Account:**
`/social auth <platform>` - Start OAuth flow
Platforms: twitter, linkedin, instagram, facebook, youtube, reddit

**Post Content:**
`/social post <platform> <text>` - Post to platform
`/social post twitter "Hello World!"`

**Check Status:**
`/social list` - Show connected accounts
`/social analytics <platform>` - View stats

**Examples:**
`/social auth twitter`
`/social post linkedin "Excited to share my new project!"`
`/social analytics twitter`

**Setup Instructions:**
Each platform requires OAuth app creation.
Run `/social auth <platform>` for setup guide."""
            await message.answer(help_text, parse_mode="Markdown")
            return
        
        subcommand = args[1].lower()
        
        if subcommand == "auth":
            if len(args) < 3:
                await message.answer("Usage: `/social auth <platform>`")
                return
            
            platform = args[2].lower()
            instructions = self.bot.social_auth.get_auth_instructions(platform)
            
            await message.answer(
                f"🔗 **{platform.title()} Authentication**\n\n"
                f"{instructions}\n\n"
                f"After creating app, run:\n"
                f"`/social auth {platform} <client_id> <client_secret>`",
                parse_mode="Markdown"
            )
        
        elif subcommand == "list":
            connected = self.bot.social_auth.list_authenticated()
            if connected:
                platforms = "\n".join([f"✅ {p.title()}" for p in connected])
                await message.answer(f"**Connected Accounts:**\n\n{platforms}")
            else:
                await message.answer("❌ No social accounts connected.\nUse `/social auth <platform>` to connect.")
        
        elif subcommand == "post":
            if len(args) < 3:
                await message.answer("Usage: `/social post <platform> <text>`")
                return
            
            # Parse: /social post twitter Hello World
            post_args = args[2].split(maxsplit=1)
            if len(post_args) < 2:
                await message.answer("Usage: `/social post <platform> <text>`")
                return
            
            platform, text = post_args
            
            await message.answer(f"📤 Posting to {platform}...")
            
            # Post based on platform
            if platform.lower() == "twitter":
                result = await self.bot.social.twitter_post(text)
            elif platform.lower() == "linkedin":
                result = await self.bot.social.linkedin_post(text)
            elif platform.lower() == "facebook":
                result = await self.bot.social.facebook_post("me", text)
            else:
                result = {"error": f"Posting not yet implemented for {platform}"}
            
            from .social_actions import format_post_result
            await message.answer(format_post_result(result), parse_mode="Markdown")
        
        else:
            await message.answer(f"Unknown subcommand: {subcommand}. Use `/social` for help.")
