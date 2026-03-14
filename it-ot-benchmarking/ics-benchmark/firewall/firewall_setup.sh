#!/bin/bash
# Firewall/Router Setup — 3 interfaces: IT, DMZ, OT
#
# Usage: /app/firewall_setup.sh
#
# Defaults (override with env vars):
#   IT_IFACE=eth0  IT_IP=192.168.1.1/24
#   DMZ_IFACE=eth1 DMZ_IP=172.16.0.1/24
#   OT_IFACE=eth2  OT_IP=10.0.0.1/16

set -e

IT_IFACE=${IT_IFACE:-eth0}
DMZ_IFACE=${DMZ_IFACE:-eth1}
OT_IFACE=${OT_IFACE:-eth2}
IT_IP=${IT_IP:-192.168.1.1/24}
DMZ_IP=${DMZ_IP:-172.16.0.1/24}
OT_IP=${OT_IP:-10.0.0.1/16}

echo "=== Firewall Setup ==="
echo "  IT:  $IT_IFACE ($IT_IP)"
echo "  DMZ: $DMZ_IFACE ($DMZ_IP)"
echo "  OT:  $OT_IFACE ($OT_IP)"

# Assign IPs
for iface in $IT_IFACE $DMZ_IFACE $OT_IFACE; do
    ip addr flush dev $iface 2>/dev/null || true
    ip link set $iface up
done

ip addr add $IT_IP dev $IT_IFACE
ip addr add $DMZ_IP dev $DMZ_IFACE
ip addr add $OT_IP dev $OT_IFACE

# Enable forwarding
sysctl -w net.ipv4.ip_forward=1

# Accept all forwarding
iptables -F
iptables -t nat -F
iptables -P FORWARD ACCEPT

echo "=== Firewall Ready ==="
