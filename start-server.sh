#!/usr/bin/env bash

# ==============================================================================
# Auto-update and Startup Wrapper for WhatsApp Bot Server
# ==============================================================================

# Exit immediately if a command exits with a non-zero status.
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "\033[0;34m[YTSK-Server] Checking for dependencies update...\033[0m"
# Runs npm install to ensure package.json changes (e.g. adding ngrok) are installed
npm install

echo -e "\033[0;32m[YTSK-Server] Launching WhatsApp Bot Server...\033[0m"
# Starts the server
npm start
