#!/usr/bin/env python3
"""
Nova-OS: Personal AI Agent for Telegram
Main entry point.

Usage:
    nova-os start          # Start the bot (foreground)
    nova-os daemon         # Start as daemon (background, PID file)
    nova-os status         # Check if running
    nova-os stop           # Stop the bot
    nova-os config         # Edit configuration
    nova-os logs           # View logs
    nova-os setup          # Interactive setup wizard

Environment Variables (override config.yaml):
    NOVA_BOT_TOKEN         Telegram bot token
    NOVA_OWNER_ID          Telegram owner user ID
    NOVA_MODEL             Ollama model name
    NOVA_CONFIG_DIR        Config directory path
"""

import asyncio
import os
import signal
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

console = Console()

# Import after ensuring we're in venv
try:
    from .bot import NovaOS, main as bot_main
    from .__init__ import __version__
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from bot import NovaOS, main as bot_main
    from __init__ import __version__


def get_config_dir() -> Path:
    """Get config directory from env or default."""
    env_dir = os.environ.get("NOVA_CONFIG_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.home() / ".config" / "nova-os"


def get_pid_file() -> Path:
    """Get PID file path."""
    return get_config_dir() / "nova-os.pid"


def get_log_file() -> Path:
    """Get log file path."""
    return get_config_dir() / "nova-os.log"


def check_ollama():
    """Check if Ollama is running."""
    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:11434/api/tags"],
            capture_output=True,
            timeout=3
        )
        return result.returncode == 0
    except Exception:
        return False


def ensure_ollama():
    """Start Ollama if not running."""
    if not check_ollama():
        console.print("[yellow]⚠️  Ollama is not running. Starting it now...[/yellow]")
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            # Wait for it
            import time
            for _ in range(30):
                time.sleep(1)
                if check_ollama():
                    console.print("[green]✓ Ollama started[/green]")
                    return True
            console.print("[red]✗ Ollama didn't start in 30s[/red]")
            return False
        except Exception as e:
            console.print(f"[red]✗ Failed to start Ollama: {e}[/red]")
            return False
    else:
        console.print("[green]✓ Ollama is running[/green]")
        return True


def ensure_config():
    """Ensure config exists; auto-generate if missing (non-interactive)."""
    config_path = get_config_dir() / "config.yaml"

    if config_path.exists():
        # Check if it's still a placeholder
        content = config_path.read_text()
        if "YOUR_BOT_TOKEN_HERE" in content:
            # Check env vars
            token = os.environ.get("NOVA_BOT_TOKEN", "")
            owner_id = os.environ.get("NOVA_OWNER_ID", "")
            if token:
                console.print("[yellow]⚠️  Config has placeholder token, updating from env vars...[/yellow]")
                _generate_config(token, owner_id)
            else:
                console.print(Panel(
                    "⚠️  Bot token not configured!\n\n"
                    "Set it via:\n"
                    "  export NOVA_BOT_TOKEN='your-token'\n"
                    "  export NOVA_OWNER_ID='your-id'\n"
                    "  nova-os start\n\n"
                    f"Or edit: {config_path}",
                    title="Configuration Required",
                    border_style="yellow"
                ))
                sys.exit(1)
        return True

    # No config exists — check env vars
    token = os.environ.get("NOVA_BOT_TOKEN", "")
    owner_id = os.environ.get("NOVA_OWNER_ID", "0")

    if token:
        console.print("[cyan]Auto-generating config from environment variables...[/cyan]")
        _generate_config(token, owner_id)
        return True

    # No token at all — offer interactive setup
    console.print(Panel(
        "🚀 Welcome to Nova-OS!\n\n"
        "No configuration found. You can:\n\n"
        "[bold]Option 1:[/bold] Set environment variables\n"
        "  export NOVA_BOT_TOKEN='123456:ABCdef...'\n"
        "  export NOVA_OWNER_ID='123456789'\n"
        "  nova-os start\n\n"
        "[bold]Option 2:[/bold] Run interactive setup\n"
        "  nova-os setup\n\n"
        "[bold]Option 3:[/bold] Re-run installer with env vars\n"
        "  NOVA_BOT_TOKEN='xxx' NOVA_OWNER_ID='123' curl -sSL ... | bash",
        title="First Run",
        border_style="green"
    ))
    sys.exit(1)


