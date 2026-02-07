#!/bin/bash
# =============================================================================
# mitigate_rate_limit.sh — Apply iptables rate-limiting rules
# Target Node: IT-Server
# =============================================================================
# Applies kernel-level and firewall-based mitigations against DoS attacks.
# Run this on the SERVER to protect against active floods.
# =============================================================================

echo "============================================================"
echo "  APPLYING DoS MITIGATIONS"
echo "============================================================"
echo ""

# --- SYN Cookies ---
echo "[1/4] Enabling SYN cookies (kernel-level SYN flood defense)..."
echo 1 > /proc/sys/net/ipv4/tcp_syncookies
echo "      SYN cookies: ENABLED"
echo ""

# --- SYN Rate Limiting ---
echo "[2/4] Adding SYN rate limit (max 10/sec, burst 20)..."
iptables -A INPUT -p tcp --syn -m limit --limit 10/s --limit-burst 20 -j ACCEPT
iptables -A INPUT -p tcp --syn -j DROP
echo "      SYN rate limit: ACTIVE"
echo ""

# --- ICMP Rate Limiting ---
echo "[3/4] Adding ICMP rate limit (max 5/sec, burst 10)..."
iptables -A INPUT -p icmp -m limit --limit 5/s --limit-burst 10 -j ACCEPT
iptables -A INPUT -p icmp -j DROP
echo "      ICMP rate limit: ACTIVE"
echo ""

# --- UDP Rate Limiting ---
echo "[4/4] Adding UDP rate limit on port 80 (max 10/sec, burst 20)..."
iptables -A INPUT -p udp --dport 80 -m limit --limit 10/s --limit-burst 20 -j ACCEPT
iptables -A INPUT -p udp --dport 80 -j DROP
echo "      UDP rate limit: ACTIVE"
echo ""

echo "============================================================"
echo "  All mitigations applied. Current iptables rules:"
echo "============================================================"
iptables -L -n -v
echo ""
echo "[+] The server should now be resilient against flood attacks."
echo "[+] Legitimate traffic at normal rates will still pass through."
