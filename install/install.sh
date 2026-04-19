#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║                    Nova-OS Auto-Installer                        ║
# ║   curl -sSL https://raw.githubusercontent.com/Dan2470/nova-os/   ║
# ║   main/install/install.sh | bash                                 ║
# ║                                                                  ║
# ║   NON-INTERACTIVE: Set env vars before running:                  ║
# ║     NOVA_BOT_TOKEN=xxx NOVA_OWNER_ID=123 curl ... | bash         ║
# ╚══════════════════════════════════════════════════════════════════╝
set -euo pipefail

# ── Colors ──────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

log()    { echo -e "${BLUE}[Nova-OS]${NC} $1"; }
success(){ echo -e "${GREEN}[✓]${NC} $1"; }
warn()   { echo -e "${YELLOW}[!]${NC} $1"; }
fail()   { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# ── Config ──────────────────────────────────────────────────────────
REPO_URL="https://github.com/Dan2470/nova-os"
INSTALL_DIR="${NOVA_INSTALL_DIR:-$HOME/.nova-os}"
CONFIG_DIR="${NOVA_CONFIG_DIR:-$HOME/.config/nova-os}"
VENV_DIR="$INSTALL_DIR/venv"
NOVA_USER="${SUDO_USER:-$USER}"

# ── Env vars for non-interactive config ─────────────────────────────
# NOVA_BOT_TOKEN  — Telegram bot token from @BotFather
# NOVA_OWNER_ID   — Your Telegram user ID from @userinfobot
# NOVA_AUTO_START — Set to "1" to auto-start service (default: 1)
# NOVA_MODEL      — Ollama model to pull (default: llama3.2:3b)
# NOVA_CLOUD_PROVIDER  — Optional: openai / google / anthropic
# NOVA_CLOUD_API_KEY   — Optional: API key for cloud fallback
# NOVA_INSTALL_DIR     — Custom install directory
# NOVA_CONFIG_DIR      — Custom config directory
# NOVA_SKIP_OLLAMA     — Set to "1" to skip Ollama install

AUTO_START="${NOVA_AUTO_START:-1}"
MODEL="${NOVA_MODEL:-llama3.2:3b}"
SKIP_OLLAMA="${NOVA_SKIP_OLLAMA:-0}"

# ── Detect OS ────────────────────────────────────────────────────────
detect_os() {
    case "$(uname -s)" in
        Linux*)  OS="Linux"; DISTRO=$(grep -oP '(?<=^ID=).+' /etc/os-release 2>/dev/null | tr -d '"' || echo "unknown");;
        Darwin*) OS="Mac";;
        *)       fail "Unsupported OS: $(uname -s)";;
    esac
    log "Detected: $OS${DISTRO:+ ($DISTRO)}"
}

# ── Check / install dependencies ────────────────────────────────────
check_python() {
    if command -v python3 &>/dev/null; then
        PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        if python3 -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)"; then
            success "Python $PY_VER"
        else
            warn "Python $PY_VER found, but 3.11+ required"
            install_python
        fi
    else
        install_python
    fi
}

install_python() {
    log "Installing Python 3.11+..."
    case $OS in
        Linux)
            if [ "$DISTRO" = "ubuntu" ] || [ "$DISTRO" = "debian" ]; then
                sudo apt-get update -qq
                sudo apt-get install -y -qq python3 python3-pip python3-venv
            elif [ "$DISTRO" = "fedora" ]; then
                sudo dnf install -y python3 python3-pip
            elif [ "$DISTRO" = "arch" ] || [ "$DISTRO" = "manjaro" ]; then
                sudo pacman -S --noconfirm python python-pip
            else
                fail "Please install Python 3.11+ manually"
            fi
            ;;
        Mac)
            if command -v brew &>/dev/null; then
                brew install python@3.11
            else
                fail "Install Homebrew first: https://brew.sh"
            fi
            ;;
    esac
    success "Python installed"
}

check_deps() {
    log "Checking dependencies..."
    check_python
    command -v pip3 &>/dev/null && success "pip3" || { warn "pip3 missing"; install_python; }
    command -v git &>/dev/null && success "git" || warn "git not found (optional)"
    command -v curl &>/dev/null && success "curl" || fail "curl is required"
}

