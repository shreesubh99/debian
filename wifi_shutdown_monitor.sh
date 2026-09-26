#!/usr/bin/env bash

# ==============================================================================
# YTSK Intelligent 3-Level Network Monitor & Power Management Daemon
# ==============================================================================
# 3-Level Escalation Architecture:
# - Level 1 (0 to 5 Minutes): Initial Disconnection Stage
#     Continuously checks every 10s if network restores.
#     If restored -> Resets to Normal.
# - Level 2 (5 to 15 Minutes = 10 Min Cooldown): Extended Outage Stage
#     Continues checking every 10s.
#     If restored -> Resets to Normal.
# - Level 3 (15 to 20 Minutes = 5 Min Final Stage): Critical Final Stage
#     Gives a final 5-minute grace window.
#     If restored -> Resets to Normal.
# - Trigger Threshold (20 Minutes Total Continuous Outage):
#     1. Gracefully pauses the running WhatsApp Bot & AI Agent (systemctl stop ytsk-bot.service)
#        to prevent CPU/battery drain and API loop errors while offline.
#     2. Puts the system into Hibernate / Suspend / Hybrid-Sleep Power Save mode.
#     3. When network restores (or system resumes and reconnects to Wi-Fi/Ethernet):
#        Automatically starts the bot service (systemctl start ytsk-bot.service)
#        and returns to Normal monitoring!
# ==============================================================================

# Time durations in seconds:
LEVEL1_DURATION=300   # 5 minutes (300s)
LEVEL2_DURATION=600   # 10 minutes (600s cooldown)
LEVEL3_DURATION=300   # 5 minutes (300s final grace)
TOTAL_TIMEOUT=$((LEVEL1_DURATION + LEVEL2_DURATION + LEVEL3_DURATION)) # 20 minutes (1200s)

CHECK_INTERVAL=10     # Interval between ping checks in seconds
CONSECUTIVE_OFFLINE_SECONDS=0
BOT_PAUSED=false

echo "=========================================================="
echo " Starting YTSK 3-Level Network & Power Management Daemon  "
echo "=========================================================="
echo "Configured Stages:"
echo "  - Level 1: 5 Minutes initial network check"
echo "  - Level 2: 10 Minutes cooldown monitor"
echo "  - Level 3: 5 Minutes final grace period"
echo "  - Action: System Hibernate & Bot Pause (Auto-resumes on Wi-Fi)"
echo "=========================================================="

# Helper function to check internet connectivity
check_internet() {
    # Check via Google DNS (8.8.8.8) or Cloudflare DNS (1.1.1.1)
    if ping -c 1 -W 3 8.8.8.8 > /dev/null 2>&1 || ping -c 1 -W 3 1.1.1.1 > /dev/null 2>&1; then
        return 0 # Online
    else
        return 1 # Offline
    fi
}

while true; do
    if check_internet; then
        # Network is ONLINE
        if [ "$CONSECUTIVE_OFFLINE_SECONDS" -gt 0 ]; then
            echo "$(date): [Network Restored] Internet connectivity is back after ${CONSECUTIVE_OFFLINE_SECONDS}s of outage!"
        fi
        
        # If bot service was paused due to long outage, automatically resume/start it
        if [ "$BOT_PAUSED" = true ]; then
            echo "$(date): [Auto-Resume] Internet restored! Automatically starting WhatsApp Bot and AI Agent services..."
            systemctl start ytsk-bot.service || true
            BOT_PAUSED=false
            echo "$(date): [Auto-Resume] Bot services successfully restored and running."
        fi
        
        # Reset offline counters
        CONSECUTIVE_OFFLINE_SECONDS=0
    else
        # Network is OFFLINE
        CONSECUTIVE_OFFLINE_SECONDS=$((CONSECUTIVE_OFFLINE_SECONDS + CHECK_INTERVAL))
        
        if [ "$CONSECUTIVE_OFFLINE_SECONDS" -le "$LEVEL1_DURATION" ]; then
            # Level 1: First 5 minutes
            REMAINING_L1=$((LEVEL1_DURATION - CONSECUTIVE_OFFLINE_SECONDS))
            echo "$(date): [Level 1 - Initial Check] Offline for ${CONSECUTIVE_OFFLINE_SECONDS}s / ${LEVEL1_DURATION}s. (${REMAINING_L1}s left in Level 1). Checking network..."
        
        elif [ "$CONSECUTIVE_OFFLINE_SECONDS" -le "$((LEVEL1_DURATION + LEVEL2_DURATION))" ]; then
            # Level 2: Next 10 minutes (Cooldown stage)
            L2_ELAPSED=$((CONSECUTIVE_OFFLINE_SECONDS - LEVEL1_DURATION))
            REMAINING_L2=$((LEVEL2_DURATION - L2_ELAPSED))
            echo "$(date): [Level 2 - Cooldown Monitor] Offline for $((CONSECUTIVE_OFFLINE_SECONDS / 60))m. (${REMAINING_L2}s left in Level 2 10-min cooldown). Checking network..."
        
        elif [ "$CONSECUTIVE_OFFLINE_SECONDS" -lt "$TOTAL_TIMEOUT" ]; then
            # Level 3: Final 5 minutes before action
            REMAINING_L3=$((TOTAL_TIMEOUT - CONSECUTIVE_OFFLINE_SECONDS))
            echo "$(date): [Level 3 - Final Warning] Critical Offline! ${REMAINING_L3}s remaining before System Hibernation & Bot Pause..."
        
        else
            # Total 20 minutes offline reached: Trigger Hibernation & Bot Pause
            echo "=========================================================="
            echo "$(date): [ACTION TRIGGERED] Continuous 20-minute offline threshold reached."
            echo "1. Temporarily pausing WhatsApp Bot code to preserve power & prevent errors."
            echo "2. Putting system into Hibernate / Suspend mode."
            echo "=========================================================="
            
            # Step 1: Temporarily pause bot code
            echo "$(date): Pausing ytsk-bot.service..."
            systemctl stop ytsk-bot.service || true
            BOT_PAUSED=true
            
            # Step 2: Attempt System Hibernate / Hybrid-sleep / Suspend
            echo "$(date): Initiating system power-saving hibernation/standby..."
            if systemctl hibernate 2>/dev/null; then
                echo "$(date): System hibernated successfully."
            elif systemctl hybrid-sleep 2>/dev/null; then
                echo "$(date): System entered hybrid-sleep."
            elif systemctl suspend 2>/dev/null; then
                echo "$(date): System suspended."
            else
                echo "$(date): Hibernation/Suspend unsupported on this environment. Entering power-save idle loop waiting for network..."
            fi
            
            # Step 3: Wait in low-power loop until network is restored
            echo "$(date): Waiting for internet restoration to automatically resume bot..."
            while ! check_internet; do
                sleep 15
            done
            
            # Step 4: Network restored!
            echo "=========================================================="
            echo "$(date): [INTERNET RESTORED!] Auto-resuming system operations..."
            echo "=========================================================="
            systemctl start ytsk-bot.service || true
            BOT_PAUSED=false
            CONSECUTIVE_OFFLINE_SECONDS=0
        fi
    fi
    
    sleep $CHECK_INTERVAL
done
