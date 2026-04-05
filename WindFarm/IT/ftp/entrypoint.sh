#!/bin/bash
set -e

# Start SSH
echo "[entrypoint] Starting SSH server..."
/usr/sbin/sshd

# Ensure FTP directories exist
mkdir -p /var/run/vsftpd/empty
mkdir -p /home/admin/uploads
chown admin:admin /home/admin/uploads

# Start vsftpd in foreground
echo "[entrypoint] Starting vsftpd..."
exec vsftpd /etc/vsftpd.conf
