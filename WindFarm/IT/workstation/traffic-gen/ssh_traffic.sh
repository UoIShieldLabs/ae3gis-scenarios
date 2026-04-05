#!/bin/bash
# ============================================================
# SSH Traffic Generator (IT Workstations Only)
# ============================================================
# Env vars:
#   SSH_TARGETS : Comma-separated IPs to SSH into (required)
#   INTERVAL    : Base interval in seconds (default: 45)
#   SSH_USER    : SSH username (default: admin)
#   SSH_PASS    : SSH password (default: password)
# ============================================================

SSH_TARGETS="${SSH_TARGETS:?SSH_TARGETS must be set}"
INTERVAL="${INTERVAL:-45}"
SSH_USER="${SSH_USER:-admin}"
SSH_PASS="${SSH_PASS:-password}"

IFS=',' read -ra TARGET_LIST <<< "$SSH_TARGETS"

COMMANDS=(
    "uptime"
    "df -h"
    "free -m"
    "ps aux --sort=-%mem | head -5"
    "ls -la /var/log/"
    "whoami"
    "date"
    "cat /etc/hostname"
    "netstat -tlnp 2>/dev/null || ss -tlnp"
    "cat /etc/os-release | head -3"
    "w"
    "last -5 2>/dev/null || echo 'no login records'"
)

echo "[SSH] Starting: targets=${SSH_TARGETS} interval=${INTERVAL}s"

while true; do
    TARGET="${TARGET_LIST[$((RANDOM % ${#TARGET_LIST[@]}))]}"
    CMD="${COMMANDS[$((RANDOM % ${#COMMANDS[@]}))]}"

    sshpass -p "$SSH_PASS" ssh \
        -o StrictHostKeyChecking=no \
        -o UserKnownHostsFile=/dev/null \
        -o ConnectTimeout=5 \
        -o LogLevel=ERROR \
        "${SSH_USER}@${TARGET}" "$CMD" > /dev/null 2>&1

    # Jitter: ±30%
    JITTER=$(( RANDOM % (INTERVAL * 6 / 10 + 1) - INTERVAL * 3 / 10 ))
    SLEEP=$(( INTERVAL + JITTER ))
    [ "$SLEEP" -lt 2 ] && SLEEP=2
    sleep "$SLEEP"
done
