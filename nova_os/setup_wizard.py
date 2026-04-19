"""
Interactive Setup Wizard for Nova-OS
First-run configuration assistant
"""
import asyncio
import os
import re
import sys
from pathlib import Path

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.spinner import Spinner
from rich.progress import Progress

console = Console()


class SetupWizard:
    """Interactive first-run setup wizard."""
    
    def __init__(self):
        self.config = {}
        self.config_path = Path.home() / ".config" / "nova-os" / "config.yaml"
        
    async def run(self):
        """Run the setup wizard."""
        console.print(Panel.fit(
            "🚀 Welcome to Nova-OS Setup Wizard!\n"
            "Your Personal AI Agent for Telegram",
            title="Nova-OS v0.1.0",
            border_style="green"
        ))
        
        console.print("\n[cyan]This wizard will help you configure Nova-OS step by step.[/cyan]\n")
        
        # Check if config already exists
        if self.config_path.exists():
            overwrite = Confirm.ask(
                "Config already exists. Overwrite?",
                default=False
            )
            if not overwrite:
                console.print("[yellow]Setup cancelled. Using existing config.[/yellow]")
                return
        
        # Step 1: Telegram Bot Token
        if not await self._step_telegram_bot():
            return
        
        # Step 2: Owner ID
        if not await self._step_owner_id():
            return
        
        # Step 3: Ollama Check
        await self._step_ollama()
        
        # Step 4: Optional Features
        await self._step_features()
        
        # Step 5: Optional API Keys
        await self._step_api_keys()
        
        # Save config
        await self._save_config()
        
        # Show summary
        await self._show_summary()
    
    async def _step_telegram_bot(self) -> bool:
        """Step 1: Get Telegram Bot Token."""
        console.print("\n[bold blue]Step 1/5: Telegram Bot Configuration[/bold blue]")
        console.print("""
To create a bot:
1. Message @BotFather on Telegram
2. Send /newbot
3. Give it a name
4. Copy the token (looks like: 123456789:ABCdefGHIjklMNOpqrSTUvwxyz)
        """)
        
        while True:
            token = Prompt.ask("Enter your Bot Token").strip()
            
            if not token:
                console.print("[red]Token is required.[/red]")
                continue
            
            # Basic validation
            if ":" not in token:
                console.print("[red]Invalid format. Token should contain a colon (:)[/red]")
                continue
            
            # Test the token
            console.print("[yellow]Testing token...[/yellow]")
            
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"https://api.telegram.org/bot{token}/getMe",
                        timeout=10
                    )
                    data = response.json()
                    
                    if data.get("ok"):
                        bot_name = data["result"]["username"]
                        console.print(f"[green]✓ Token valid! Bot: @{bot_name}[/green]")
                        self.config["bot_token"] = token
                        return True
                    else:
                        console.print(f"[red]✗ Invalid token: {data.get('description')}[/red]")
                        
            except Exception as e:
                console.print(f"[red]✗ Failed to test token: {e}[/red]")
                if Confirm.ask("Skip validation and continue anyway?", default=False):
                    self.config["bot_token"] = token
                    return True
        
        return False
    
    async def _step_owner_id(self) -> bool:
        """Step 2: Get Owner ID."""
        console.print("\n[bold blue]Step 2/5: Owner Configuration[/bold blue]")
        console.print("""
To find your User ID:
1. Message @userinfobot on Telegram
2. It will reply with your ID number
3. Copy that number
        """)
        
        while True:
            owner_id = IntPrompt.ask("Enter your Telegram User ID").strip()
            
            if not owner_id or owner_id <= 0:
                console.print("[red]Please enter a valid user ID (positive number)[/red]")
                continue
            
            # Verify by sending a message
            console.print("[yellow]Sending test message...[/yellow]")
            
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"https://api.telegram.org/bot{self.config['bot_token']}/sendMessage",
                        json={
                            "chat_id": owner_id,
                            "text": "🚀 Nova-OS is being configured!"
                        },
                        timeout=10
                    )
                    data = response.json()
                    
                    if data.get("ok"):
                        console.print("[green]✓ Test message sent! Check your Telegram.[/green]")
                        self.config["owner_id"] = owner_id
                        return True
                    else:
                        error = data.get('description', 'Unknown error')
                        if "chat not found" in error.lower():
                            console.print("[red]✗ Please message your bot first, then try again[/red]")
                        else:
                            console.print(f"[red]✗ Error: {error}[/red]")
                        
            except Exception as e:
                console.print(f"[red]✗ Failed to send test: {e}[/red]")
            
            if Confirm.ask("Continue with this ID anyway?", default=False):
                self.config["owner_id"] = owner_id
                return True
        
        return False
    
    async def _step_ollama(self):
        """Step 3: Check/Setup Ollama."""
        console.print("\n[bold blue]Step 3/5: Ollama Configuration[/bold blue]")
        
        # Check if Ollama is running
        console.print("[yellow]Checking Ollama...[/yellow]")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "http://localhost:11434/api/tags",
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])
                    
                    if models:
                        console.print(f"[green]✓ Ollama is running with {len(models)} model(s)[/green]")
                        for model in models:
                            console.print(f"  • {model.get('name')}")
                    else:
                        console.print("[yellow]⚠ Ollama running but no models installed[/yellow]")
                    
                    self.config["ollama_running"] = True
                    return
                    
        except Exception:
            pass
        
        # Ollama not running
        console.print("[yellow]⚠ Ollama is not running[/yellow]")
        
        if Confirm.ask("Do you want to start Ollama now?", default=True):
            console.print("[yellow]Starting Ollama...[/yellow]")
            
            # Start Ollama in background
            import subprocess
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            
            # Wait for it
            with console.status("[bold green]Waiting for Ollama to start...") as status:
                for i in range(30):
                    await asyncio.sleep(1)
                    try:
                        async with httpx.AsyncClient() as client:
                            response = await client.get(
                                "http://localhost:11434/api/tags",
                                timeout=5
                            )
                            if response.status_code == 200:
                                console.print("[green]✓ Ollama started successfully![/green]")
                                self.config["ollama_running"] = True
                                return
                    except:
                        pass
            
            console.print("[red]✗ Ollama failed to start. Please start manually: ollama serve[/red]")
        
        self.config["ollama_running"] = False
    
    async def _step_features(self):
        """Step 4: Configure optional features."""
        console.print("\n[bold blue]Step 4/5: Feature Configuration[/bold blue]")
        
        self.config["system_commands"] = Confirm.ask(
            "Enable system command execution (/exec)?",
            default=True
        )
        
        self.config["web_search"] = Confirm.ask(
            "Enable web search functionality?",
            default=True
        )
        
        self.config["file_operations"] = Confirm.ask(
            "Enable file operations?",
            default=True
        )
        
        self.config["subagent_enabled"] = Confirm.ask(
            "Enable sub-agent system (parallel tasks)?",
            default=True
        )
        
        self.config["clawhub_enabled"] = Confirm.ask(
            "Enable ClawHub skill installation?",
            default=True
        )
        
        # Max parallel tasks
        if self.config["subagent_enabled"]:
            self.config["max_parallel"] = IntPrompt.ask(
                "Max parallel sub-agents",
                default=5
            )
    
    async def _step_api_keys(self):
        """Step 5: Optional API keys."""
        console.print("\n[bold blue]Step 5/5: Optional API Keys[/bold blue]")
        console.print("[dim]These are optional. You can add them later in the config file.[/dim]\n")
        
        # Tavily for search
        if Confirm.ask("Add Tavily API key for web search?", default=False):
            self.config["tavily_api_key"] = Prompt.ask(
                "Tavily API Key (get from https://tavily.com)",
                password=True
            )
        
        # Cloud fallback
        if Confirm.ask("Add OpenAI API key for fallback?", default=False):
            self.config["openai_api_key"] = Prompt.ask(
                "OpenAI API Key",
                password=True
            )
    
    async def _save_config(self):
        """Save the configuration."""
        console.print("\n[bold green]Saving configuration...[/bold green]")
        
        # Create directory
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Build YAML content
        yaml_content = f"""# Nova-OS Configuration
# Generated by setup wizard on {asyncio.get_event_loop().time()}

bot:
  token: "{self.config['bot_token']}"
  owner_id: {self.config['owner_id']}

model:
  provider: ollama
  model: llama3.2:3b
  ollama_base_url: http://localhost:11434
"""
        
        # Add cloud fallback if provided
        if self.config.get("openai_api_key"):
            yaml_content += f"""
  # Cloud fallback (used if Ollama fails)
  cloud_provider: openai
  cloud_model: gpt-3.5-turbo
  api_key: "{self.config['openai_api_key']}"
"""
        
        yaml_content += f"""
memory:
  enabled: true
  storage: sqlite
  db_path: ~/.config/nova-os/memory.db

subagent:
  enabled: {str(self.config.get('subagent_enabled', True)).lower()}
  max_parallel: {self.config.get('max_parallel', 5)}
  working_dir: ~/.nova-os/subagents
  clawhub:
    enabled: {str(self.config.get('clawhub_enabled', True)).lower()}
    url: https://clawhub.ai
"""
        
        # Add Tavily if provided
        if self.config.get("tavily_api_key"):
            yaml_content += f"""
# External APIs
tavily:
  api_key: "{self.config['tavily_api_key']}"
"""
        
        yaml_content += f"""
features:
  system_commands: {str(self.config.get('system_commands', True)).lower()}
  web_search: {str(self.config.get('web_search', True)).lower()}
  file_operations: {str(self.config.get('file_operations', True)).lower()}

logging:
  level: INFO
  file: ~/.config/nova-os/nova-os.log
"""
        
        # Write file
        self.config_path.write_text(yaml_content)
        
        # Secure permissions
        os.chmod(self.config_path, 0o600)
        
        console.print(f"[green]✓ Config saved to: {self.config_path}[/green]")
    
    async def _show_summary(self):
        """Show setup summary."""
        console.print("\n" + "="*50)
        console.print(Panel.fit(
            "[bold green]✓ Setup Complete![/bold green]\n\n"
            "[cyan]Your Nova-OS is ready to run![/cyan]\n\n"
            f"Config: [dim]{self.config_path}[/dim]\n\n"
            "[bold]Next Steps:[/bold]\n"
            "1. Start Nova-OS:\n"
            "   [green]python3 -m nova_os.main start[/green]\n\n"
            "2. Or use systemd:\n"
            "   [green]sudo systemctl start nova-os[/green]\n\n"
            "3. Message your bot on Telegram!\n\n"
            "[dim]View logs: tail -f ~/.config/nova-os/nova-os.log[/dim]",
            border_style="green"
        ))


async def main():
    """Entry point for setup wizard."""
    wizard = SetupWizard()
    await wizard.run()


if __name__ == "__main__":
    asyncio.run(main())