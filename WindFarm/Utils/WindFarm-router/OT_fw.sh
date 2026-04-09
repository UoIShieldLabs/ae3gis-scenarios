#!/bin/bash

############################################
# VARIABLES
############################################

# OT_JUMP:  IP Address for OT Jumpbox
# OT_NET:   OT Network

############################################
# BASE RULES
############################################

iptables -A INPUT -i lo -j ACCEPT
iptables -A FORWARD -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

############################################
# OT RULES
############################################

# Jump host access
for PORT in 8080 502 22; do
    iptables -A FORWARD -s $OT_JUMP -d $OT_NET -p tcp --dport $PORT -j ACCEPT
    iptables -A FORWARD -s $OT_JUMP -d $OT_NET -p udp --dport $PORT -j ACCEPT
done

# ICMP
iptables -A FORWARD -s $OT_JUMP -d $OT_NET -p icmp -j ACCEPT

############################################
# DEFAULT DENY
############################################

iptables -A FORWARD -j DROP