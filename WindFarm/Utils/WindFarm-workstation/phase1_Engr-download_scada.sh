#!/bin/bash

FTP_SERVER="${FTP_SERVER:-172.16.20.13}"
FTP_USER="admin"
FTP_PASS="password"

LISTEN_FILE="init_scada_project.tar.gz"
LOCAL_COPY="/home/init_scada_project.tar.gz"

echo "SSHPASS=\"mypassword\"" >> /etc/environment

# Poll for results file
while true; do
    curl -s --list-only ftp://$FTP_USER:$FTP_PASS@$FTP_SERVER/uploads/ | grep -q "$LISTEN_FILE"

    if [ $? -eq 0 ]; then
        echo "[+] Results found, downloading..."
        curl -s -o "$LOCAL_COPY" ftp://$FTP_USER:$FTP_PASS@$FTP_SERVER/uploads/$LISTEN_FILE
        break
    fi

    sleep 1
done
