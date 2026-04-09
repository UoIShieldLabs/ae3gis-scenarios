#!/bin/bash
## $UPSTREAM_RTR should be set in the device metadata for routers. The value should be the subnet of the upstream router.

# UPSTREAM_RTR="${UPSTREAM_RTR}"

read ADDR DEV <<< $(ip route show | awk -v foo="$UPSTREAM_RTR" '$0 ~ foo {print $3, $5}')
ip route replace default via $ADDR dev $DEV