FROM alpine:3.19

# Networking, routing, firewall & debugging tools
RUN apk add --no-cache \
    bash \
    vim \
    curl \
    wget \
    iproute2 \
    net-tools \
    iputils \
    tcpdump \
    bind-tools \
    iptables \
    nmap \
    busybox-extras \
    procps \
    htop \
    conntrack-tools

# Bake in the setup script
COPY dmz_setup.sh /app/dmz_setup.sh
RUN chmod +x /app/dmz_setup.sh

# Keep container running
CMD ["tail", "-f", "/dev/null"]