# ── Install Ollama ──────────────────────────────────────────────────
install_ollama() {
    [ "$SKIP_OLLAMA" = "1" ] && { warn "Ollama install skipped (NOVA_SKIP_OLLAMA=1)"; return; }

    if command -v ollama &>/dev/null; then
        success "Ollama already installed: $(ollama --version 2>/dev/null || echo 'installed')"
        return
    fi

    log "Installing Ollama..."
    case $OS in
        Linux|Mac)
            curl -fsSL https://ollama.com/install.sh | sh
            ;;
        *)
            warn "Please install Ollama manually from https://ollama.com"
            return
            ;;
    esac
    success "Ollama installed"
}

start_ollama() {
    [ "$SKIP_OLLAMA" = "1" ] && return

    # Check if already running
    if curl -sf http://localhost:11434/api/tags &>/dev/null; then
        success "Ollama is running"
        return
    fi

    log "Starting Ollama..."
    if command -v ollama &>/dev/null; then
        ollama serve &>/dev/null &
        # Wait up to 30s for Ollama to come up
        for i in $(seq 1 30); do
            if curl -sf http://localhost:11434/api/tags &>/dev/null; then
                success "Ollama started"
                return
            fi
            sleep 1
        done
        warn "Ollama didn't respond in 30s — it may need manual start"
    else
        warn "Ollama not found — install it or set NOVA_SKIP_OLLAMA=1"
    fi
}

pull_model() {
    [ "$SKIP_OLLAMA" = "1" ] && return

    log "Pulling model: $MODEL (may take a few minutes)..."
    if command -v ollama &>/dev/null; then
        ollama pull "$MODEL" 2>/dev/null && success "Model '$MODEL' ready" || warn "Model pull failed — run 'ollama pull $MODEL' manually"
    fi
}

# ── Install Nova-OS ─────────────────────────────────────────────────
install_nova_os() {
    log "Installing Nova-OS..."

    # Clone or update
    if [ -d "$INSTALL_DIR/.git" ]; then
        log "Updating existing installation..."
        cd "$INSTALL_DIR"
        # Force reset to match remote (handles history changes)
        git fetch origin main 2>/dev/null || warn "Git fetch failed"
        git reset --hard origin/main 2>/dev/null || warn "Git reset failed — continuing with existing code"
    else
        rm -rf "$INSTALL_DIR"
        mkdir -p "$INSTALL_DIR"
        git clone --depth 1 "$REPO_URL" "$INSTALL_DIR" 2>/dev/null || {
            # Fallback: download tarball
            log "Git clone failed, downloading archive..."
            curl -fsSL "$REPO_URL/archive/refs/heads/main.tar.gz" | tar -xz -C "$INSTALL_DIR" --strip-components=1
        }
    fi

    # Create virtual environment
    log "Creating virtual environment..."
    python3 -m venv "$VENV_DIR" 2>/dev/null || {
        warn "venv creation failed, installing to user site-packages"
        pip3 install --user -r "$INSTALL_DIR/nova_os/requirements.txt" --quiet
        return
    }

    # Install dependencies in venv
    log "Installing Python dependencies (this may take a minute)..."
    "$VENV_DIR/bin/pip" install --upgrade pip --quiet 2>/dev/null
    "$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/nova_os/requirements.txt" --quiet 2>/dev/null || \
        warn "Some dependencies failed — bot may need manual fixes"

    success "Nova-OS installed to $INSTALL_DIR"
}

