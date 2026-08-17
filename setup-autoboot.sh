#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== YTSK Debian Console Login Autostart Setup ===${NC}"

# Kill any conflicting orphaned Node or Ngrok processes immediately
echo -e "${BLUE}Cleaning up any conflicting Node.js or Ngrok background processes...${NC}"
sudo killall -9 node ngrok 2>/dev/null || true

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
NODE_PATH=$(which node)

if [ -z "$NODE_PATH" ]; then
    echo -e "${RED}Error: Node.js not found! Please run setup-debian.sh first.${NC}"
    exit 1
fi

# Hardcode username to beck
CURRENT_USER="beck"
echo -e "Target User: ${GREEN}$CURRENT_USER${NC}"

# 1. Clean up old background systemd service to prevent conflicts
echo -e "\n${BLUE}[1/5] Disabling background systemd service (to avoid conflicts)...${NC}"
sudo systemctl stop whatsapp-bot &>/dev/null || true
sudo systemctl disable whatsapp-bot &>/dev/null || true
sudo rm -f /etc/systemd/system/whatsapp-bot.service
sudo systemctl daemon-reload

# 2. Fix Directory and File Permissions permanently (Crucial for WhatsApp Session persistence)
echo -e "\n${BLUE}[2/5] Fixing file ownership and permissions for user '$CURRENT_USER'...${NC}"

# Ensure user's home directories are owned by the user
USER_HOME=$(getent passwd "$CURRENT_USER" | cut -d: -f6)
if [ -d "$USER_HOME" ]; then
    sudo chown -R $CURRENT_USER:$CURRENT_USER "$USER_HOME/.cache" 2>/dev/null || true
    sudo chown -R $CURRENT_USER:$CURRENT_USER "$USER_HOME/.config" 2>/dev/null || true
fi

# Give ownership of the entire project directory to beck
sudo chown -R $CURRENT_USER:$CURRENT_USER "$SCRIPT_DIR"

# Set open read/write/execute permissions for project files
sudo chmod -R 755 "$SCRIPT_DIR"

# Set full read/write permissions for the session folder specifically
if [ -d "$SCRIPT_DIR/session" ]; then
    sudo chmod -R 777 "$SCRIPT_DIR/session" 2>/dev/null || true
fi

# Ensure startup scripts are executable
chmod +x "$SCRIPT_DIR/start-server.sh"
chmod +x "$SCRIPT_DIR/setup-debian.sh"

echo -e "${GREEN}✓ File ownership and permissions configured successfully.${NC}"

# 3. Add user to the autologin group
echo -e "\n${BLUE}[3/5] Adding user to 'autologin' system group...${NC}"
sudo groupadd -r autologin 2>/dev/null || true
sudo usermod -aG autologin $CURRENT_USER
echo -e "${GREEN}✓ User $CURRENT_USER added to 'autologin' group.${NC}"

# 4. Configure PAM to allow passwordless login
echo -e "\n${BLUE}[4/5] Configuring PAM password bypass...${NC}"
PAM_FILE="/etc/pam.d/login"
if [ -f "$PAM_FILE" ]; then
    sudo sed -i '/user ingroup autologin/d' "$PAM_FILE"
    sudo sed -i '/user = beck/d' "$PAM_FILE"
    sudo sed -i '/user = Beck/d' "$PAM_FILE"
    
    # Prepend direct user bypass rules to the top of the file
    sudo sed -i '1s/^/auth sufficient pam_succeed_if.so user = beck\nauth sufficient pam_succeed_if.so user = Beck\n/' "$PAM_FILE"
    echo -e "${GREEN}✓ PAM login bypass enabled.${NC}"
fi

# Getty TTY1 override configuration (to auto-login)
GETTY_CONF_DIR="/etc/systemd/system/getty@tty1.service.d"
sudo mkdir -p "$GETTY_CONF_DIR"
cat <<EOF | sudo tee "$GETTY_CONF_DIR/override.conf" > /dev/null
[Service]
ExecStart=
ExecStart=-/sbin/agetty --noclear --autologin $CURRENT_USER %I \$TERM
EOF
sudo systemctl daemon-reload
echo -e "${GREEN}✓ CLI getty auto-login fallback configured (Bypass password enabled).${NC}"

# 5. Configure Shell Autostart in .bashrc (Runs server in terminal window on tty1 login)
echo -e "\n${BLUE}[5/5] Configuring .bashrc Shell Autostart...${NC}"
BASHRC_FILE="$USER_HOME/.bashrc"

if [ -f "$BASHRC_FILE" ]; then
    # Remove any old auto-start blocks to avoid duplicates
    sudo sed -i '/# YTSK WhatsApp Server Autostart/,/# End YTSK/d' "$BASHRC_FILE"
    
    # Append autostart block (Runs server automatically ONLY when logging in on physical console tty1)
    cat <<EOF | sudo tee -a "$BASHRC_FILE" > /dev/null

# YTSK WhatsApp Server Autostart
if [ "\$(tty)" = "/dev/tty1" ]; then
    echo -e "\n${BLUE}🚀 Starting YTSK WhatsApp Bot Server automatically...${NC}"
    cd "$SCRIPT_DIR"
    ./start-server.sh
fi
# End YTSK
EOF
    sudo chown "$CURRENT_USER:$CURRENT_USER" "$BASHRC_FILE"
    echo -e "${GREEN}✓ Shell autostart added to $BASHRC_FILE (Runs on physical TTY1 login).${NC}"
else
    echo -e "${RED}Error: .bashrc file not found for user $CURRENT_USER!${NC}"
fi

# Configure Passwordless Sudo
SUDOERS_FILE="/etc/sudoers.d/$CURRENT_USER"
echo "$CURRENT_USER ALL=(ALL) NOPASSWD:ALL" | sudo tee "$SUDOERS_FILE" > /dev/null
sudo chmod 0440 "$SUDOERS_FILE"

echo -e "\n${GREEN}=== Setup Complete! ===${NC}"
echo -e "✓ Permissions fixed: Session will now persist across reboots."
echo -e "✓ The WhatsApp server will start automatically as user '$CURRENT_USER' on boot."
echo -e "\n${RED}⚠️ IMPORTANT: Never run the server manually using 'sudo npm start' or 'sudo node server.js'.${NC}"
echo -e "${RED}             Always run it as a normal user (./start-server.sh) to prevent session locks!${NC}"
echo -e "\n${GREEN}Please reboot to verify everything: sudo reboot${NC}"
