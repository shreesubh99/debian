#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "=========================================================="
echo "      Debian Unified Setup: WhatsApp Bot & AI Agent       "
echo "=========================================================="

# 1. Run as root check
if [ "$EUID" -ne 0 ]; then
  echo "Error: Please run this script as root or using sudo."
  exit 1
fi

# Pre-installation Swap Check to prevent OOM Killer (Exit Code 137)
echo "Checking Swap Space configuration..."
SWAP_SIZE=$(free -m | awk '/Swap/ {print $2}')
if [ -z "$SWAP_SIZE" ] || [ "$SWAP_SIZE" -eq 0 ]; then
    echo "No swap space detected! Creating a 2GB swap file to protect Node/Python/Chrome from OOM crashes (Exit Code 137)..."
    fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    if ! grep -q "/swapfile" /etc/fstab; then
        echo "/swapfile none swap sw 0 0" >> /etc/fstab
    fi
    echo "✅ 2GB Swap space successfully created and enabled."
else
    echo "Swap space is already configured: ${SWAP_SIZE}MB. Skipping swap creation."
fi

# Pre-installation System-wide Port & Process Cleanup (Resolves Locked Ports/Chrome)
echo "Performing pre-installation system cleanup as root..."

# Stop background services
systemctl stop ytsk-bot.service 2>/dev/null || true
systemctl stop ytsk-wifi-monitor.service 2>/dev/null || true

# Force kill Node, Python, Chrome/Chromium, and Ngrok processes
killall -9 node python python3 uvicorn chrome chromium chromium-browser ngrok 2>/dev/null || true
pkill -f -9 node 2>/dev/null || true
pkill -f -9 python 2>/dev/null || true
pkill -f -9 uvicorn 2>/dev/null || true
pkill -f -9 chrome 2>/dev/null || true
pkill -f -9 chromium 2>/dev/null || true

# Determine script directories for pre-cleaning lock files
TEMP_SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
if [ -d "${TEMP_SCRIPT_DIR}/whatsapp" ] && [ -d "${TEMP_SCRIPT_DIR}/agent" ]; then
    TEMP_ROOT_DIR="${TEMP_SCRIPT_DIR}"
else
    TEMP_ROOT_DIR="${TEMP_SCRIPT_DIR}/whatsapp-bot-server"
fi

# Clean up stale session lock files
if [ -d "${TEMP_ROOT_DIR}/whatsapp/session/session" ]; then
    echo "Clearing stale session lock files..."
    rm -f "${TEMP_ROOT_DIR}/whatsapp/session/session/SingletonLock" 2>/dev/null || true
    rm -f "${TEMP_ROOT_DIR}/whatsapp/session/session/DevToolsActivePort" 2>/dev/null || true
fi

echo "System cleanup completed successfully."

# 2. System updates
echo "[1/5] Updating system packages..."
apt-get update && apt-get upgrade -y

# 3. Install Node.js LTS (v20)
echo "[2/5] Installing Node.js & npm..."
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
else
    echo "Node.js is already installed: $(node -v)"
fi

# 4. Install Python 3 & pip
echo "[3/5] Installing Python 3 & pip..."
apt-get install -y python3 python3-pip python3-venv

# 5. Install Puppeteer/Chrome Native Dependencies & Chromium Browser
echo "[4/5] Installing Puppeteer system dependencies & Chromium Browser..."
apt-get install -y wget gnupg ca-certificates procps libxss1 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libdbus-1-3 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libasound2 libpango-1.0-0 libcairo2 libx11-xcb1 libxfixes3 \
    libxi6 libxtst6 libnss3 chromium

# 6. Configure project structures and self-healing requirements
echo "[5/5] Configuring project requirements..."
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Auto-detect folder layout (flat directory or nested inside whatsapp-bot-server/)
if [ -d "${SCRIPT_DIR}/whatsapp" ] && [ -d "${SCRIPT_DIR}/agent" ]; then
    ROOT_DIR="${SCRIPT_DIR}"
    WA_DIR="${SCRIPT_DIR}/whatsapp"
    AGENT_DIR="${SCRIPT_DIR}/agent"
    echo "Detected flat directory structure at: ${ROOT_DIR}"