# ── Generate config (non-interactive) ───────────────────────────────
generate_config() {
    mkdir -p "$CONFIG_DIR"

    BOT_TOKEN="${NOVA_BOT_TOKEN:-}"
    OWNER_ID="${NOVA_OWNER_ID:-0}"

    # If no token provided, generate a placeholder config
    if [ -z "$BOT_TOKEN" ]; then
        warn "No NOVA_BOT_TOKEN provided — generating placeholder config"
        warn "Edit $CONFIG_DIR/config.yaml or set NOVA_BOT_TOKEN and re-run"
    fi

    # Validate token format if provided
    if [ -n "$BOT_TOKEN" ] && [[ ! "$BOT_TOKEN" == *":"* ]]; then
        fail "NOVA_BOT_TOKEN looks invalid — Telegram tokens contain a colon (:)"
    fi

    # Validate owner_id if provided
    if [ -n "$OWNER_ID" ] && [ "$OWNER_ID" != "0" ] && ! [[ "$OWNER_ID" =~ ^[0-9]+$ ]]; then
        fail "NOVA_OWNER_ID must be a number"
    fi

    # Test token if provided
    if [ -n "$BOT_TOKEN" ]; then
        log "Validating bot token..."
        if command -v curl &>/dev/null; then
            TG_RESPONSE=$(curl -sf "https://api.telegram.org/bot${BOT_TOKEN}/getMe" 2>/dev/null || echo '{"ok":false}')
            if echo "$TG_RESPONSE" | grep -q '"ok":true'; then
                BOT_USERNAME=$(echo "$TG_RESPONSE" | grep -oP '"username":"\K[^"]+' || echo "unknown")
                success "Token valid — bot: @$BOT_USERNAME"
            else
                warn "Token validation failed — bot may not work. Check your token."
            fi
        fi
    fi

    # Build cloud fallback section
    CLOUD_SECTION=""
    if [ -n "${NOVA_CLOUD_PROVIDER:-}" ] && [ -n "${NOVA_CLOUD_API_KEY:-}" ]; then
        case "$NOVA_CLOUD_PROVIDER" in
            openai)    CLOUD_MODEL="gpt-4o-mini" ;;
            google)    CLOUD_MODEL="gemini-pro" ;;
            anthropic)  CLOUD_MODEL="claude-3-haiku-20240307" ;;
            *)         CLOUD_MODEL="gpt-4o-mini" ;;
        esac
        CLOUD_SECTION="
  # Cloud fallback (used if Ollama fails)
  cloud_provider: ${NOVA_CLOUD_PROVIDER}
  cloud_model: ${CLOUD_MODEL}
  api_key: \"${NOVA_CLOUD_API_KEY}\"
"
    fi

    cat > "$CONFIG_DIR/config.yaml" << YAML
# Nova-OS Configuration
# Auto-generated by install.sh on $(date -u +"%Y-%m-%d %H:%M UTC")
# Edit manually: nano $CONFIG_DIR/config.yaml

bot:
  token: "${BOT_TOKEN:-YOUR_BOT_TOKEN_HERE}"
  owner_id: ${OWNER_ID}

model:
  provider: ollama
  model: ${MODEL}
  ollama_base_url: http://localhost:11434
${CLOUD_SECTION}
memory:
  enabled: true
  storage: sqlite
  db_path: ${CONFIG_DIR}/memory.db

subagent:
  enabled: true
  max_parallel: 5
  working_dir: ${INSTALL_DIR}/subagents
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
  file: ${CONFIG_DIR}/nova-os.log
YAML

    chmod 600 "$CONFIG_DIR/config.yaml"
    success "Config saved to $CONFIG_DIR/config.yaml"

    # Also create .env file for easy re-configuration
    cat > "$CONFIG_DIR/.env" << ENV
# Nova-OS Environment Variables
# Source this file: source $CONFIG_DIR/.env
NOVA_BOT_TOKEN=${BOT_TOKEN:-}
NOVA_OWNER_ID=${OWNER_ID}
NOVA_MODEL=${MODEL}
ENV
    chmod 600 "$CONFIG_DIR/.env"
}

# ── Create CLI wrapper ──────────────────────────────────────────────
create_wrapper() {
    log "Creating nova-os command..."
    local WRAPPER="$HOME/.local/bin/nova-os"
    mkdir -p "$(dirname "$WRAPPER")"

    cat > "$WRAPPER" << 'WRAPPER'
#!/usr/bin/env bash
# Nova-OS CLI wrapper
set -e
NOVA_DIR="$HOME/.nova-os"
CONFIG_DIR="${NOVA_CONFIG_DIR:-$HOME/.config/nova-os}"

# Source env if available
[ -f "$CONFIG_DIR/.env" ] && source "$CONFIG_DIR/.env"

# Activate venv if available
if [ -f "$NOVA_DIR/venv/bin/activate" ]; then
    source "$NOVA_DIR/venv/bin/activate"
fi

# Run Nova-OS
python3 -m nova_os.main "$@"
WRAPPER

    chmod +x "$WRAPPER"

    # Add to PATH if needed
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
        [ -f "$HOME/.zshrc" ] && echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
        export PATH="$HOME/.local/bin:$PATH"
    fi

    success "Command 'nova-os' available"
}

