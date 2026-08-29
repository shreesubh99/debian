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

# 1b. Force clean all ports and stale processes as root before launching
echo "[System] Performing strict port and process cleanup before boot..."
fuser -k 8000/tcp 2>/dev/null || true
fuser -k 3333/tcp 2>/dev/null || true
if command -v lsof &>/dev/null; then
    kill -9 $(lsof -t -i:8000) 2>/dev/null || true
    kill -9 $(lsof -t -i:3333) 2>/dev/null || true
fi
killall -9 node python python3 uvicorn chrome chromium chromium-browser ngrok 2>/dev/null || true
pkill -f -9 node 2>/dev/null || true
pkill -f -9 python 2>/dev/null || true
pkill -f -9 uvicorn 2>/dev/null || true
pkill -f -9 chrome 2>/dev/null || true
pkill -f -9 chromium 2>/dev/null || true
echo "[System] Cleanup completed. Ports 8000 and 3333 are now fully clear."


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

# 3b. Pull latest changes from GitHub automatically on startup
echo "[System] Checking for updates and pulling latest code from GitHub..."
git fetch --all 2>/dev/null || true
git reset --hard origin/main 2>/dev/null || true

# 4. Start the servers concurrently dropping root privileges
echo "[System] Booting Bot and Agent servers as user '${RUN_USER}'..."
cd "${ROOT_DIR}"

# Execute npm start as the non-root user to avoid Puppeteer profile blocks
sudo -u "${RUN_USER}" npm start

