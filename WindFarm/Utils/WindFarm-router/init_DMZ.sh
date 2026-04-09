#!/bin/bash

## $LAN_NW should be set in the device metadata for the DMZ router. 
## The value should be the subnet of the internal business network.

## $WAN_NW is the external network (DMZ) for the business. Knowing the LAN/WAN networks allows the DMZ to use NAT.

read LAN_IFACE <<< $(ip route show | awk -v foo="$LAN_NW" '$0 ~ foo {print $5}')
read WAN_IFACE <<< $(ip route show | awk -v foo="$WAN_NW" '$0 ~ foo {print $5}')

iptables -t nat -A POSTROUTING -o $WAN_IFACE -j MASQUERADE
iptables -A FORWARD -i $WAN_IFACE -o $LAN_IFACE -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -A FORWARD -i $LAN_IFACE -o $WAN_IFACE -j ACCEPT