def _generate_config(token: str, owner_id: str):
    """Generate config.yaml from values (non-interactive)."""
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    model = os.environ.get("NOVA_MODEL", "llama3.2:3b")

    yaml_content = f"""# Nova-OS Configuration
# Auto-generated by nova-os

bot:
  token: "{token}"
  owner_id: {owner_id or 0}

model:
  provider: ollama
  model: {model}
  ollama_base_url: http://localhost:11434

memory:
  enabled: true
  storage: sqlite
  db_path: {config_dir}/memory.db

subagent:
  enabled: true
  max_parallel: 5
  working_dir: {Path.home() / ".nova-os" / "subagents"}
  clawhub:
    enabled: true
    url: https://clawhub.ai

features:
  system_commands: true
  web_search: true
  file_operations: true
  docker_management: false
  cloud_integration: false

logging:
  level: INFO
  file: {config_dir}/nova-os.log
"""

    config_path.write_text(yaml_content)
    os.chmod(config_path, 0o600)
    console.print(f"[green]✓ Config saved to {config_path}[/green]")


def start():
    """Start Nova-OS in foreground."""
    ensure_config()
    ensure_ollama()

    console.print(Panel(
        f"🚀 Starting Nova-OS v{__version__}\n"
        "Your personal AI agent for Telegram\n"
        "Press Ctrl+C to stop",
        title="Nova-OS",
        border_style="green"
    ))

    try:
        asyncio.run(bot_main())
    except KeyboardInterrupt:
        console.print("\n[green]✓ Nova-OS stopped. Goodbye![/green]")


def daemon():
    """Start Nova-OS as a background daemon."""
    ensure_config()
    ensure_ollama()

    pid_file = get_pid_file()
    log_file = get_log_file()

    # Check if already running
    if pid_file.exists():
        try:
            old_pid = int(pid_file.read_text().strip())
            os.kill(old_pid, 0)  # Check if process exists
            console.print(f"[yellow]Nova-OS already running (PID: {old_pid})[/yellow]")
            sys.exit(0)
        except (ProcessLookupError, ValueError):
            pid_file.unlink(missing_ok=True)

    console.print(Panel(
        f"🚀 Starting Nova-OS v{__version__} as daemon",
        title="Nova-OS",
        border_style="green"
    ))

    # Fork to background
    try:
        pid = os.fork()
        if pid > 0:
            # Parent — write PID and exit
            pid_file.write_text(str(pid))
            console.print(f"[green]✓ Nova-OS started (PID: {pid})[/green]")
            console.print(f"  Logs: tail -f {log_file}")
            console.print(f"  Stop: nova-os stop")
            sys.exit(0)
    except OSError as e:
        console.print(f"[red]✗ Fork failed: {e}[/red]")
        sys.exit(1)

    # Child — redirect stdio, start bot
    os.setsid()
    sys.stdin.close()
    log_file.parent.mkdir(parents=True, exist_ok=True)
    sys.stdout = open(log_file, "a")
    sys.stderr = open(log_file, "a")

    # Write actual PID (forked child)
    pid_file.write_text(str(os.getpid()))

    try:
        asyncio.run(bot_main())
    except Exception as e:
        print(f"Nova-OS crashed: {e}", file=sys.stderr)
    finally:
        pid_file.unlink(missing_ok=True)


def stop():
    """Stop Nova-OS daemon."""
    pid_file = get_pid_file()

    # Try systemd first
    if sys.platform == "linux":
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", "nova-os"],
            capture_output=True
        )
        if result.returncode == 0:
            subprocess.run(["sudo", "systemctl", "stop", "nova-os"])
            console.print("[green]✓ Nova-OS stopped (systemd)[/green]")
            return

    if not pid_file.exists():
        # Try finding by process name
        result = subprocess.run(
            ["pgrep", "-f", "nova_os.main"],
            capture_output=True
        )
        if result.stdout.strip():
            pids = result.stdout.decode().strip().split("\n")
            for p in pids:
                try:
                    os.kill(int(p), signal.SIGTERM)
                except ProcessLookupError:
                    pass
            console.print("[green]✓ Nova-OS stopped[/green]")
            return

        console.print("[yellow]Nova-OS is not running[/yellow]")
        return

    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        console.print(f"[green]✓ Nova-OS stopped (PID: {pid})[/green]")
        pid_file.unlink(missing_ok=True)
    except ProcessLookupError:
        console.print("[yellow]Process not found — may have already stopped[/yellow]")
        pid_file.unlink(missing_ok=True)
    except ValueError:
        console.print("[red]Invalid PID file[/red]")
        pid_file.unlink(missing_ok=True)


