#!/usr/bin/env bash

# Network Monitor Shutdown Script
# Checks internet connectivity by pinging Google DNS (8.8.8.8)
# If offline continuously for 15 minutes, shuts down the system safely.

OFFLINE_COUNT=0
MAX_OFFLINE_LIMIT=6  # 6 check failures (each check is ~15s total with timeout) = 1.5 minutes offline
CHECK_INTERVAL=10   # Check every 10 seconds

echo "Starting internet connection monitoring daemon..."

while true; do
    # Ping Google DNS to check connection (1 ping, 5 second timeout)
    if ping -c 1 -W 5 8.8.8.8 > /dev/null 2>&1; then
        # Connection is active, reset counter
        OFFLINE_COUNT=0
        echo "$(date): Connection OK."
    else
        OFFLINE_COUNT=$((OFFLINE_COUNT + 1))
        echo "$(date): Connection offline! Offline count: ${OFFLINE_COUNT}/${MAX_OFFLINE_LIMIT}"
        
        # If offline limit reached, initiate shutdown
        if [ "$OFFLINE_COUNT" -ge "$MAX_OFFLINE_LIMIT" ]; then
            echo "$(date): System offline for 1.5 minutes. Initiating automatic shutdown..."
            sudo shutdown -h now
            exit 0
        fi
    fi
    sleep $CHECK_INTERVAL
done
