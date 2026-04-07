#!/bin/bash

SUBNET=$1

SIM_IP=$(nmap --open -T4 -n --max-retries 0 -p 5555 $SUBNET -oG - | grep "5555/open" | awk '{print $2}')

echo "$SIM_IP:5555" > /opt/OpenPLC_v3/webserver/core/psm/SIM_NET_ADDR.txt