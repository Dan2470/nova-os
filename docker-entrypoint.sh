#!/bin/bash
# Docker entrypoint for Nova-OS

set -e

# Start Ollama in background
echo "🚀 Starting Ollama..."
ollama serve &
OLLAMA_PID=$!

# Wait for Ollama to be ready
echo "⏳ Waiting for Ollama..."
until curl -s http://localhost:11434/api/tags >/dev/null 2>&1; do
    sleep 1
done
echo "✓ Ollama is ready"

# Pull model if not exists
echo "📦 Checking model..."
ollama pull llama3.2:3b || true

# Handle config from environment
if [ -n "$BOT_TOKEN" ]; then
    echo "📝 Creating config from environment..."
    mkdir -p /root/.config/nova-os
    cat > /root/.config/nova-os/config.yaml << EOF
bot:
  token: "$BOT_TOKEN"
  owner_id: ${OWNER_ID:-0}

model:
  provider: ollama
  model: llama3.2:3b
  ollama_base_url: http://localhost:11434

memory:
  enabled: true
  storage: sqlite
  db_path: /root/.config/nova-os/memory.db

features:
  system_commands: true
  web_search: true
  file_operations: true

logging:
  level: INFO
  file: /root/.config/nova-os/nova-os.log
EOF
fi

# Execute command
case "$1" in
    start)
        echo "🚀 Starting Nova-OS..."
        exec python3 -m nova_os.main start
        ;;
    status)
        exec python3 -m nova_os.main status
        ;;
    config)
        cat /root/.config/nova-os/config.yaml
        ;;
    logs)
        tail -f /root/.config/nova-os/nova-os.log
        ;;
    shell|bash|sh)
        exec /bin/bash
        ;;
    *)
        exec "$@"
        ;;
esac