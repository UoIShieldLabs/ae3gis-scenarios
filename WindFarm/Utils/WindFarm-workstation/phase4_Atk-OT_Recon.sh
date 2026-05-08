#!/bin/bash

JB_LOG="/home/jumpbox.log"
TARGET="10.10.6.3"
SSH_PASSWD="mypassword"
SSH_RTR_PASSWD="root"
OT_SUBNET="10.0.0.0/24"
## SIMULATOR should be defined in the metadata of attacker container
OT_PORT_LIST="22,80,8080,502,102,20000,4840,44818,34980"

JB_RTR_CMD="sshpass -p $SSH_RTR_PASSWD ssh -o StrictHostKeyChecking=no 10.10.6.1 \"ip route show\""
echo "$START$JB_RTR_CMD$END" | ncat -l 4040 >> $JB_LOG

OT_NMAP="nmap -p $OT_PORT_LIST -n -sV --open --exclude \"$SIMULATOR\" -sS -T4 $OT_SUBNET &"
echo "$START$OT_NMAP$END" | ncat -l 4040 >> $JB_LOG &