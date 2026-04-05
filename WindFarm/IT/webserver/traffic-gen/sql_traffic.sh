#!/bin/bash
# ============================================================
# SQL Traffic Generator (Webservers -> Database)
# ============================================================
# Env vars:
#   DB_SERVER : Database IP (required)
#   DB_USER   : Database user (default: webapp)
#   DB_PASS   : Database password (default: webapp_pass)
#   DB_NAME   : Database name (default: corp_data)
#   INTERVAL  : Base interval in seconds (default: 10)
# ============================================================

DB_SERVER="${DB_SERVER:?DB_SERVER must be set}"
DB_USER="${DB_USER:-webapp}"
DB_PASS="${DB_PASS:-webapp_pass}"
DB_NAME="${DB_NAME:-corp_data}"
INTERVAL="${INTERVAL:-10}"

QUERIES=(
    "SELECT * FROM employees WHERE department='HR';"
    "SELECT COUNT(*) FROM employees;"
    "SELECT name, email FROM employees LIMIT 10;"
    "SELECT * FROM employees WHERE department='Engineering';"
    "SELECT department, COUNT(*) as cnt FROM employees GROUP BY department;"
    "SELECT * FROM employees WHERE department='Marketing';"
    "SELECT * FROM employees ORDER BY id DESC LIMIT 5;"
    "SELECT name FROM employees WHERE email LIKE '%corp.local';"
)

echo "[SQL] Starting: server=$DB_SERVER interval=${INTERVAL}s"

# Retry loop — wait for database to come up
MAX_RETRIES=30
RETRY=0
while [ $RETRY -lt $MAX_RETRIES ]; do
    if mysql -h "$DB_SERVER" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" \
        -e "SELECT 1;" > /dev/null 2>&1; then
        echo "[SQL] Database connection established."
        break
    fi
    RETRY=$((RETRY + 1))
    echo "[SQL] Waiting for database... (attempt $RETRY/$MAX_RETRIES)"
    sleep 5
done

if [ $RETRY -eq $MAX_RETRIES ]; then
    echo "[SQL] ERROR: Could not connect to database at $DB_SERVER after $MAX_RETRIES attempts."
    exit 1
fi

# Main loop
while true; do
    QUERY="${QUERIES[$((RANDOM % ${#QUERIES[@]}))]}"

    mysql -h "$DB_SERVER" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" \
        -e "$QUERY" > /dev/null 2>&1

    # Jitter: ±30%
    JITTER=$(( RANDOM % (INTERVAL * 6 / 10 + 1) - INTERVAL * 3 / 10 ))
    SLEEP=$(( INTERVAL + JITTER ))
    [ "$SLEEP" -lt 2 ] && SLEEP=2
    sleep "$SLEEP"
done
