FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    dnsmasq \
    openssh-server \
    openssh-client \
    net-tools \
    iputils-ping \
    iproute2 \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Create admin user
RUN useradd -m -s /bin/bash admin && \
    echo "admin:password" | chpasswd

# Configure SSH
RUN mkdir -p /var/run/sshd && \
    sed -i 's/#PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Copy DNS config
COPY dnsmasq.conf /etc/dnsmasq.d/corp.conf

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22 53/udp 53/tcp

CMD ["/entrypoint.sh"]
