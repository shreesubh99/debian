#!/usr/bin/env bash
# ==============================================================================
#  Configure Auto-Restart Service on Debian Boot (systemd)
#  - Window 1: WhatsApp Bot & Agent (npm start)
#  - Window 2: BankFlow Audit (bash run.sh)
# ==============================================================================

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CURRENT_USER="$(whoami)"

SUDO=""
if [ "$EUID" -ne 0 ]; then
    if command -v sudo &> /dev/null; then
        SUDO="sudo"
    fi
fi

echo "=========================================================="
echo "  ⚙️  Configuring Auto-Restart on Debian Boot (systemd)   "
echo "=========================================================="
echo "User:   ${CURRENT_USER}"
echo "Path:   ${SCRIPT_DIR}/start-all.sh"

SERVICE_FILE="/etc/systemd/system/office-servers.service"

${SUDO} bash -c "cat << 'EOF' > ${SERVICE_FILE}
[Unit]
Description=Office Suite - WhatsApp Bot (npm start) & BankFlow Audit (bash run.sh)
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=forking
User=${CURRENT_USER}
WorkingDirectory=${SCRIPT_DIR}
ExecStart=/bin/bash ${SCRIPT_DIR}/start-all.sh
ExecStop=/usr/bin/tmux kill-session -t office-servers
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF"

${SUDO} systemctl daemon-reload
${SUDO} systemctl enable office-servers.service
${SUDO} systemctl restart office-servers.service

echo ""
echo "=========================================================="
echo "  ✅ Auto-Restart Service Successfully Enabled!            "
echo "=========================================================="
echo "  • On system reboot, both servers will start automatically!"
echo "  • To check service status: sudo systemctl status office-servers"
echo "  • To see live split terminal: tmux a                    "
echo "=========================================================="
