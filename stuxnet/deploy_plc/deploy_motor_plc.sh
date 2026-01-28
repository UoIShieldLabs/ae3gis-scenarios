#!/bin/bash

# PLC_URL="172.16.101.10:8080"
PLC_URL=$1
PLC_USERNAME="openplc"
PLC_PASSWORD="openplc"
COOKIE_JAR="plc_cookie.txt"
MOTOR_ST_FILE="motor.st"
MOTOR_PSM_FILE="motor_psm.py"
MOTOR_PROGRAM_NAME="motor_test"


# Login and get session cookie
echo "Login..."
curl -c "$COOKIE_JAR" \
     -X POST "$PLC_URL/login" \
     -d "username=$PLC_USERNAME&password=$PLC_PASSWORD" > /dev/null

# ========================= # 
# Enable PSM hardware layer #
# ========================= #
echo "Change HW Layer..."
curl -b "$COOKIE_JAR" \
        -X POST "$PLC_URL/hardware" \
        -F "hardware_layer=psm_linux" \
        -F "custom_layer_code=<$MOTOR_PSM_FILE" > /dev/null

# ========================== # 
# Upload and compile ST file #
# ========================== #
echo "Upload File..."
UPLOAD_RESPONSE=$(curl -b "$COOKIE_JAR" -X POST "$PLC_URL/upload-program"  -F "file=@$MOTOR_ST_FILE" -F "name=$MOTOR_PROGRAM_NAME")
UPLOAD_REGEX=".*input type='hidden' value='([0-9]*.st)'.*<input type='hidden' value='([0-9]*)' id='epoch.*"
if [[ "$UPLOAD_RESPONSE" =~ $UPLOAD_REGEX ]]; then
    MATCH_FILE="${BASH_REMATCH[1]}"
    MATCH_TIME="${BASH_REMATCH[2]}"
else
    echo "PATTERN not found"
fi

echo "Upload File Action..."
curl -b "$COOKIE_JAR" \
        -X POST "$PLC_URL/upload-program-action" \
        -F "prog_name=$MOTOR_PROGRAM_NAME" \
        -F "prog_descr=''" \
        -F "prog_file=$MATCH_FILE" \
        -F "epoch_time=$MATCH_TIME" \ > /dev/null

echo "Compile..."
curl -b "$COOKIE_JAR" \
     -X GET "$PLC_URL/compile-program?file=$MATCH_FILE" > /dev/null

COMPILE_LOGS=""
COMPILE_REGEX=".*Compilation finished"
while ! [[ "$COMPILE_LOGS" =~ $COMPILE_REGEX ]]; do
    COMPILE_LOGS=$(curl -s -b $COOKIE_JAR "http://$PLC_URL/compilation-logs")
    #echo $COMPILE_LOGS
done

echo "Start..."
curl -b "$COOKIE_JAR" \
        -X GET "$PLC_URL/start_plc" > /dev/null
# echo $UPLOAD_RESPONSE