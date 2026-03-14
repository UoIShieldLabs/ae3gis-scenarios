FROM alpine:3.19
RUN apk add --no-cache \
    bash vim curl wget iproute2 net-tools iputils \
    tcpdump bind-tools iptables nmap busybox-extras procps htop \
    conntrack-tools
COPY firewall_setup.sh /app/firewall_setup.sh
RUN chmod +x /app/firewall_setup.sh
CMD ["tail", "-f", "/dev/null"]
