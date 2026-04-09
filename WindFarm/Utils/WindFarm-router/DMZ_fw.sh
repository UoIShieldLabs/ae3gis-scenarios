#!/bin/bash

############################################
# VARIABLES 
############################################

# WEB_1:  IP ADDR of Webserver_1
# WEB_2:  IP ADDR of Webserver_1
# DNS:    IP ADDR of DNS server
# FTP:    IP ADDR of Fileserver
# DB:     IP ADDR of Database server

# IT_NET: IT Subnet (i.e. 10.10.5.0/24)
# DMZ_NET: DMZ Network
# CORE_NET: Core Network

############################################
# BASE RULES
############################################

# Loopback
iptables -A INPUT -i lo -j ACCEPT

# Stateful
iptables -A FORWARD -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

############################################
# DMZ RULES
############################################

# Public services
for HOST in $WEB_1 $WEB_2; do
    iptables -A FORWARD -p tcp -d $HOST --dport 80 -j ACCEPT
    iptables -A FORWARD -p udp -d $HOST --dport 80 -j ACCEPT
done

iptables -A FORWARD -p tcp -d $DNS --dport 53 -j ACCEPT
iptables -A FORWARD -p udp -d $DNS --dport 53 -j ACCEPT

iptables -A FORWARD -p tcp -d $FTP --dport 21 -j ACCEPT
iptables -A FORWARD -p udp -d $FTP --dport 21 -j ACCEPT

# IT -> DMZ SSH
iptables -A FORWARD -s $IT_NET -d $DMZ_NET -p tcp --dport 22 -j ACCEPT

# Webservers -> DB
for HOST in $WEB_1 $WEB_2; do
    iptables -A FORWARD -s $HOST -d $DB -p tcp --dport 3306 -j ACCEPT
done

# ICMP from Core
iptables -A FORWARD -s $CORE_NET -d $DMZ_NET -p icmp -j ACCEPT

# Allow Core -> External
iptables -A FORWARD -s $CORE_NET ! -d $DMZ_NET -j ACCEPT

# DEFAULT DENY
iptables -A FORWARD -j DROP