elif [ -d "${SCRIPT_DIR}/whatsapp-bot-server/whatsapp" ] && [ -d "${SCRIPT_DIR}/whatsapp-bot-server/agent" ]; then
    ROOT_DIR="${SCRIPT_DIR}/whatsapp-bot-server"
    WA_DIR="${SCRIPT_DIR}/whatsapp-bot-server/whatsapp"
    AGENT_DIR="${SCRIPT_DIR}/whatsapp-bot-server/agent"
    echo "Detected nested directory structure at: ${ROOT_DIR}"
else
    # Create defaults in script directory
    ROOT_DIR="${SCRIPT_DIR}/whatsapp-bot-server"
    WA_DIR="${ROOT_DIR}/whatsapp"
    AGENT_DIR="${ROOT_DIR}/agent"
    mkdir -p "$WA_DIR"
    mkdir -p "$AGENT_DIR"
    echo "Created default directory structure at: ${ROOT_DIR}"
fi

# Ensure RAILKIT_API_KEY is configured in the actual .env file during setup
if [ -f "${ROOT_DIR}/.env" ]; then
    echo "Updating RAILKIT_API_KEY in the actual .env file..."
    if grep -q "^RAILKIT_API_KEY=" "${ROOT_DIR}/.env"; then
        sed -i 's|^RAILKIT_API_KEY=.*|RAILKIT_API_KEY=irctc_49ac9361264ab72fe4bf3d139a8ec0cf904dcb834e0fa|' "${ROOT_DIR}/.env"
    else
        echo "RAILKIT_API_KEY=irctc_49ac9361264ab72fe4bf3d139a8ec0cf904dcb834e0fa" >> "${ROOT_DIR}/.env"
    fi
else
    echo "Creating .env configuration file from template..."
    cp "${ROOT_DIR}/.env.example" "${ROOT_DIR}/.env"
fi

# Clean Windows carriage returns (\r) in .env and scripts immediately
if [ -f "${ROOT_DIR}/.env" ]; then
    echo "Cleaning Windows carriage returns (\r) from .env..."
    sed -i 's/\r$//' "${ROOT_DIR}/.env"
fi
# 
# # Automatically configure Gemini as the primary provider (Lite version for higher quota)
# if [ -f "${ROOT_DIR}/.env" ]; then
#     echo "Automatically configuring Gemini 3.5 Flash Lite as the primary provider..."
#     sed -i 's|^PRIMARY_PROVIDER=.*|PRIMARY_PROVIDER=gemini|' "${ROOT_DIR}/.env"
#     sed -i 's|^PRIMARY_MODEL=.*|PRIMARY_MODEL=gemini-3.5-flash-lite|' "${ROOT_DIR}/.env"
#     sed -i 's|^SECONDARY_PROVIDER=.*|SECONDARY_PROVIDER=gemini|' "${ROOT_DIR}/.env"
#     sed -i 's|^SECONDARY_MODEL=.*|SECONDARY_MODEL=gemini-3.5-flash-lite|' "${ROOT_DIR}/.env"
#     sed -i 's|^GROQ_MODEL=.*|GROQ_MODEL=qwen/qwen3.6-27b|' "${ROOT_DIR}/.env"
# fi
# 
# # Interactive API Key Prompting during setup
# if [ -f "${ROOT_DIR}/.env" ]; then
#     # Read current keys
#     CURRENT_GEMINI=$(grep "^GEMINI_API_KEY=" "${ROOT_DIR}/.env" | cut -d'=' -f2-)
#     CURRENT_GROQ=$(grep "^GROQ_API_KEY=" "${ROOT_DIR}/.env" | cut -d'=' -f2-)
#     
#     # Check if Gemini key is incomplete
#     if [[ "$CURRENT_GEMINI" == *"___"* ]] || [[ "$CURRENT_GEMINI" == *"YOUR_GEMINI"* ]] || [ -z "$CURRENT_GEMINI" ]; then
#         echo ""
#         echo "=========================================================="
#         echo "🔑 GEMINI_API_KEY is incomplete or not configured!"
#         echo "Please paste your COMPLETE Google Gemini API key:"
#         echo "=========================================================="
#         read -r USER_GEMINI
#         USER_GEMINI=$(echo "$USER_GEMINI" | tr -d '\r' | xargs)
#         if [ -n "$USER_GEMINI" ]; then
#             sed -i "s|^GEMINI_API_KEY=.*|GEMINI_API_KEY=$USER_GEMINI|" "${ROOT_DIR}/.env"
#             echo "✅ Gemini API Key updated."
#         fi
#     fi
#     
#     # Check if Groq key is incomplete
#     if [[ "$CURRENT_GROQ" == *"___"* ]] || [[ "$CURRENT_GROQ" == *"YOUR_GROQ"* ]] || [ -z "$CURRENT_GROQ" ]; then
#         echo ""
#         echo "=========================================================="
#         echo "🔑 GROQ_API_KEY is incomplete or not configured!"
#         echo "Please paste your COMPLETE Groq API key:"
#         echo "=========================================================="
#         read -r USER_GROQ
#         USER_GROQ=$(echo "$USER_GROQ" | tr -d '\r' | xargs)
#         if [ -n "$USER_GROQ" ]; then
#             sed -i "s|^GROQ_API_KEY=.*|GROQ_API_KEY=$USER_GROQ|" "${ROOT_DIR}/.env"
#             echo "✅ Groq API Key updated."
#         fi
#     fi
# fi

