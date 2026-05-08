#!/bin/bash

# SIM_IP and SIM_PORT should be defined in the PLCs metadata
MAX_ATTEMPTS=5
ATTEMPT=1
SLEEP_TIME=2

echo "$SIM_IP:5555" > /opt/OpenPLC_v3/webserver/core/psm/SIM_NET_ADDR.txt
cat /opt/OpenPLC_v3/webserver/core/psm/SIM_NET_ADDR.txt >> $START_LOG 2>&1

# Loop until port is open or attempts exceed 10
# 'nc -z' scans without sending data, '-w 1' sets a 1s timeout
while ! nc -z -w 1 "$SIM_IP" "$SIM_PORT"; do
    echo "Attempt $ATTEMPT/$MAX_ATTEMPTS: Port $SIM_PORT is closed."
    
    if [ "$ATTEMPT" -gt "$MAX_ATTEMPTS" ]; then
        echo "Failed to connect to $SIM_IP:$SIM_PORT after $MAX_ATTEMPTS attempts."
        exit 1
    fi
    
    ATTEMPT=$((ATTEMPT+1))
    sleep $SLEEP_TIME
done 

/opt/OpenPLC_v3/start_openplc.sh &
/usr/sbin/sshd &

tail -f /dev/null