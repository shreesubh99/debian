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

# 1b. Force clean all stale services, processes, ports, and memory before launching
echo "[System] Performing comprehensive system and process cleanup before boot..."

# 1b-1. Stop conflicting background systemd services so they don't loop-restart and send SIGKILL
if command -v systemctl &>/dev/null; then
    echo "[System] Stopping conflicting background systemd services..."
    systemctl stop ytsk-bot.service 2>/dev/null || true
    systemctl stop office-servers.service 2>/dev/null || true
fi

# 1b-2. Kill duplicate runner.js, stale uvicorn, bot, and chrome processes
echo "[System] Terminating all stale runner, bot, python, and chromium processes..."
pkill -9 -f "runner.js" 2>/dev/null || true
pkill -9 -f "uvicorn" 2>/dev/null || true
pkill -9 -f "src.server:app" 2>/dev/null || true
pkill -9 -f "whatsapp.*server.js" 2>/dev/null || true
pkill -9 -f "node.*server.js" 2>/dev/null || true
killall -9 chrome chromium chromium-browser 2>/dev/null || true
pkill -9 -f "chromium" 2>/dev/null || true
pkill -9 -f "chrome" 2>/dev/null || true

# 1b-3. Multi-layer port cleanup (8000 and 3333)
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

# 1b-4. Clear stale Puppeteer lock files
rm -f "${ROOT_DIR}/whatsapp/session/session/SingletonLock" 2>/dev/null || true
rm -f "${ROOT_DIR}/whatsapp/session/session/DevToolsActivePort" 2>/dev/null || true
rm -f "${ROOT_DIR}/whatsapp/.puppeteer_cache/SingletonLock" 2>/dev/null || true
rm -f "${ROOT_DIR}/whatsapp/.puppeteer_cache/DevToolsActivePort" 2>/dev/null || true

# 1b-5. Ensure minimum 2GB Swap space to protect from Linux Kernel OOM SIGKILL
if [ "$EUID" -eq 0 ]; then
    SWAP_SIZE=$(free -m 2>/dev/null | awk '/Swap/ {print $2}')
    if [ -z "$SWAP_SIZE" ] || [ "$SWAP_SIZE" -lt 1024 ]; then
        echo "[System] Low/no swap detected (${SWAP_SIZE}MB). Enabling 2GB swap file to prevent OOM SIGKILL..."
        if [ ! -f /swapfile ]; then
            fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048 2>/dev/null || true
            chmod 600 /swapfile 2>/dev/null || true
            mkswap /swapfile 2>/dev/null || true
        fi
        swapon /swapfile 2>/dev/null || true
        if ! grep -q "/swapfile" /etc/fstab 2>/dev/null; then
            echo "/swapfile none swap sw 0 0" >> /etc/fstab 2>/dev/null || true
        fi
        echo "[System] 2GB Swap verified and active."
    fi
fi

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

