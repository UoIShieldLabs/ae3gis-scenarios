#!/bin/bash
# ============================================================
# DNS Traffic Generator
# ============================================================
# Env vars:
#   DNS_SERVER : IP of DNS server (required)
#   INTERVAL   : Base interval in seconds (default: 45)
# ============================================================

DNS_SERVER="${DNS_SERVER:?DNS_SERVER must be set}"
INTERVAL="${INTERVAL:-45}"

DOMAINS=(
    "webserver1.corp.local"
    "webserver2.corp.local"
    "internal-web.corp.local"
    "ftp-ext.corp.local"
    "internal-ftp.corp.local"
    "db.corp.local"
    "google.com"
    "github.com"
    "stackoverflow.com"
    "microsoft.com"
    "reddit.com"
    "amazon.com"
)

echo "[DNS] Starting: server=$DNS_SERVER interval=${INTERVAL}s"

while true; do
    DOMAIN="${DOMAINS[$((RANDOM % ${#DOMAINS[@]}))]}"
    dig @"$DNS_SERVER" "$DOMAIN" +short +timeout=3 > /dev/null 2>&1

    # Jitter: ±30%
    JITTER=$(( RANDOM % (INTERVAL * 6 / 10 + 1) - INTERVAL * 3 / 10 ))
    SLEEP=$(( INTERVAL + JITTER ))
    [ "$SLEEP" -lt 2 ] && SLEEP=2
    sleep "$SLEEP"
done
