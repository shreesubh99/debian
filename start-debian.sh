#!/usr/bin/env bash

echo "=========================================================="
echo "          Starting YTSK WhatsApp Bot & AI Agent           "
echo "=========================================================="

# 1. Resolve directories dynamically
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [ -d "${SCRIPT_DIR}/whatsapp" ] && [ -d "${SCRIPT_DIR}/agent" ]; then
    ROOT_DIR="${SCRIPT_DIR}"
elif [ -d "${SCRIPT_DIR}/whatsapp-bot-server/whatsapp" ] && [ -d "${SCRIPT_DIR}/whatsapp-bot-server/agent" ]; then
    ROOT_DIR="${SCRIPT_DIR}/whatsapp-bot-server"
else
    echo "Error: Could not find whatsapp or agent directories!"
    exit 1
fi

# 2. Identify the normal user (non-root) to run the servers safely
RUN_USER="${SUDO_USER:-beck}"
echo "[System] Using user account: ${RUN_USER}"

# 3. Secure and correct directory permissions automatically
echo "[System] Aligning file permissions..."
chown -R "${RUN_USER}:${RUN_USER}" "${ROOT_DIR}"
chmod -R 755 "${ROOT_DIR}"
if [ -d "${ROOT_DIR}/whatsapp/session" ]; then
    chmod -R 777 "${ROOT_DIR}/whatsapp/session" 2>/dev/null || true
fi

# 4. Start the servers concurrently dropping root privileges
echo "[System] Booting Bot and Agent servers as user '${RUN_USER}'..."
cd "${ROOT_DIR}"

# Execute npm start as the non-root user to avoid Puppeteer profile blocks
sudo -u "${RUN_USER}" npm start
