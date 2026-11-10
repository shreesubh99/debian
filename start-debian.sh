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

# 1b. Force clean whatsapp bot ports and stale processes as root before launching
echo "[System] Performing strict port and process cleanup before boot..."
for port in 8000 3333; do
    fuser -k -9 ${port}/tcp 2>/dev/null || /usr/sbin/fuser -k -9 ${port}/tcp 2>/dev/null || true
    if command -v lsof &>/dev/null; then
        lsof -ti:${port} 2>/dev/null | xargs -r kill -9 2>/dev/null || true
    fi
    if command -v ss &>/dev/null; then
        for pid in $(ss -lptn "sport = :${port}" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u); do
            kill -9 "$pid" 2>/dev/null || true
        done
    fi
done

pkill -9 -f "uvicorn.*8000" 2>/dev/null || true
pkill -9 -f "src.server:app" 2>/dev/null || true
pkill -9 -f "whatsapp" 2>/dev/null || true
pkill -9 -f "server.js" 2>/dev/null || true
killall -9 chrome chromium chromium-browser 2>/dev/null || true
sleep 1
echo "[System] Cleanup completed. Ports 8000 and 3333 are now fully clear and ready."


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

# 3c. Run setup-debian.sh only if dependencies are missing or --setup is requested
if [ "$1" == "--setup" ] || ! command -v node &>/dev/null || ! command -v chromium &>/dev/null; then
    echo "[System] Running setup-debian.sh to configure environment..."
    bash "${ROOT_DIR}/setup-debian.sh" --no-restart
fi


# 4. Start the servers concurrently dropping root privileges
echo "[System] Booting Bot and Agent servers as user '${RUN_USER}'..."
cd "${ROOT_DIR}"

# Execute npm start as the non-root user to avoid Puppeteer profile blocks
sudo -u "${RUN_USER}" npm start

