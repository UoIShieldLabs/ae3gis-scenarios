#!/bin/bash
set -e

# ============================================================
# AE3GIS Database Server Entrypoint
# ============================================================

# Start SSH
echo "[entrypoint] Starting SSH server..."
/usr/sbin/sshd

# Initialize MySQL data directory if needed
if [ ! -d /var/lib/mysql/mysql ]; then
    echo "[entrypoint] Initializing MySQL data directory..."
    mysqld --initialize-insecure --user=mysql
fi

# Start MySQL in background
echo "[entrypoint] Starting MySQL..."
mkdir -p /var/run/mysqld
chown mysql:mysql /var/run/mysqld
mysqld --user=mysql &

# Wait for MySQL to be ready
echo "[entrypoint] Waiting for MySQL to start..."
MAX_RETRIES=30
RETRY=0
while [ $RETRY -lt $MAX_RETRIES ]; do
    if mysqladmin ping --silent 2>/dev/null; then
        echo "[entrypoint] MySQL is ready."
        break
    fi
    RETRY=$((RETRY + 1))
    sleep 2
done

if [ $RETRY -eq $MAX_RETRIES ]; then
    echo "[entrypoint] ERROR: MySQL did not start in time."
    exit 1
fi

# Run init script if database doesn't exist yet
if ! mysql -e "USE corp_data" 2>/dev/null; then
    echo "[entrypoint] Running init.sql..."
    mysql < /opt/init.sql
    echo "[entrypoint] Database initialized."
else
    echo "[entrypoint] Database already exists, skipping init."
fi

echo "[entrypoint] Database server ready."
exec tail -f /dev/null
