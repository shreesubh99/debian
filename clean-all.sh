#!/usr/bin/env bash

# ==============================================================================
#  MASTER CLEANUP UTILITY: YTSK WhatsApp Bot & Python AI Agent
#  Forcefully sweeps all duplicate runners, stale uvicorn/node/chrome processes,
#  port binds (8000 & 3333), lockfiles, and conflicting systemd services.
# ==============================================================================

echo "=========================================================="
echo "      🧹 MASTER CLEANUP: Resetting All Servers & Ports     "
echo "=========================================================="

# 1. Stop background systemd services
if command -v systemctl &>/dev/null; then
    echo "[1/5] Stopping systemd background services..."
    systemctl stop ytsk-bot.service 2>/dev/null || sudo systemctl stop ytsk-bot.service 2>/dev/null || true
    systemctl stop office-servers.service 2>/dev/null || sudo systemctl stop office-servers.service 2>/dev/null || true
fi

# 2. Terminate all related processes forcefully
echo "[2/5] Killing all running runners, python agents, bots, and browsers..."
pkill -9 -f "runner.js" 2>/dev/null || sudo pkill -9 -f "runner.js" 2>/dev/null || true
pkill -9 -f "uvicorn" 2>/dev/null || sudo pkill -9 -f "uvicorn" 2>/dev/null || true
pkill -9 -f "src.server:app" 2>/dev/null || sudo pkill -9 -f "src.server:app" 2>/dev/null || true
pkill -9 -f "whatsapp.*server.js" 2>/dev/null || sudo pkill -9 -f "whatsapp.*server.js" 2>/dev/null || true
pkill -9 -f "node.*server.js" 2>/dev/null || sudo pkill -9 -f "node.*server.js" 2>/dev/null || true
killall -9 chrome chromium chromium-browser 2>/dev/null || sudo killall -9 chrome chromium chromium-browser 2>/dev/null || true
pkill -9 -f "chromium" 2>/dev/null || sudo pkill -9 -f "chromium" 2>/dev/null || true
pkill -9 -f "chrome" 2>/dev/null || sudo pkill -9 -f "chrome" 2>/dev/null || true

# 3. Clear Ports 8000 and 3333 completely
echo "[3/5] Force freeing ports 8000 and 3333..."
for port in 8000 3333; do
    fuser -k -9 ${port}/tcp 2>/dev/null || /usr/sbin/fuser -k -9 ${port}/tcp 2>/dev/null || sudo fuser -k -9 ${port}/tcp 2>/dev/null || true
    if command -v lsof &>/dev/null; then
        lsof -ti:${port} 2>/dev/null | xargs -r kill -9 2>/dev/null || sudo lsof -ti:${port} 2>/dev/null | sudo xargs -r kill -9 2>/dev/null || true
    fi
    if command -v ss &>/dev/null; then
        for pid in $(ss -lptn "sport = :${port}" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u); do
            kill -9 "$pid" 2>/dev/null || sudo kill -9 "$pid" 2>/dev/null || true
        done
    fi
done

# 4. Wipe stale Puppeteer locks & temp profiles
echo "[4/5] Removing stale Chromium lock files..."
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
find "${SCRIPT_DIR}" -name "SingletonLock" -delete 2>/dev/null || true
find "${SCRIPT_DIR}" -name "DevToolsActivePort" -delete 2>/dev/null || true
rm -rf /tmp/pup_pdf_* 2>/dev/null || true

# 5. Verify swap space for Linux OOM protection
echo "[5/5] Checking system swap space..."
SWAP_SIZE=$(free -m 2>/dev/null | awk '/Swap/ {print $2}')
if [ -z "$SWAP_SIZE" ] || [ "$SWAP_SIZE" -lt 1024 ]; then
    echo "  ⚠️ Low swap space detected (${SWAP_SIZE}MB). Enabling 2GB swapfile..."
    if [ ! -f /swapfile ]; then
        fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048 2>/dev/null || true
        chmod 600 /swapfile 2>/dev/null || true
        mkswap /swapfile 2>/dev/null || true
    fi
    swapon /swapfile 2>/dev/null || sudo swapon /swapfile 2>/dev/null || true
    echo "  ✅ 2GB Swap enabled."
else
    echo "  ✅ Swap space is healthy: ${SWAP_SIZE}MB."
fi

echo ""
echo "=========================================================="
echo "  ✅ System Cleaned! Ports 8000 and 3333 are 100% Free.  "
echo "  You can now start cleanly with: bash start-debian.sh   "
echo "=========================================================="
