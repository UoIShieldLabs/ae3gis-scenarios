#!/bin/bash
# ============================================================
# HTTP Traffic Generator
# ============================================================
# Env vars:
#   TARGETS  : Comma-separated IPs of web servers (required)
#   INTERVAL : Base interval in seconds (default: 20)
# ============================================================

TARGETS="${TARGETS:?TARGETS must be set}"
INTERVAL="${INTERVAL:-20}"

IFS=',' read -ra TARGET_LIST <<< "$TARGETS"

PATHS=("/" "/index.html" "/about" "/contact" "/status" "/login" "/dashboard" "/api/health" "/news" "/products")
USER_AGENTS=(
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    "Mozilla/5.0 (X11; Linux x86_64)"
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    "curl/7.81.0"
)

echo "[HTTP] Starting: targets=${TARGETS} interval=${INTERVAL}s"

while true; do
    TARGET="${TARGET_LIST[$((RANDOM % ${#TARGET_LIST[@]}))]}"
    URL_PATH="${PATHS[$((RANDOM % ${#PATHS[@]}))]}"
    UA="${USER_AGENTS[$((RANDOM % ${#USER_AGENTS[@]}))]}"

    curl -s -o /dev/null --max-time 5 \
        -H "User-Agent: $UA" \
        "http://${TARGET}${URL_PATH}" 2>/dev/null

    # Jitter: ±30%
    JITTER=$(( RANDOM % (INTERVAL * 6 / 10 + 1) - INTERVAL * 3 / 10 ))
    SLEEP=$(( INTERVAL + JITTER ))
    [ "$SLEEP" -lt 2 ] && SLEEP=2
    sleep "$SLEEP"
done
