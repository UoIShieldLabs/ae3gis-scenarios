#!/bin/bash
set -e

# ============================================================
# AE3GIS DNS Server Entrypoint
# ============================================================
# Env vars (all optional, override dnsmasq.conf defaults):
#   WEBSERVER_1  : IP for webserver1.corp.local  (default: 10.10.1.10)
#   WEBSERVER_2  : IP for webserver2.corp.local  (default: 10.10.1.11)
#   DNS_SELF     : IP for dns.corp.local         (default: 10.10.1.12)
#   EXTERNAL_FTP : IP for ftp-ext.corp.local     (default: 10.10.1.13)
#   INTERNAL_WEB : IP for internal-web.corp.local(default: 10.10.5.20)
#   INTERNAL_FTP : IP for internal-ftp.corp.local(default: 10.10.5.21)
#   DB_SERVER    : IP for db.corp.local          (default: 10.10.5.22)
# ============================================================

# If env vars are set, generate a dynamic config that overrides defaults
if [ -n "$WEBSERVER_1" ] || [ -n "$WEBSERVER_2" ]; then
    cat > /etc/dnsmasq.d/dynamic.conf << EOF
address=/webserver1.corp.local/${WEBSERVER_1:-10.10.1.10}
address=/webserver2.corp.local/${WEBSERVER_2:-10.10.1.11}
address=/dns.corp.local/${DNS_SELF:-10.10.1.12}
address=/ftp-ext.corp.local/${EXTERNAL_FTP:-10.10.1.13}
address=/internal-web.corp.local/${INTERNAL_WEB:-10.10.5.20}
address=/internal-ftp.corp.local/${INTERNAL_FTP:-10.10.5.21}
address=/db.corp.local/${DB_SERVER:-10.10.5.22}
EOF
    echo "[entrypoint] Generated dynamic DNS config from env vars."
fi

# Disable systemd-resolved if present (conflicts with dnsmasq on port 53)
if [ -f /etc/resolv.conf ]; then
    # Point local resolution at ourselves
    echo "nameserver 127.0.0.1" > /etc/resolv.conf
fi

# Start SSH
echo "[entrypoint] Starting SSH server..."
/usr/sbin/sshd

# Start dnsmasq in foreground
echo "[entrypoint] Starting dnsmasq..."
exec dnsmasq --no-daemon --log-queries
