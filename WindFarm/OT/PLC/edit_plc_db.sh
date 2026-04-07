#!/bin/bash
PROG_NAME=$1
PROG_DESC=$2
PROG_FILE=$3

echo $PROG_NAME
echo $PROG_DESC
echo $PROG_FILE

SQL_ADD_SCRIPT_PROG="INSERT INTO Programs (Name, Description, File, Date_upload) VALUES ('$PROG_NAME','$PROG_DESC','$PROG_FILE', strftime('%s', 'now'));"

sqlite3 /opt/OpenPLC_v3/webserver/openplc.db "$SQL_ADD_SCRIPT_PROG"