def status():
    """Check Nova-OS status."""
    console.print(Panel("Nova-OS Status", border_style="blue"))

    # Check if running
    pid_file = get_pid_file()
    running = False

    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            running = True
            console.print(f"[green]✓[/green] Running (PID: {pid})")
        except (ProcessLookupError, ValueError):
            console.print("[red]✗[/red] Not running (stale PID file)")

    # Check systemd
    if sys.platform == "linux":
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", "nova-os"],
            capture_output=True
        )
        if result.returncode == 0:
            console.print("[green]✓[/green] systemd service active")
            running = True

    if not running:
        console.print("[red]✗[/red] Not running")

    # Ollama
    ollama_ok = check_ollama()
    console.print(f"{'[green]✓[/green]' if ollama_ok else '[red]✗[/red]'} Ollama {'running' if ollama_ok else 'not running'}")

    # Config
    config_path = get_config_dir() / "config.yaml"
    config_ok = config_path.exists()
    console.print(f"{'[green]✓[/green]' if config_ok else '[red]✗[/red]'} Config {'found' if config_ok else 'not found'}")

    if config_ok:
        content = config_path.read_text()
        if "YOUR_BOT_TOKEN_HERE" in content:
            console.print("[yellow]⚠[/yellow] Token not configured (placeholder)")

    if not config_ok:
        console.print("[yellow]Run the installer first:[/yellow]")
        console.print("  curl -sSL https://raw.githubusercontent.com/Dan2470/nova-os/main/install/install.sh | bash")


def config():
    """Open config in editor."""
    config_path = get_config_dir() / "config.yaml"

    if not config_path.exists():
        console.print(f"[yellow]Config not found at {config_path}[/yellow]")
        console.print("Run 'nova-os setup' or set NOVA_BOT_TOKEN env var first.")
        return

    editors = ["nano", "vim", "vi"]
    for editor in editors:
        if subprocess.run(["which", editor], capture_output=True).returncode == 0:
            subprocess.run([editor, str(config_path)])
            return

    console.print(f"Config location: {config_path}")


def logs():
    """Show recent logs."""
    log_path = get_log_file()

    if log_path.exists():
        subprocess.run(["tail", "-50", str(log_path)])
    else:
        console.print("[yellow]No log file found[/yellow]")


def setup_wizard():
    """Run interactive setup wizard."""
    try:
        from .setup_wizard import main as wizard_main
    except ImportError:
        sys.path.insert(0, str(Path(__file__).parent))
        from setup_wizard import main as wizard_main

    try:
        asyncio.run(wizard_main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Setup cancelled.[/yellow]")


def help_text():
    """Show help."""
    console.print(Panel(f"""
Nova-OS v{__version__} - Personal AI Agent

Commands:
  start    Start the bot (foreground)
  daemon   Start as background daemon
  stop     Stop the daemon
  status   Check if running
  config   Edit configuration
  logs     View recent logs
  setup    Interactive setup wizard
  help     Show this help

Environment Variables:
  NOVA_BOT_TOKEN    Telegram bot token (from @BotFather)
  NOVA_OWNER_ID     Your Telegram user ID
  NOVA_MODEL        Ollama model (default: llama3.2:3b)
  NOVA_CONFIG_DIR   Config directory (default: ~/.config/nova-os)

Quick Start:
  export NOVA_BOT_TOKEN='123456:ABCdef...'
  export NOVA_OWNER_ID='123456789'
  nova-os start

  Or one-line install:
  NOVA_BOT_TOKEN='xxx' NOVA_OWNER_ID='123' \\
    curl -sSL https://raw.githubusercontent.com/Dan2470/nova-os/main/install/install.sh | bash
    """, title="Help", border_style="blue"))


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        help_text()
        sys.exit(0)

    command = sys.argv[1].lower()

    commands = {
        'start': start,
        'daemon': daemon,
        'status': status,
        'stop': stop,
        'config': config,
        'logs': logs,
        'help': help_text,
        '-h': help_text,
        '--help': help_text,
        'setup': setup_wizard,
    }

    if command in commands:
        commands[command]()
    else:
        console.print(f"[red]Unknown command: {command}[/red]")
        help_text()
        sys.exit(1)


if __name__ == "__main__":
    main()