# ── Systemd service ────────────────────────────────────────────────
create_systemd_service() {
    [ "$OS" != "Linux" ] && { warn "systemd service only available on Linux — use 'nova-os start' manually"; return; }
    [ ! -d /etc/systemd/system ] && { warn "systemd not found — skipping service creation"; return; }

    log "Creating systemd service..."

    local SERVICE_FILE="/etc/systemd/system/nova-os.service"
    local PYTHON_PATH="$VENV_DIR/bin/python3"

    # If no venv, find system python
    [ ! -f "$PYTHON_PATH" ] && PYTHON_PATH="$(which python3)"

    cat > "$SERVICE_FILE" << SERVICE
[Unit]
Description=Nova-OS Personal AI Agent
After=network-online.target ollama.service
Wants=network-online.target

[Service]
Type=simple
User=$NOVA_USER
WorkingDirectory=$INSTALL_DIR
ExecStartPre=/bin/sleep 5
ExecStart=$PYTHON_PATH -m nova_os.main start
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=nova-os

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$CONFIG_DIR $INSTALL_DIR
PrivateTmp=true

# Env vars (override via: systemctl edit nova-os)
Environment=NOVA_CONFIG_DIR=$CONFIG_DIR
EnvironmentFile=-$CONFIG_DIR/.env

[Install]
WantedBy=multi-user.target
SERVICE

    systemctl daemon-reload

    # Enable and start if AUTO_START
    if [ "$AUTO_START" = "1" ] && [ -n "${NOVA_BOT_TOKEN:-}" ]; then
        log "Enabling and starting nova-os service..."
        systemctl enable nova-os.service 2>/dev/null || warn "Could not enable service"
        systemctl start nova-os.service 2>/dev/null || warn "Could not start service — check: journalctl -u nova-os"
        success "Nova-OS service started"
    elif [ "$AUTO_START" = "1" ]; then
        systemctl enable nova-os.service 2>/dev/null || true
        warn "Service enabled but NOT started — set NOVA_BOT_TOKEN and run: systemctl start nova-os"
    else
        warn "Auto-start disabled (NOVA_AUTO_START=0)"
        log "Start manually: systemctl start nova-os"
    fi
}

# ── Fallback: nohup start (non-root / no systemd) ──────────────────
create_nohup_launcher() {
    local LAUNCHER="$INSTALL_DIR/start.sh"

    cat > "$LAUNCHER" << 'LAUNCHER'
#!/usr/bin/env bash
# Nova-OS background launcher (nohup fallback)
set -e
NOVA_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="${NOVA_CONFIG_DIR:-$HOME/.config/nova-os}"
PID_FILE="$CONFIG_DIR/nova-os.pid"
LOG_FILE="$CONFIG_DIR/nova-os.log"

mkdir -p "$CONFIG_DIR"

# Source env
[ -f "$CONFIG_DIR/.env" ] && source "$CONFIG_DIR/.env"

# Activate venv
if [ -f "$NOVA_DIR/venv/bin/activate" ]; then
    source "$NOVA_DIR/venv/bin/activate"
fi

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "Nova-OS already running (PID: $OLD_PID)"
        exit 0
    fi
    rm -f "$PID_FILE"
fi

# Start in background
nohup python3 -m nova_os.main start >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
echo "Nova-OS started (PID: $(cat "$PID_FILE"))"
echo "  Logs: tail -f $LOG_FILE"
echo "  Stop: kill \$(cat $PID_FILE)"
LAUNCHER

    chmod +x "$LAUNCHER"
    success "Background launcher created: $LAUNCHER"
}

# ── Create stop script ──────────────────────────────────────────────
create_stop_script() {
    local STOPPER="$INSTALL_DIR/stop.sh"

    cat > "$STOPPER" << 'STOPPER'
#!/usr/bin/env bash
# Nova-OS stop script
CONFIG_DIR="${NOVA_CONFIG_DIR:-$HOME/.config/nova-os}"
PID_FILE="$CONFIG_DIR/nova-os.pid"

# Try systemd first
if systemctl is-active --quiet nova-os 2>/dev/null; then
    sudo systemctl stop nova-os
    echo "Nova-OS stopped (systemd)"
    exit 0
fi

# Try PID file
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "Nova-OS stopped (PID: $PID)"
        rm -f "$PID_FILE"
        exit 0
    fi
fi

# Try finding the process
PIDS=$(pgrep -f "nova_os.main start" 2>/dev/null || true)
if [ -n "$PIDS" ]; then
    kill $PIDS 2>/dev/null
    echo "Nova-OS stopped (found by process name)"
    exit 0
fi

echo "Nova-OS is not running"
STOPPER

    chmod +x "$STOPPER"
}

