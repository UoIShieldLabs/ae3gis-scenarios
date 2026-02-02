#!/bin/bash

# Example Usage: ./deploy_hmi.sh "[HMI_IP_ADDRESS and PORT]/ScadaBR"
# NOTE: You may need to change the IP Address for the Modbus data point in motor_hmi.json. That value is currently hardcoded.

# HMI_URL="172.16.101.30:8080/ScadaBR"
HMI_URL=$1
HMI_USERNAME="admin"
HMI_PASSWORD="admin"
COOKIE_JAR="hmi_cookie.txt"
CONFIG_FILE="motor_hmi.json"

# Login and get session cookie
echo "Login..."
curl -c "$COOKIE_JAR" \
     -X POST "$HMI_URL/login.htm" \
     -d "username=$HMI_USERNAME&password=$HMI_PASSWORD"

# Get scriptSessionId Token
echo "Get DWR session token..."
DWR_ENGINE_RESPONSE=$(curl -b "$COOKIE_JAR" "$HMI_URL/dwr/engine.js")
DWR_ENGINE_REGEX='dwr\.engine\._origScriptSessionId = "([^"]*)";'
if [[ "$DWR_ENGINE_RESPONSE" =~ $DWR_ENGINE_REGEX ]]; then
    ORIG_TOKEN="${BASH_REMATCH[1]}"
else
    echo "PATTERN not found"
fi

# Append the random suffix to complete DWR scriptSessionId Token
RAND_SUFFIX=$(printf "%03d" $((RANDOM % 1000)))
SCRIPT_SESSION_ID="$ORIG_TOKEN$RAND_SUFFIX"


# URL Encode the JSON Config File and push to ScadaBR
echo "Encode config file and push config to ScadaBR..."
ENCODED_JSON=$(python3 -c "
import json, urllib.parse, sys
try:
    with open('$CONFIG_FILE','r') as f:
        data = json.load(f)
        minified = json.dumps(data, separators=(',', ':'))
        print(urllib.parse.quote(minified))
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)
")

if [[ $? -ne 0 ]]; then
    echo "Error: Python falied to process config file: $CONFIG_FILE"
    exit 1
fi

PAYLOAD="callCount=1
page=/ScadaBR/emport.shtm
httpSessionId=
scriptSessionId=$SCRIPT_SESSION_ID
c0-scriptName=EmportDwr
c0-methodName=importData
c0-id=0
c0-param0=string:$ENCODED_JSON"

curl -b $COOKIE_JAR \
     -X POST "$HMI_URL/dwr/call/plaincall/EmportDwr.importData.dwr" \
     --data-binary "$PAYLOAD" > /dev/null

  