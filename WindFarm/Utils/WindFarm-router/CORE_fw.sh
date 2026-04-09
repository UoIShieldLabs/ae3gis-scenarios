#!/bin/bash

############################################
# VARIABLES
############################################

# WEB_1:  IP ADDR of Webserver_1
# WEB_2:  IP ADDR of Webserver_1
# DB:     IP ADDR of Database server

# CORE_NET:   Core Network
# ENGR_NET:   Engineering Subnet
# OT_DMZ_NET: OT DMZ Network

############################################
# BASE RULES
############################################

iptables -A INPUT -i lo -j ACCEPT
iptables -A FORWARD -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

############################################
# CORE RULES
############################################

# Block DB access
iptables -A FORWARD -s $CORE_NET -d $DB -j DROP

# Only Engineering can SSH to OT_DMZ
iptables -A FORWARD ! -s $ENGR_NET -d $OT_DMZ_NET -j DROP

# Web -> DB (allow exceptions BEFORE deny)
for HOST in $WEB_1 $WEB_2; do
    iptables -A FORWARD -s $HOST -d $DB -p tcp --dport 3306 -j ACCEPT
done

# Allow internal traffic
iptables -A FORWARD -s $CORE_NET -j ACCEPT

############################################
# DEFAULT DENY
############################################

iptables -A FORWARD -j DROP