#!/bin/bash
# =============================================================================
# static_arp.sh — Add static ARP entries to mitigate ARP spoofing
# Target Node: IT-Workstation (or any node to protect)
# =============================================================================
# Usage: ./static_arp.sh <SERVER_IP> <SERVER_REAL_MAC>
#
# Static ARP entries cannot be overwritten by ARP replies, preventing
# ARP spoofing attacks from poisoning the cache.
#
# IMPORTANT: Use the REAL MAC address of the server (recorded before the attack).
# =============================================================================

TARGET_IP="$1"
TARGET_MAC="$2"

if [ -z "$TARGET_IP" ] || [ -z "$TARGET_MAC" ]; then
    echo "Usage: $0 <TARGET_IP> <TARGET_REAL_MAC>"
    echo "Example: $0 192.168.1.1 aa:bb:cc:dd:ee:ff"
    echo ""
    echo "  TARGET_IP   = IP address of the host to protect against spoofing"
    echo "  TARGET_MAC  = The REAL MAC address of that host (not the spoofed one!)"
    echo ""
    echo "To find the real MAC, check your notes from the baseline step,"
    echo "or run 'ip addr show' on the target host directly."
    exit 1
fi

echo "[*] Current ARP table:"
arp -a
echo ""

echo "[*] Adding static ARP entry: $TARGET_IP -> $TARGET_MAC"
arp -s "$TARGET_IP" "$TARGET_MAC"

echo ""
echo "[+] Updated ARP table:"
arp -a
echo ""
echo "[+] The entry for $TARGET_IP should now show as PERM (permanent)."
echo "[+] ARP spoofing attempts against this entry will be ignored."