# ── Status script ───────────────────────────────────────────────────
create_status_script() {
    local STATUS="$INSTALL_DIR/status.sh"

    cat > "$STATUS" << 'STATUS'
#!/usr/bin/env bash
# Nova-OS status check
CONFIG_DIR="${NOVA_CONFIG_DIR:-$HOME/.config/nova-os}"

echo "═══ Nova-OS Status ═══"

# Check systemd
if systemctl is-active --quiet nova-os 2>/dev/null; then
    echo "  Service:  ✅ running (systemd)"
elif [ -f "$CONFIG_DIR/nova-os.pid" ] && kill -0 "$(cat "$CONFIG_DIR/nova-os.pid")" 2>/dev/null; then
    echo "  Service:  ✅ running (PID: $(cat "$CONFIG_DIR/nova-os.pid"))"
else
    echo "  Service:  ❌ not running"
fi

# Check Ollama
if curl -sf http://localhost:11434/api/tags &>/dev/null; then
    echo "  Ollama:   ✅ running"
else
    echo "  Ollama:   ❌ not running"
fi

# Check config
if [ -f "$CONFIG_DIR/config.yaml" ]; then
    echo "  Config:   ✅ $CONFIG_DIR/config.yaml"
    # Check if token is placeholder
    if grep -q "YOUR_BOT_TOKEN_HERE" "$CONFIG_DIR/config.yaml"; then
        echo "  Token:    ⚠️  placeholder — set NOVA_BOT_TOKEN and re-run"
    else
        echo "  Token:    ✅ configured"
    fi
else
    echo "  Config:   ❌ not found"
fi

# Show recent errors
if [ -f "$CONFIG_DIR/nova-os.log" ]; then
    ERRORS=$(grep -c "ERROR\|Traceback" "$CONFIG_DIR/nova-os.log" 2>/dev/null || echo "0")
    if [ "$ERRORS" -gt 0 ]; then
        echo "  Errors:   ⚠️  $ERRORS in log — check: tail -20 $CONFIG_DIR/nova-os.log"
    fi
fi
STATUS

    chmod +x "$STATUS"
}

# ── Print summary ──────────────────────────────────────────────────
print_summary() {
    echo ""
    echo -e "${CYAN}══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}  ✓ Nova-OS installed!${NC}"
    echo -e "${CYAN}══════════════════════════════════════════════════════════${NC}"
    echo ""

    if [ -n "${NOVA_BOT_TOKEN:-}" ]; then
        echo -e "  ${GREEN}Bot is configured and should be starting...${NC}"
    else
        echo -e "  ${YELLOW}⚠  Bot token not set!${NC}"
        echo ""
        echo "  Set your token and re-run, or edit the config:"
        echo ""
        echo -e "    ${BOLD}Option 1: Environment variables${NC}"
        echo "    export NOVA_BOT_TOKEN='123456:ABCdef...'"
        echo "    export NOVA_OWNER_ID='123456789'"
        echo "    bash $INSTALL_DIR/install/install.sh"
        echo ""
        echo -e "    ${BOLD}Option 2: Edit config directly${NC}"
        echo "    nano $CONFIG_DIR/config.yaml"
        echo ""
        echo -e "    ${BOLD}Option 3: Re-run with env vars inline${NC}"
        echo "    NOVA_BOT_TOKEN='xxx' NOVA_OWNER_ID='123' curl -sSL ... | bash"
        echo ""
    fi

    echo -e "  ${BOLD}Commands:${NC}"
    echo "    nova-os start     Start the bot"
    echo "    nova-os status    Check status"
    echo "    nova-os stop      Stop the bot"
    echo "    nova-os logs      View logs"
    echo "    nova-os config    Edit config"
    echo ""
    echo -e "  ${BOLD}Files:${NC}"
    echo "    Install:   $INSTALL_DIR"
    echo "    Config:    $CONFIG_DIR/config.yaml"
    echo "    Logs:      $CONFIG_DIR/nova-os.log"
    echo ""

    if [ "$OS" = "Linux" ] && [ -d /etc/systemd/system ]; then
        echo -e "  ${BOLD}Systemd:${NC}"
        echo "    systemctl status nova-os"
        echo "    systemctl restart nova-os"
        echo "    journalctl -u nova-os -f"
        echo ""
    fi

    echo -e "  ${BOLD}Quick test:${NC}  message your bot on Telegram! 🚀"
    echo ""
}

