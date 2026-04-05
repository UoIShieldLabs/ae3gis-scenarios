#!/bin/bash
set -e

# ============================================================
# AE3GIS Workstation Entrypoint
# ============================================================
# Configure via environment variables:
#   ROLE              : hr | marketing | engineering | it
#   DNS_SERVER        : IP of DNS server         (default: 10.10.1.12)
#   WEBSERVER_1       : IP of external webserver  (default: 10.10.1.10)
#   WEBSERVER_2       : IP of external webserver  (default: 10.10.1.11)
#   INTERNAL_WEB      : IP of internal webserver  (default: 10.10.5.20)
#   INTERNAL_FTP      : IP of internal FTP server (default: 10.10.5.21)
#   EXTERNAL_FTP      : IP of external FTP server (default: 10.10.1.13)
#   DB_SERVER         : IP of database server     (default: 10.10.5.22)
#   SSH_TARGETS       : Comma-separated IPs for SSH traffic (IT only)
#   TRAFFIC_ENABLED   : Set to "false" to disable traffic gen
# ============================================================

# -- Defaults --
ROLE="${ROLE:-hr}"
DNS_SERVER="${DNS_SERVER:-10.10.1.12}"
WEBSERVER_1="${WEBSERVER_1:-10.10.1.10}"
WEBSERVER_2="${WEBSERVER_2:-10.10.1.11}"
INTERNAL_WEB="${INTERNAL_WEB:-10.10.5.20}"
INTERNAL_FTP="${INTERNAL_FTP:-10.10.5.21}"
EXTERNAL_FTP="${EXTERNAL_FTP:-10.10.1.13}"
DB_SERVER="${DB_SERVER:-10.10.5.22}"
TRAFFIC_ENABLED="${TRAFFIC_ENABLED:-true}"

# Start SSH daemon
echo "[entrypoint] Starting SSH server..."
/usr/sbin/sshd

echo "[entrypoint] Role: $ROLE"

if [ "$TRAFFIC_ENABLED" = "false" ]; then
    echo "[entrypoint] Traffic generation disabled."
    exec tail -f /dev/null
fi

# Wait for network to settle before generating traffic
echo "[entrypoint] Waiting 15s for network to stabilize..."
sleep 15

echo "[entrypoint] Starting traffic generation..."

# ---- Traffic by role ----
# Volume mapping: Low=45s, Medium=20s, High=10s

case "$ROLE" in

  hr)
    # DNS -> DNS Server (Low)
    DNS_SERVER="$DNS_SERVER" INTERVAL=45 /opt/traffic-gen/dns_traffic.sh &

    # HTTP -> External webservers (Low)
    TARGETS="${WEBSERVER_1},${WEBSERVER_2}" INTERVAL=45 /opt/traffic-gen/http_traffic.sh &

    # HTTP -> Internal web server (Medium)
    TARGETS="${INTERNAL_WEB}" INTERVAL=20 /opt/traffic-gen/http_traffic.sh &

    # FTP -> Internal file server (High)
    FTP_TARGET="$INTERNAL_FTP" INTERVAL=10 /opt/traffic-gen/ftp_traffic.sh &
    ;;

  marketing)
    # DNS -> DNS Server (Low)
    DNS_SERVER="$DNS_SERVER" INTERVAL=45 /opt/traffic-gen/dns_traffic.sh &

    # HTTP -> External webservers (High)
    TARGETS="${WEBSERVER_1},${WEBSERVER_2}" INTERVAL=10 /opt/traffic-gen/http_traffic.sh &

    # HTTP -> Internal web server (Medium)
    TARGETS="${INTERNAL_WEB}" INTERVAL=20 /opt/traffic-gen/http_traffic.sh &

    # FTP -> Internal file server (Medium)
    FTP_TARGET="$INTERNAL_FTP" INTERVAL=20 /opt/traffic-gen/ftp_traffic.sh &
    ;;

  engineering)
    # DNS -> DNS Server (Low)
    DNS_SERVER="$DNS_SERVER" INTERVAL=45 /opt/traffic-gen/dns_traffic.sh &

    # HTTP -> External webservers (Low)
    TARGETS="${WEBSERVER_1},${WEBSERVER_2}" INTERVAL=45 /opt/traffic-gen/http_traffic.sh &

    # HTTP -> Internal web server (Medium)
    TARGETS="${INTERNAL_WEB}" INTERVAL=20 /opt/traffic-gen/http_traffic.sh &

    # FTP -> Internal file server (Low)
    FTP_TARGET="$INTERNAL_FTP" INTERVAL=45 /opt/traffic-gen/ftp_traffic.sh &

    # FTP -> External file server (Medium)
    FTP_TARGET="$EXTERNAL_FTP" INTERVAL=20 /opt/traffic-gen/ftp_traffic.sh &
    ;;

  it)
    # DNS -> DNS Server (Low)
    DNS_SERVER="$DNS_SERVER" INTERVAL=45 /opt/traffic-gen/dns_traffic.sh &

    # HTTP -> External webservers (Low)
    TARGETS="${WEBSERVER_1},${WEBSERVER_2}" INTERVAL=45 /opt/traffic-gen/http_traffic.sh &

    # HTTP -> Internal web server (Medium)
    TARGETS="${INTERNAL_WEB}" INTERVAL=20 /opt/traffic-gen/http_traffic.sh &

    # FTP -> Internal file server (Medium)
    FTP_TARGET="$INTERNAL_FTP" INTERVAL=20 /opt/traffic-gen/ftp_traffic.sh &

    # SSH -> Various servers (Low)
    SSH_TARGETS="${SSH_TARGETS:-${WEBSERVER_1},${WEBSERVER_2},${DNS_SERVER},${EXTERNAL_FTP},${INTERNAL_WEB},${INTERNAL_FTP},${DB_SERVER}}"
    SSH_TARGETS="$SSH_TARGETS" INTERVAL=45 /opt/traffic-gen/ssh_traffic.sh &
    ;;

  *)
    echo "[entrypoint] WARNING: Unknown ROLE '$ROLE'. No traffic will be generated."
    ;;
esac

echo "[entrypoint] All traffic generators launched for role: $ROLE"

# Keep container alive
exec tail -f /dev/null
