#!/bin/bash
# =============================================================================
# detect_attack.sh — Detect DoS attacks on the server
# Target Node: IT-Server
# =============================================================================
# Run this on the SERVER while an attack is in progress.
# It checks for common DoS indicators.
# =============================================================================

echo "============================================================"
echo "  DoS ATTACK DETECTION REPORT"
echo "============================================================"
echo ""

# 1. Check half-open (SYN_RECV) connections — indicator of SYN flood
echo "--- SYN_RECV Connections (SYN Flood Indicator) ---"
SYN_COUNT=$(netstat -an 2>/dev/null | grep -c SYN_RECV || ss -tn state syn-recv 2>/dev/null | tail -n +2 | wc -l)
echo "  Half-open connections: $SYN_COUNT"
if [ "$SYN_COUNT" -gt 10 ]; then
    echo "  ⚠️  WARNING: High number of SYN_RECV connections — possible SYN flood!"
else
    echo "  ✅ Normal range."
fi
echo ""

# 2. Check total established connections
echo "--- Established Connections ---"
ESTABLISHED=$(netstat -an 2>/dev/null | grep -c ESTABLISHED || ss -tn state established 2>/dev/null | tail -n +2 | wc -l)
echo "  Established connections: $ESTABLISHED"
echo ""

# 3. Count connections per source IP
echo "--- Top Source IPs (by connection count) ---"
netstat -an 2>/dev/null | grep ':80' | awk '{print $5}' | cut -d: -f1 | sort | uniq -c | sort -rn | head -10 || \
ss -tn 2>/dev/null | grep ':80' | awk '{print $5}' | rev | cut -d: -f2- | rev | sort | uniq -c | sort -rn | head -10
echo ""

# 4. Live packet rate (10-second sample)
echo "--- Packet Rate (10-second sample) ---"
echo "  Counting incoming packets for 10 seconds..."
PACKET_COUNT=$(timeout 10 tcpdump -i eth0 -c 99999 2>/dev/null | wc -l)
RATE=$((PACKET_COUNT / 10))
echo "  Packets received: $PACKET_COUNT in 10s ($RATE packets/sec)"
if [ "$RATE" -gt 100 ]; then
    echo "  ⚠️  WARNING: High packet rate — possible flood attack!"
else
    echo "  ✅ Normal packet rate."
fi
echo ""

echo "============================================================"
echo "  Detection complete. Review results above."
echo "============================================================"
