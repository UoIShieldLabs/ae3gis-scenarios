#!/bin/bash
# ============================================================
# FTP Traffic Generator
# ============================================================
# Env vars:
#   FTP_TARGET : IP of FTP server (required)
#   INTERVAL   : Base interval in seconds (default: 20)
#   FTP_USER   : FTP username (default: admin)
#   FTP_PASS   : FTP password (default: password)
# ============================================================

FTP_TARGET="${FTP_TARGET:?FTP_TARGET must be set}"
INTERVAL="${INTERVAL:-20}"
FTP_USER="${FTP_USER:-admin}"
FTP_PASS="${FTP_PASS:-password}"

# Create dummy files of varying sizes for uploads
mkdir -p /tmp/ftp_data
for i in $(seq 1 5); do
    dd if=/dev/urandom of="/tmp/ftp_data/report_${i}.dat" bs=1K count=$((RANDOM % 50 + 5)) 2>/dev/null
done

echo "[FTP] Starting: target=$FTP_TARGET interval=${INTERVAL}s"

while true; do
    FILE="/tmp/ftp_data/report_$((RANDOM % 5 + 1)).dat"

    # Alternate between upload, download (list), and get
    ACTION=$((RANDOM % 3))
    case $ACTION in
        0)
            # Upload a file
            curl -s --max-time 10 \
                -T "$FILE" \
                "ftp://${FTP_TARGET}/uploads/" \
                --user "${FTP_USER}:${FTP_PASS}" > /dev/null 2>&1
            ;;
        1)
            # List directory
            curl -s --max-time 10 \
                "ftp://${FTP_TARGET}/uploads/" \
                --user "${FTP_USER}:${FTP_PASS}" > /dev/null 2>&1
            ;;
        2)
            # Download attempt (may fail if file doesn't exist, that's fine)
            curl -s --max-time 10 -o /dev/null \
                "ftp://${FTP_TARGET}/uploads/report_$((RANDOM % 5 + 1)).dat" \
                --user "${FTP_USER}:${FTP_PASS}" 2>/dev/null
            ;;
    esac

    # Jitter: ±30%
    JITTER=$(( RANDOM % (INTERVAL * 6 / 10 + 1) - INTERVAL * 3 / 10 ))
    SLEEP=$(( INTERVAL + JITTER ))
    [ "$SLEEP" -lt 2 ] && SLEEP=2
    sleep "$SLEEP"
done
