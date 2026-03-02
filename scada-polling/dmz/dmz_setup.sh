#!/bin/bash
# DMZ Router Setup
# Run this after the container starts in GNS3.
#
# Usage: /app/dmz_setup.sh
#
# Assumes:
#   eth0 = IT side (10.0.1.0/24)
#   eth1 = OT side (10.0.2.0/24)
#
# Adjust interface names if GNS3 assigns differently (check with `ip a`).

set -e

IT_IFACE=${IT_IFACE:-eth0}
OT_IFACE=${OT_IFACE:-eth1}
IT_IP=${IT_IP:-10.0.1.1/24}
OT_IP=${OT_IP:-10.0.2.1/24}

echo "=== DMZ Router Setup ==="
echo "  IT interface: $IT_IFACE ($IT_IP)"
echo "  OT interface: $OT_IFACE ($OT_IP)"

# Assign IPs
ip addr flush dev $IT_IFACE 2>/dev/null || true
ip addr flush dev $OT_IFACE 2>/dev/null || true
ip addr add $IT_IP dev $IT_IFACE
ip addr add $OT_IP dev $OT_IFACE
ip link set $IT_IFACE up
ip link set $OT_IFACE up

# Enable forwarding
sysctl -w net.ipv4.ip_forward=1

# Basic iptables — allow forwarding between subnets
iptables -F
iptables -t nat -F
iptables -P FORWARD ACCEPT
iptables -A FORWARD -i $IT_IFACE -o $OT_IFACE -j ACCEPT
iptables -A FORWARD -i $OT_IFACE -o $IT_IFACE -j ACCEPT

echo ""
echo "=== DMZ Router Ready ==="
echo "  Forwarding: enabled"
echo "  IT ($IT_IFACE) <-> OT ($OT_IFACE)"
echo ""
echo "Verify with: ping 10.0.1.10 (from OT side) or ping 10.0.2.11 (from IT side)"
