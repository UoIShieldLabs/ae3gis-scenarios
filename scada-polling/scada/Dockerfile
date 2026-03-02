FROM python:3.11-alpine

# Networking & debugging tools
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
    htop

# Python dependencies
RUN pip install --no-cache-dir pymodbus==3.6.9

# Bake in the script
COPY scada_poller.py /app/scada_poller.py

# Default env
ENV PLC_HOSTS=""
ENV POLL_INTERVAL=0.5
ENV RUN_DURATION=0

# Keep container running (user starts the script manually in GNS3 console)
CMD ["tail", "-f", "/dev/null"]