# API keys are pre-configured in .env.example templates for fully automated startup

# Write the self-healing Python requirement installer script
cat << 'EOF' > "${ROOT_DIR}/install_requirements.py"
import os
import sys
import subprocess
import json
import urllib.request

# Load env variables manually to avoid dependencies
def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip()
    return env_vars

def get_gemini_fix(api_key, err_msg):
    prompt = f"""
You are a Debian Linux systems administrator and Python packaging expert.
The user is trying to install Python requirements via pip, but it failed with the following error:
---
{err_msg}
---
Please analyze the error and suggest specific shell commands to resolve it (e.g. installing missing debian system packages using apt-get, or modifying pip install flags).
Return ONLY a valid JSON list of command strings to run, with no extra text or markdown formatting. Example format:
[
  "sudo apt-get install -y default-libmysqlclient-dev",
  "pip3 install mysql-connector-python --break-system-packages"
]
"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            # Strip potential markdown code block backticks
            if text.startswith("```"):
                lines = text.split("\n")
                if lines[0].startswith("```json") or lines[0].startswith("```"):
                    lines = lines[1:-1]
                text = "\n".join(lines).strip()
            return json.loads(text)
    except Exception as e:
        print(f"[Self-Healer Error] Failed to contact Gemini API: {e}")
        return []

def main():
    env = load_env()
    api_key = env.get("GEMINI_API_KEY", "")
    requirements_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent", "requirements.txt")
    
    if not os.path.exists(requirements_path):
        print(f"Error: requirements.txt not found at {requirements_path}")
        sys.exit(1)
        
    print("[Installer] Starting Python requirements installation...")
    
    # Try normal pip installation (first attempt)
    pip_cmd = ["pip3", "install", "-r", requirements_path, "--break-system-packages"]
    process = subprocess.run(pip_cmd, capture_output=True, text=True)
    
    if process.returncode == 0:
        print("[Installer] Python requirements installed successfully.")
        sys.exit(0)
        
    # Attempt fallback without --break-system-packages if not supported
    if "no such option: --break-system-packages" in process.stderr:
        pip_cmd = ["pip3", "install", "-r", requirements_path]
        process = subprocess.run(pip_cmd, capture_output=True, text=True)
        if process.returncode == 0:
            print("[Installer] Python requirements installed successfully.")
            sys.exit(0)

    # First attempt failed, trigger self-healing
    print("\n[Self-Healer] Installation failed! Stderr details:")
    print(process.stderr)
    
    if not api_key:
        print("[Self-Healer] GEMINI_API_KEY is not defined in .env. Skipping self-healing.")
        sys.exit(1)
        
    print("\n[Self-Healer] Querying Gemini AI chatbot to heal installation error...")
    fixes = get_gemini_fix(api_key, process.stderr)
    
    if not fixes:
        print("[Self-Healer] Gemini was unable to suggest any fix commands.")
        sys.exit(1)
        
    print(f"[Self-Healer] Gemini suggested {len(fixes)} fix command(s) to execute:")
    for cmd in fixes:
        print(f"  -> {cmd}")
        
    # Execute fixes
    for cmd in fixes:
        print(f"\n[Self-Healer] Running: {cmd}")
        sub_proc = subprocess.run(cmd, shell=True)
        if sub_proc.returncode != 0:
            print(f"[Self-Healer Warning] Command failed with code {sub_proc.returncode}")
            
    # Retry pip installation (second attempt)
    print("\n[Installer] Retrying requirements installation after self-healing...")
    process_retry = subprocess.run(pip_cmd)
    if process_retry.returncode == 0:
        print("[Installer] Requirements installed successfully after self-healing!")
        sys.exit(0)
    else:
        print("[Installer Error] Requirements installation failed again after self-healing.")
        sys.exit(1)

if __name__ == "__main__":
    main()
EOF

# Execute self-healing Python installer
echo "Installing Python packages..."
python3 "${ROOT_DIR}/install_requirements.py"

# Install Node packages for WhatsApp Bot
if [ -d "$WA_DIR" ]; then
    echo "Installing Node.js packages..."
    cd "$WA_DIR"
    npm install
else
    echo "Warning: WhatsApp Bot folder not found at ${WA_DIR}."
fi

# 7. Configure automated daily training cron job (2:30 PM)
echo "Setting up daily fine-tuning cron job at 2:30 PM..."
CRON_JOB="30 14 * * * /usr/bin/python3 ${AGENT_DIR}/src/scripts/train_agent.py >> ${ROOT_DIR}/tuning_cron.log 2>&1"
(crontab -l 2>/dev/null | grep -F "train_agent.py") && echo "Cron job already exists." || ( (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab - )
echo "Cron job registered successfully to run daily at 14:30 (2:30 PM)."
echo ""

# 8. Configure Systemd Auto-Start Service (Run on boot)
echo "Setting up background systemd auto-start service..."
SERVICE_FILE="/etc/systemd/system/ytsk-bot.service"
RUN_USER="${SUDO_USER:-beck}"
NPM_PATH=$(which npm || echo "/usr/bin/npm")

# Ensure permissions on root directory belong to the user
chown -R "$RUN_USER:$RUN_USER" "$ROOT_DIR"
chmod -R 755 "$ROOT_DIR"

# Ensure start-debian.sh at root is executable
if [ -f "${SCRIPT_DIR}/start-debian.sh" ]; then
    chown "$RUN_USER:$RUN_USER" "${SCRIPT_DIR}/start-debian.sh"
    chmod +x "${SCRIPT_DIR}/start-debian.sh"
fi

cat <<EOF | sudo tee "$SERVICE_FILE" > /dev/null
[Unit]
Description=YTSK WhatsApp Bot & Python AI Agent Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${ROOT_DIR}
ExecStart=/bin/bash ${ROOT_DIR}/start-debian.sh
Restart=always
RestartSec=10
Environment=NODE_ENV=production

[Install]
WantedBy=multi-user.target
EOF

# Reload daemon and enable service to run on boot
sudo systemctl daemon-reload
sudo systemctl enable ytsk-bot.service
echo "Systemd service 'ytsk-bot.service' created and configured to run on boot!"
echo ""

# 9. Configure Wi-Fi Network Monitor Service (Auto-shutdown on boot)
echo "Setting up background systemd Wi-Fi monitor and shutdown service..."
MONITOR_SERVICE_FILE="/etc/systemd/system/ytsk-wifi-monitor.service"

# Make the wifi monitor script executable
chmod +x "${ROOT_DIR}/wifi_shutdown_monitor.sh"

cat <<EOF | sudo tee "$MONITOR_SERVICE_FILE" > /dev/null
[Unit]
Description=YTSK Wi-Fi Monitor & Shutdown Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${ROOT_DIR}
ExecStart=/bin/bash ${ROOT_DIR}/wifi_shutdown_monitor.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload daemon and enable the wifi monitor service to run on boot
sudo systemctl daemon-reload
sudo systemctl enable ytsk-wifi-monitor.service
echo "Systemd service 'ytsk-wifi-monitor.service' created and configured to run on boot!"
echo ""

# Restart the services automatically so they run instantly on setup completion
echo "Starting background services (ytsk-bot.service & ytsk-wifi-monitor.service)..."
sudo systemctl restart ytsk-bot.service
sudo systemctl restart ytsk-wifi-monitor.service

echo "=========================================================="
echo "           SETUP COMPLETED SUCCESSFULLY!                 "
echo "=========================================================="
echo "Your WhatsApp Bot and Python AI Agent services are now running!"
echo "Check bot status by running:"
echo "  sudo systemctl status ytsk-bot.service"
echo ""
echo "Or check live logs by running:"
echo "  sudo journalctl -u ytsk-bot.service -f"
echo "=========================================================="
