#!/bin/bash
set -e

# ============================================================
# AE3GIS Zeek Network Monitor Entrypoint
# ============================================================
# Env vars:
#   ZEEK_INTERFACE : Network interface to capture on (default: eth0)
#   ZEEK_LOGDIR    : Log output directory (default: /opt/zeek/logs/current)
# ============================================================

ZEEK_INTERFACE="${ZEEK_INTERFACE:-eth0}"
ZEEK_LOGDIR="${ZEEK_LOGDIR:-/opt/zeek/logs/current}"

# Start SSH
echo "[entrypoint] Starting SSH server..."
/usr/sbin/sshd

# Wait for interface to be ready
echo "[entrypoint] Waiting for interface $ZEEK_INTERFACE..."
RETRIES=0
while [ $RETRIES -lt 30 ]; do
    if ip link show "$ZEEK_INTERFACE" > /dev/null 2>&1; then
        echo "[entrypoint] Interface $ZEEK_INTERFACE is ready."
        break
    fi
    RETRIES=$((RETRIES + 1))
    sleep 2
done

# Enable promiscuous mode on the interface
echo "[entrypoint] Setting $ZEEK_INTERFACE to promiscuous mode..."
ip link set "$ZEEK_INTERFACE" promisc on 2>/dev/null || \
    echo "[entrypoint] WARNING: Could not set promiscuous mode (may need NET_ADMIN capability)."

# Create log directory
mkdir -p "$ZEEK_LOGDIR"
cd "$ZEEK_LOGDIR"

# Start Zeek
echo "[entrypoint] Starting Zeek on interface $ZEEK_INTERFACE..."
echo "[entrypoint] Logs will be written to $ZEEK_LOGDIR"

# Run Zeek in foreground
exec zeek -i "$ZEEK_INTERFACE" /opt/zeek/share/zeek/site/local.zeek
