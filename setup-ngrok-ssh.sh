#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

echo -e "\033[0;34m====================================================\033[0m"
echo -e "\033[0;34m  Automated Setup: Ngrok CLI & SSH on Debian Server \033[0m"
echo -e "\033[0;34m====================================================\033[0m"

# 1. Ensure the script is run as root/sudo
if [ "$EUID" -ne 0 ]; then
  echo -e "\033[0;31mError: Please run this script with sudo.\033[0m"
  echo -e "Usage: sudo ./setup-ngrok-ssh.sh"
  exit 1
fi

# 2. Install SSH Server (in case it is missing)
echo -e "\033[1;33m[1/4] Verifying and installing OpenSSH Server...\033[0m"
apt-get update -y
apt-get install -y openssh-server curl gnupg

# Enable and start SSH service
systemctl enable ssh
systemctl start ssh
echo -e "\033[0;32mSSH Server is active and running.\033[0m"

# 3. Add Ngrok GPG Key and Repository
echo -e "\033[1;33m[2/4] Adding Ngrok repository to APT sources...\033[0m"
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | tee /etc/apt/sources.list.d/ngrok.list

# 4. Install Ngrok CLI agent
echo -e "\033[1;33m[3/4] Installing Ngrok CLI agent...\033[0m"
apt-get update -y
apt-get install -y ngrok

# 5. Configure Authtoken
echo -e "\033[1;33m[4/4] Configuring Ngrok Authtoken...\033[0m"
NGROK_TOKEN="31yGVbAOlk0V2i0vjxJLHGkLclx_6XXNTqL8u39utRass2MB8"

# Configure for the user who called sudo, and also root
if [ "$SUDO_USER" ]; then
  sudo -u "$SUDO_USER" ngrok config add-authtoken "$NGROK_TOKEN"
fi
ngrok config add-authtoken "$NGROK_TOKEN"

echo -e "\033[0;32m====================================================\033[0m"
echo -e "\033[0;32m           SETUP COMPLETED SUCCESSFULLY!            \033[0m"
echo -e "\033[0;32m====================================================\033[0m"
echo -e "\nTo start the remote SSH tunnel, run the following command:"
echo -e "\033[1;33mngrok tcp 22\033[0m\n"
