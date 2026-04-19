#!/bin/bash
# Nova-OS Quick Start Script for VPS
# Run: curl -sSL https://raw.githubusercontent.com/Dan2470/nova-os/main/quickstart.sh | bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[Nova-OS]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; exit 1; }

echo ""
log "═══════════════════════════════════════════════════"
log "   Nova-OS Quick Setup"
log "═══════════════════════════════════════════════════"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    error "Please run as root (use sudo)"
fi

# Step 1: Clone repository
log "Step 1: Downloading Nova-OS..."
if [ -d "nova-os" ]; then
    warn "nova-os directory exists, updating..."
    cd nova-os
    git pull
else
    git clone https://github.com/Dan2470/nova-os.git
    cd nova-os
fi
success "Nova-OS downloaded"

# Step 2: Install Python dependencies
log "Step 2: Installing Python packages..."
pip3 install -q -r nova_os/requirements.txt
success "Python packages installed"

# Step 3: Check/Install Ollama
log "Step 3: Checking Ollama..."
if command -v ollama &> /dev/null; then
    success "Ollama already installed"
else
    log "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    success "Ollama installed"
fi

# Step 4: Start Ollama
log "Step 4: Starting Ollama service..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    ollama serve &
    sleep 3
fi

# Wait for Ollama
until curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
    sleep 1
done
success "Ollama is running"

# Step 5: Download model
log "Step 5: Downloading llama3.2:3b (this may take a few minutes)..."
ollama pull llama3.2:3b || warn "Model download may have failed, will retry on first run"
success "Model ready"

# Step 7: Run interactive setup (replaces manual config)
log "Step 7: Running interactive setup wizard..."
echo ""
python3 -m nova_os.setup_wizard
echo ""

# Step 8: Create startup script
cat > /usr/local/bin/nova-os << 'EOF'
#!/bin/bash
cd ~/nova-os && python3 -m nova_os.main "$@"
EOF
chmod +x /usr/local/bin/nova-os

# Step 9: Create systemd service
log "Step 9: Creating systemd service..."
cat > /etc/systemd/system/nova-os.service << 'EOF'
[Unit]
Description=Nova-OS AI Agent
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/nova-os
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/usr/bin/python3 -m nova_os.main start
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable nova-os.service
success "Service created and enabled"

# Final message
echo ""
log "═══════════════════════════════════════════════════"
success "Setup complete!"
log "═══════════════════════════════════════════════════"
echo ""
echo "Start Nova-OS now with:"
echo "  sudo systemctl start nova-os"
echo ""
echo "Or run manually:"
echo "  cd ~/nova-os && python3 -m nova_os.main start"
echo ""
echo "Check status:"
echo "  sudo systemctl status nova-os"
echo "  sudo journalctl -u nova-os -f"
echo ""
echo "View logs:"
echo "  tail -f ~/.config/nova-os/nova-os.log"
echo ""
echo "Message your bot on Telegram to start!"
echo ""