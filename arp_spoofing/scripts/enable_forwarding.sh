#!/bin/bash
# =============================================================================
# enable_forwarding.sh — Enable IP forwarding on the Attacker
# Target Node: Attacker
# =============================================================================
# IP forwarding must be enabled so that intercepted packets are still delivered
# to their intended destination. Without this, the attack becomes a DoS instead
# of a man-in-the-middle — the victim loses connectivity entirely.
# =============================================================================

echo "[*] Enabling IP forwarding..."
echo 1 > /proc/sys/net/ipv4/ip_forward

# Verify
if [ "$(cat /proc/sys/net/ipv4/ip_forward)" = "1" ]; then
    echo "[+] IP forwarding is ENABLED."
    echo "[+] Intercepted packets will be forwarded to their real destination."
else
    echo "[-] ERROR: Failed to enable IP forwarding."
    exit 1
fi

# Install required tools
echo "[*] Installing attack tools (dsniff, tcpdump)..."
apt-get update -qq && apt-get install -y -qq dsniff tcpdump net-tools > /dev/null 2>&1
echo "[+] Tools installed: arpspoof, tcpdump"
