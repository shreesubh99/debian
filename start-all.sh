#!/usr/bin/env bash

# ==============================================================================
#  MASTER RUNNER: WhatsApp Bot + Python AI Agent + BankFlow Audit System
#  Splits terminal into two parallel live windows (panes) using tmux.
# ==============================================================================

SESSION_NAME="office-servers"

# 0. Handle restart flag
if [ "$1" == "--restart" ] || [ "$1" == "-r" ] || [ "$1" == "restart" ]; then
    echo "[System] Killing previous session and restarting fresh..."
    tmux kill-session -t "${SESSION_NAME}" 2>/dev/null || true
    sleep 1
fi

# 1. Ensure tmux is installed
if ! command -v tmux &> /dev/null; then
    echo "[System] tmux is not installed. Installing tmux..."
    if [ "$EUID" -eq 0 ]; then
        apt-get update -y && apt-get install -y tmux
    else
        sudo apt-get update -y && sudo apt-get install -y tmux
    fi
fi

# 2. Check if session already running
if tmux has-session -t "${SESSION_NAME}" 2>/dev/null; then
    # Verify if services are actually alive
    if ! curl -s http://127.0.0.1:8080/api/health >/dev/null 2>&1 && ! curl -s http://127.0.0.1:3333 >/dev/null 2>&1; then
        echo "[System] Detected dead/stale session '${SESSION_NAME}'. Re-launching fresh..."
        tmux kill-session -t "${SESSION_NAME}" 2>/dev/null || true
        sleep 1
    else
        echo "[System] Session '${SESSION_NAME}' is already running!"
        if [ -t 0 ]; then
            echo "[System] Attaching to live windows now..."
            tmux attach-session -t "${SESSION_NAME}"
        else
            echo "[System] Running in background."
        fi
        exit 0
    fi
fi

# 3. Detect Paths dynamically
CURRENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
USER_HOME="${HOME:-/root}"

WA_DIR=""
for dir in "${CURRENT_DIR}/whatsapp-bot-server" "${USER_HOME}/whatsapp-bot-server" "/root/whatsapp-bot-server" "${CURRENT_DIR}/../whatsapp-bot-server" "${CURRENT_DIR}/../debian" "${USER_HOME}/debian" "/root/debian" "${CURRENT_DIR}"; do
    if [ -f "${dir}/start-debian.sh" ]; then
        WA_DIR="$(cd "${dir}" && pwd)"
        break
    fi
done

BANK_ROOT=""
for dir in "${CURRENT_DIR}" "${CURRENT_DIR}/bankflow-audit" "${USER_HOME}/bankflow-audit" "/root/bankflow-audit" "${CURRENT_DIR}/.."; do
    if [ -f "${dir}/backend/app/main.py" ] && [ -f "${dir}/run.sh" ]; then
        BANK_ROOT="$(cd "${dir}" && pwd)"
        break
    fi
done

echo "=========================================================="
echo " Starting Dual Server in Split Tmux Windows               "
echo "  • Window 1 (Left): WhatsApp Bot & AI Agent               "
echo "  • Window 2 (Right): BankFlow Audit System                "
echo "=========================================================="
echo "WhatsApp Directory: ${WA_DIR}"
echo "BankFlow Directory: ${BANK_ROOT}"

# 4. Launch tmux session with Left Pane (WhatsApp Bot)
tmux new-session -d -s "${SESSION_NAME}" -n "Office-Suite"
tmux send-keys -t "${SESSION_NAME}:0.0" "clear" C-m
tmux send-keys -t "${SESSION_NAME}:0.0" "echo '=== [WINDOW 1] WhatsApp Bot & Python Agent ==='" C-m
if [ -n "${WA_DIR}" ]; then
    tmux send-keys -t "${SESSION_NAME}:0.0" "cd '${WA_DIR}' && npm start" C-m
else
    tmux send-keys -t "${SESSION_NAME}:0.0" "echo 'Warning: whatsapp-bot-server directory not found. Please clone it to ~/debian or ~/whatsapp-bot-server'" C-m
fi

# 5. Split Window Horizontally into Right Pane (BankFlow Audit)
tmux split-window -h -t "${SESSION_NAME}:0"
tmux send-keys -t "${SESSION_NAME}:0.1" "clear" C-m
tmux send-keys -t "${SESSION_NAME}:0.1" "echo '=== [WINDOW 2] BankFlow Audit System (Port 8080) ==='" C-m
if [ -n "${BANK_ROOT}" ]; then
    tmux send-keys -t "${SESSION_NAME}:0.1" "cd '${BANK_ROOT}' && bash run.sh" C-m
else
    tmux send-keys -t "${SESSION_NAME}:0.1" "cd '${CURRENT_DIR}' && bash run.sh" C-m
fi

# Enable mouse mode for easy clicking between panes
tmux set-option -t "${SESSION_NAME}" -g mouse on 2>/dev/null || true

echo "[System] Both systems started in parallel!"
if [ -t 0 ]; then
    echo "[System] Attaching to split screen... (To detach, press Ctrl+B then D)"
    tmux attach-session -t "${SESSION_NAME}"
else
    echo "[System] Running in background under session '${SESSION_NAME}'."
    echo "[System] To view live windows anytime, run: tmux a"
fi
