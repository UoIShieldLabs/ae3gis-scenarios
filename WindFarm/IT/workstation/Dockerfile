FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    openssh-server \
    openssh-client \
    sshpass \
    curl \
    wget \
    ftp \
    lftp \
    dnsutils \
    net-tools \
    iputils-ping \
    iproute2 \
    nmap \
    mysql-client \
    python3 \
    bash \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Create admin user with password
RUN useradd -m -s /bin/bash admin && \
    echo "admin:password" | chpasswd && \
    mkdir -p /home/admin/Documents

# Configure SSH server
RUN mkdir -p /var/run/sshd && \
    sed -i 's/#PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config

# Copy traffic generation scripts
COPY traffic-gen/ /opt/traffic-gen/
RUN chmod +x /opt/traffic-gen/*.sh

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22

CMD ["/entrypoint.sh"]