# ═══════════════════════════════════════════════════════════════════
#  DETECT PIPE MODE
# ═══════════════════════════════════════════════════════════════════
detect_pipe() {
    # Check if stdin is a terminal (interactive) or pipe
    if [ -t 0 ]; then
        # Terminal attached - interactive mode
        INTERACTIVE=1
    else
        # Pipe detected - non-interactive mode (needs env vars)
        INTERACTIVE=0
    fi
}

# ═══════════════════════════════════════════════════════════════════
#  INTERACTIVE SETUP
# ═══════════════════════════════════════════════════════════════════
interactive_setup() {
    echo ""
    echo -e "${CYAN}══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}  🚀 Nova-OS Interactive Setup${NC}"
    echo -e "${CYAN}══════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Check if running via pipe (stdin not terminal)
    if [ "$INTERACTIVE" = "0" ]; then
        echo -e "${YELLOW}⚠️  Detected pipe mode (curl ... | bash)${NC}"
        echo ""
        echo "Interactive prompts don't work with pipes."
        echo ""
        echo -e "${BOLD}Please run directly:${NC}"
        echo "  bash <(curl -sSL https://.../install/install.sh)"
        echo ""
        echo -e "${BOLD}Or use environment variables:${NC}"
        echo "  NOVA_BOT_TOKEN='xxx' NOVA_OWNER_ID='123' curl ... | bash"
        echo ""
        exit 1
    fi
    
    # Interactive prompts
    echo -e "${CYAN}Step 1/4: Telegram Bot Token${NC}"
    echo "Get from @BotFather:"
    echo "  1. Message @BotFather on Telegram"
    echo "  2. Send /newbot"
    echo "  3. Give it a name"
    echo "  4. Copy the token"
    echo ""
    read -rp "Enter Bot Token: " NOVA_BOT_TOKEN
    
    if [ -z "$NOVA_BOT_TOKEN" ]; then
        fail "Bot token is required"
    fi
    
    echo ""
    echo -e "${CYAN}Step 2/4: Your Telegram User ID${NC}"
    echo "Get from @userinfobot:"
    echo "  1. Message @userinfobot on Telegram"
    echo "  2. It will reply with your ID"
    echo ""
    read -rp "Enter Your User ID: " NOVA_OWNER_ID
    
    if [ -z "$NOVA_OWNER_ID" ]; then
        fail "User ID is required"
    fi
    
    echo ""
    echo -e "${CYAN}Step 3/4: Ollama Model${NC}"
    echo "Available models:"
    echo "  1) llama3.2:3b (default, recommended)"
    echo "  2) gemma3:4b"
    echo "  3) qwen2.5:3b (Bengali optimized)"
    echo "  4) Other (specify)"
    echo ""
    read -rp "Select [1-4] (default: 1): " model_choice
    
    case "${model_choice:-1}" in
        1|"") MODEL="llama3.2:3b" ;;
        2) MODEL="gemma3:4b" ;;
        3) MODEL="qwen2.5:3b" ;;
        4) read -rp "Enter model name: " MODEL ;;
        *) MODEL="llama3.2:3b" ;;
    esac
    
    echo ""
    echo -e "${CYAN}Step 4/4: Auto-start service?${NC}"
    read -rp "Start bot automatically? [Y/n]: " auto_start
    case "${auto_start:-y}" in
        [Yy]*) AUTO_START=1 ;;
        *) AUTO_START=0 ;;
    esac
    
    # Export for the rest of the script
    export NOVA_BOT_TOKEN NOVA_OWNER_ID MODEL AUTO_START
}

# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════
main() {
    # Detect if running interactively or via pipe
    detect_pipe
    
    # If no env vars set and interactive terminal, run interactive setup
    if [ -z "${NOVA_BOT_TOKEN:-}" ] && [ "$INTERACTIVE" = "1" ]; then
        interactive_setup
    fi
    
    echo ""
    echo -e "${CYAN}══════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}  Nova-OS Auto-Installer${NC}"
    echo -e "${CYAN}══════════════════════════════════════════════════════════${NC}"
    echo ""

    detect_os
    check_deps
    install_ollama
    install_nova_os
    start_ollama
    pull_model
    generate_config
    create_wrapper
    create_nohup_launcher
    create_stop_script
    create_status_script
    create_systemd_service
    print_summary
}

main "$@"