#!/bin/bash
set -e

# ============================================================
# AE3GIS Webserver Entrypoint
# ============================================================
# Env vars:
#   SERVER_NAME     : Display name (default: "AE3GIS Web Server")
#   DB_SERVER       : Database server IP (default: 10.10.5.22)
#   DB_USER         : Database user (default: webapp)
#   DB_PASS         : Database password (default: webapp_pass)
#   DB_NAME         : Database name (default: corp_data)
#   SQL_INTERVAL    : SQL traffic interval (default: 10)
#   SQL_ENABLED     : Set to "false" to disable SQL traffic
#   TRAFFIC_ENABLED : Set to "false" to disable all traffic
# ============================================================

DB_SERVER="${DB_SERVER:-10.10.5.22}"
SQL_ENABLED="${SQL_ENABLED:-true}"
TRAFFIC_ENABLED="${TRAFFIC_ENABLED:-true}"

# Start SSH
echo "[entrypoint] Starting SSH server..."
/usr/sbin/sshd

# Start Nginx
echo "[entrypoint] Starting Nginx..."
nginx

# Start SQL traffic if enabled
if [ "$TRAFFIC_ENABLED" = "true" ] && [ "$SQL_ENABLED" = "true" ]; then
    echo "[entrypoint] Waiting 20s for database to initialize..."
    sleep 20
    echo "[entrypoint] Starting SQL traffic to $DB_SERVER..."
    DB_SERVER="$DB_SERVER" \
    DB_USER="${DB_USER:-webapp}" \
    DB_PASS="${DB_PASS:-webapp_pass}" \
    DB_NAME="${DB_NAME:-corp_data}" \
    INTERVAL="${SQL_INTERVAL:-10}" \
    /opt/traffic-gen/sql_traffic.sh &
fi

echo "[entrypoint] Webserver ready."
exec tail -f /dev/null
